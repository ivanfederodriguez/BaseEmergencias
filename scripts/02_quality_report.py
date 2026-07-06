"""
Genera un reporte de calidad sobre data_clean/emergencias_productores_raw_clean.csv.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data_clean" / "emergencias_productores_raw_clean.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data_intermediate" / "reporte_calidad.xlsx"

SURFACE_COLUMNS = [
    "superficie_total",
    "superficie_agricola_uso",
    "superficie_agricola_afectada",
    "superficie_ganadera_uso",
    "superficie_ganadera_afectada",
]


def potential_errors(df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []

    for column in SURFACE_COLUMNS:
        if column in df.columns:
            negative = df[df[column].fillna(0) < 0]
            if not negative.empty:
                records.append({"tipo_error": f"{column}_negativa", "cantidad_filas": len(negative)})

    checks = [
        ("superficie_agricola_afectada", "superficie_agricola_uso", "afectada_agricola_mayor_uso"),
        ("superficie_ganadera_afectada", "superficie_ganadera_uso", "afectada_ganadera_mayor_uso"),
        ("superficie_agricola_afectada", "superficie_total", "afectada_agricola_mayor_total"),
        ("superficie_ganadera_afectada", "superficie_total", "afectada_ganadera_mayor_total"),
    ]
    for affected, base, label in checks:
        if affected in df.columns and base in df.columns:
            mask = df[affected].notna() & df[base].notna() & (df[affected] > df[base])
            if mask.any():
                records.append({"tipo_error": label, "cantidad_filas": int(mask.sum())})

    for column in ["anio", "productor_nombre", "departamento"]:
        if column in df.columns:
            missing = df[column].isna().sum()
            if missing:
                records.append({"tipo_error": f"{column}_faltante", "cantidad_filas": int(missing)})

    return pd.DataFrame(records, columns=["tipo_error", "cantidad_filas"])


def build_quality_report(input_path: Path, output_path: Path) -> dict[str, pd.DataFrame]:
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo limpio: {input_path}")

    df = pd.read_csv(input_path, low_memory=False)
    for column in SURFACE_COLUMNS + [
        "existencias",
        "mortandad",
        "produccion_estimada",
        "produccion_obtenida",
        "porcentaje_afectacion_ganadera",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    duplicate_subset = [
        column
        for column in ["periodo", "productor_nombre", "documento_nro", "cuit_cuil", "departamento", "actividad", "cultivo"]
        if column in df.columns
    ]
    duplicates = df[df.duplicated(subset=duplicate_subset, keep=False)] if duplicate_subset else pd.DataFrame()

    sheets = {
        "preview": df.head(100),
        "nulos": df.isna().sum().reset_index(name="cantidad_nulos").rename(columns={"index": "columna"}),
        "filas_por_anio": df.groupby("anio", dropna=False).size().reset_index(name="filas") if "anio" in df.columns else pd.DataFrame(),
        "filas_por_departamento": df.groupby("departamento", dropna=False).size().reset_index(name="filas") if "departamento" in df.columns else pd.DataFrame(),
        "duplicados": duplicates.head(500),
        "resumen_superficies": df[[c for c in SURFACE_COLUMNS if c in df.columns]].describe().reset_index(),
        "errores_potenciales": potential_errors(df),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, sheet_df in sheets.items():
            sheet_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])

    return sheets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generar reporte de calidad de la tabla limpia.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sheets = build_quality_report(args.input, args.output)
    print(f"Reporte de calidad generado: {args.output}")
    for sheet_name, sheet_df in sheets.items():
        print(f"{sheet_name}: {len(sheet_df)} filas")


if __name__ == "__main__":
    main()
