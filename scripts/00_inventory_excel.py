"""
Inventario no destructivo de archivos Excel historicos.

Lee archivos .xlsx, .xls y .xlsm desde data_raw/ por defecto y genera
data_intermediate/inventario_excel.xlsx con metadatos por hoja.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data_raw"
DEFAULT_OUTPUT = PROJECT_ROOT / "data_intermediate" / "inventario_excel.xlsx"
EXCEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm")


def list_excel_files(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in EXCEL_EXTENSIONS
        and not path.name.startswith("~$")
    )


def preview_to_text(df: pd.DataFrame, rows: int = 15) -> str:
    if df.empty:
        return ""
    return df.head(rows).to_string(index=False)


def inventory_workbook(path: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    try:
        workbook = pd.ExcelFile(path)
    except Exception as exc:
        return [
            {
                "archivo": path.name,
                "hoja": None,
                "cantidad_filas": None,
                "cantidad_columnas": None,
                "nombres_columnas_detectadas": None,
                "primeras_15_filas": None,
                "error_lectura": f"{type(exc).__name__}: {exc}",
            }
        ]

    for sheet_name in workbook.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet_name)
            records.append(
                {
                    "archivo": path.name,
                    "hoja": sheet_name,
                    "cantidad_filas": len(df),
                    "cantidad_columnas": len(df.columns),
                    "nombres_columnas_detectadas": " | ".join(map(str, df.columns)),
                    "primeras_15_filas": preview_to_text(df),
                    "error_lectura": None,
                }
            )
        except Exception as exc:
            records.append(
                {
                    "archivo": path.name,
                    "hoja": sheet_name,
                    "cantidad_filas": None,
                    "cantidad_columnas": None,
                    "nombres_columnas_detectadas": None,
                    "primeras_15_filas": None,
                    "error_lectura": f"{type(exc).__name__}: {exc}",
                }
            )

    return records


def build_inventory(input_dir: Path, output_path: Path) -> pd.DataFrame:
    if not input_dir.exists():
        raise FileNotFoundError(f"No existe la carpeta de entrada: {input_dir}")

    records: list[dict[str, object]] = []
    for excel_path in list_excel_files(input_dir):
        records.extend(inventory_workbook(excel_path))

    df_inventory = pd.DataFrame(
        records,
        columns=[
            "archivo",
            "hoja",
            "cantidad_filas",
            "cantidad_columnas",
            "nombres_columnas_detectadas",
            "primeras_15_filas",
            "error_lectura",
        ],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_inventory.to_excel(writer, index=False, sheet_name="inventario")

    return df_inventory


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventariar archivos Excel historicos.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inventory = build_inventory(args.input_dir, args.output)
    errores = inventory["error_lectura"].notna().sum() if not inventory.empty else 0
    print(f"Inventario generado: {args.output}")
    print(f"Hojas inventariadas: {len(inventory)}")
    print(f"Hojas con errores de lectura: {errores}")


if __name__ == "__main__":
    main()
