"""
Consolida y relaciona archivos historicos por evento.

El script distingue:
- consolidate_same_level: archivos del mismo nivel, deduplicables entre si.
- complementary_detail: archivos principal/detalle, relacionados por evento_id + iddj.
- standalone: archivos sin relacion explicita.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = PROJECT_ROOT / "data_clean" / "emergencias_productores_raw_clean.csv"
DEFAULT_MAPPING = PROJECT_ROOT / "config" / "event_mapping.csv"
DEFAULT_OUTPUT_CONSOLIDATED = PROJECT_ROOT / "data_clean" / "emergencias_productores_consolidated.csv"
DEFAULT_OUTPUT_PRINCIPAL = PROJECT_ROOT / "data_clean" / "emergencias_declaraciones_principal.csv"
DEFAULT_OUTPUT_AGRICOLA = PROJECT_ROOT / "data_clean" / "emergencias_agricolas_detalle.csv"
DEFAULT_REPORT_CONFLICTS = PROJECT_ROOT / "data_intermediate" / "reporte_conflictos_consolidacion.xlsx"
DEFAULT_REPORT_RELATIONS = PROJECT_ROOT / "data_intermediate" / "reporte_relaciones_eventos.xlsx"

NUMERIC_COLUMNS = [
    "superficie_total",
    "superficie_agricola_uso",
    "superficie_agricola_afectada",
    "superficie_ganadera_uso",
    "superficie_ganadera_afectada",
    "existencias",
    "mortandad",
    "produccion_estimada",
    "produccion_obtenida",
]

ALT_SAME_LEVEL_KEY_COLUMNS = [
    "documento_nro",
    "productor_nombre",
    "departamento",
    "actividad",
    "cultivo",
]

PRINCIPAL_ALT_KEY_COLUMNS = [
    "documento_nro",
    "productor_nombre",
    "departamento",
]

DETAIL_KEY_COLUMNS = [
    "evento_id",
    "iddj",
    "especie",
    "categoria",
]


def normalize_key(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().upper()
    if not text or text in {"NAN", "NONE", "S/D", "SD"}:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    return text.strip("_")


def normalize_code(value: object) -> str:
    return re.sub(r"\.0$", "", normalize_key(value))


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for column in columns:
        if column not in df.columns:
            df[column] = pd.NA
    return df


def coalesce_event_id(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "evento_id_map" in df.columns:
        raw_event = df["evento_id"] if "evento_id" in df.columns else pd.Series(pd.NA, index=df.index)
        df["evento_id"] = df["evento_id_map"].fillna(raw_event).fillna(df.get("periodo"))
        df = df.drop(columns=["evento_id_map"])
    else:
        df["evento_id"] = df["evento_id"].fillna(df.get("periodo")) if "evento_id" in df.columns else df.get("periodo")
    return df


def load_inputs(input_path: Path, mapping_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"No existe el archivo raw_clean: {input_path}")
    if not mapping_path.exists():
        raise FileNotFoundError(f"No existe el mapeo de eventos: {mapping_path}")

    raw = pd.read_csv(input_path, dtype={"codigo": "string", "iddj": "string"}, low_memory=False)
    mapping = pd.read_csv(mapping_path)

    required_mapping = {
        "source_file",
        "evento_id",
        "dataset_role",
        "relation_type",
        "evento_nombre",
        "anio_inicio",
        "anio_fin",
        "prioridad",
        "comentario",
    }
    missing = required_mapping.difference(mapping.columns)
    if missing:
        raise ValueError(f"Faltan columnas en event_mapping.csv: {sorted(missing)}")

    df = raw.merge(mapping, on="source_file", how="left", suffixes=("", "_map"), indicator="mapping_status")
    df["sin_event_mapping"] = df["mapping_status"].eq("left_only")
    df = df.drop(columns=["mapping_status"])
    df = coalesce_event_id(df)
    df["dataset_role"] = df["dataset_role"].fillna("desconocido")
    df["relation_type"] = df["relation_type"].fillna("standalone")
    df["evento_nombre"] = df["evento_nombre"].fillna(df["evento_id"])
    df["prioridad"] = pd.to_numeric(df["prioridad"], errors="coerce").fillna(0)
    return df


def build_same_level_key(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df, ["codigo", "evento_id"] + ALT_SAME_LEVEL_KEY_COLUMNS)
    df["evento_id_norm"] = df["evento_id"].map(normalize_key)
    df["codigo_norm"] = df["codigo"].map(normalize_code)
    has_code = df["codigo_norm"].ne("")

    alt_key = df[ALT_SAME_LEVEL_KEY_COLUMNS].map(normalize_key).agg("|".join, axis=1)
    df["dedup_key_type"] = has_code.map({True: "codigo", False: "alternativa"})
    df["dedup_key"] = df["evento_id_norm"] + "||" + df["dedup_key_type"].str.upper() + "||"
    df.loc[has_code, "dedup_key"] = df.loc[has_code, "dedup_key"] + df.loc[has_code, "codigo_norm"]
    df.loc[~has_code, "dedup_key"] = df.loc[~has_code, "dedup_key"] + alt_key.loc[~has_code]
    return df


def build_principal_key(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df, ["evento_id", "iddj"] + PRINCIPAL_ALT_KEY_COLUMNS)
    df["evento_id_norm"] = df["evento_id"].map(normalize_key)
    df["iddj_norm"] = df["iddj"].map(normalize_code)
    has_iddj = df["iddj_norm"].ne("")

    alt_key = df[PRINCIPAL_ALT_KEY_COLUMNS].map(normalize_key).agg("|".join, axis=1)
    df["principal_key_type"] = has_iddj.map({True: "iddj", False: "alternativa"})
    df["principal_key"] = df["evento_id_norm"] + "||" + df["principal_key_type"].str.upper() + "||"
    df.loc[has_iddj, "principal_key"] = df.loc[has_iddj, "principal_key"] + df.loc[has_iddj, "iddj_norm"]
    df.loc[~has_iddj, "principal_key"] = df.loc[~has_iddj, "principal_key"] + alt_key.loc[~has_iddj]
    return df


def build_detail_key(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_columns(df, DETAIL_KEY_COLUMNS)
    df["evento_id_norm"] = df["evento_id"].map(normalize_key)
    df["iddj_norm"] = df["iddj"].map(normalize_code)
    df["especie_norm"] = df["especie"].map(normalize_key)
    df["categoria_norm"] = df["categoria"].map(normalize_key)
    df["detalle_key"] = df["evento_id_norm"] + "||" + df["iddj_norm"] + "||" + df["especie_norm"] + "||" + df["categoria_norm"]
    return df


def duplicate_rows(df: pd.DataFrame, key_column: str) -> pd.DataFrame:
    if df.empty or key_column not in df.columns:
        return pd.DataFrame()
    mask = df.duplicated(key_column, keep=False) & df[key_column].notna() & df[key_column].ne("")
    return df.loc[mask].sort_values(["evento_id", key_column, "prioridad"], ascending=[True, True, False])


def conflict_report(duplicates: pd.DataFrame, key_column: str) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    if duplicates.empty:
        return pd.DataFrame(
            columns=[
                "evento_id",
                "clave",
                "variable",
                "valores_distintos",
                "source_files",
                "prioridades",
                "cantidad_registros",
            ]
        )

    for key_value, group in duplicates.groupby(key_column, dropna=False):
        for column in NUMERIC_COLUMNS:
            if column not in group.columns:
                continue
            values = pd.to_numeric(group[column], errors="coerce").dropna()
            distinct = sorted(values.unique())
            if len(distinct) > 1:
                records.append(
                    {
                        "evento_id": group["evento_id"].iloc[0],
                        "clave": key_value,
                        "variable": column,
                        "valores_distintos": " | ".join(str(value) for value in distinct),
                        "source_files": " | ".join(sorted(group["source_file"].dropna().astype(str).unique())),
                        "prioridades": " | ".join(str(value) for value in sorted(group["prioridad"].dropna().unique())),
                        "cantidad_registros": len(group),
                    }
                )
    return pd.DataFrame(records)


def consolidate_same_level(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    same = df[df["relation_type"].isin(["consolidate_same_level", "standalone"])].copy()
    same = build_same_level_key(same)
    same["_row_order"] = range(len(same))
    duplicates = duplicate_rows(same, "dedup_key")
    conflicts = conflict_report(duplicates, "dedup_key")
    consolidated = (
        same.sort_values(["dedup_key", "prioridad", "_row_order"], ascending=[True, False, True])
        .drop_duplicates("dedup_key", keep="first")
        .drop(columns=["_row_order"])
        .reset_index(drop=True)
    )
    return consolidated, duplicates.drop(columns=["_row_order"], errors="ignore"), conflicts


def split_complementary(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    comp = df[df["relation_type"].eq("complementary_detail")].copy()
    principal = build_principal_key(comp[comp["dataset_role"].eq("principal")].copy())
    agricola = build_detail_key(comp[comp["dataset_role"].eq("detalle_agricola")].copy())

    principal["_row_order"] = range(len(principal))
    agricola["_row_order"] = range(len(agricola))

    dup_principal = duplicate_rows(principal, "principal_key")
    dup_detalle = duplicate_rows(agricola, "detalle_key")

    principal_out = (
        principal.sort_values(["principal_key", "prioridad", "_row_order"], ascending=[True, False, True])
        .drop_duplicates("principal_key", keep="first")
        .drop(columns=["_row_order"])
        .reset_index(drop=True)
    )

    agricola_no_exact = agricola.drop_duplicates().copy()
    agricola_out = (
        agricola_no_exact.sort_values(["detalle_key", "prioridad", "_row_order"], ascending=[True, False, True])
        .drop_duplicates("detalle_key", keep="first")
        .drop(columns=["_row_order"])
        .reset_index(drop=True)
    )

    return (
        principal_out,
        agricola_out,
        dup_principal.drop(columns=["_row_order"], errors="ignore"),
        dup_detalle.drop(columns=["_row_order"], errors="ignore"),
    )


def relation_reports(df: pd.DataFrame, principal: pd.DataFrame, agricola: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    archivos_por_evento = (
        df.groupby(["evento_id", "source_file", "dataset_role", "relation_type"], dropna=False)
        .size()
        .reset_index(name="filas_raw_clean")
        .sort_values(["evento_id", "source_file"])
    )
    roles_por_evento = (
        df.groupby(["evento_id", "relation_type", "dataset_role"], dropna=False)
        .agg(archivos=("source_file", "nunique"), filas=("source_file", "size"))
        .reset_index()
        .sort_values(["evento_id", "relation_type", "dataset_role"])
    )

    p_keys = set(principal["principal_key"]) if "principal_key" in principal.columns else set()
    d_parent_keys = set(
        agricola["evento_id_norm"] + "||IDDJ||" + agricola["iddj_norm"]
    ) if not agricola.empty and {"evento_id_norm", "iddj_norm"}.issubset(agricola.columns) else set()

    principales_sin_detalle = principal[~principal["principal_key"].isin(d_parent_keys)].copy() if p_keys else pd.DataFrame()
    detalles_sin_principal = agricola[~(agricola["evento_id_norm"] + "||IDDJ||" + agricola["iddj_norm"]).isin(p_keys)].copy() if d_parent_keys else pd.DataFrame()
    return archivos_por_evento, roles_por_evento, principales_sin_detalle, detalles_sin_principal


def write_outputs(
    consolidated: pd.DataFrame,
    principal: pd.DataFrame,
    agricola: pd.DataFrame,
    duplicates_same: pd.DataFrame,
    conflicts_same: pd.DataFrame,
    dup_principal: pd.DataFrame,
    dup_detalle: pd.DataFrame,
    report_tables: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame],
    output_consolidated: Path,
    output_principal: Path,
    output_agricola: Path,
    report_conflicts: Path,
    report_relations: Path,
) -> None:
    for path in [output_consolidated, output_principal, output_agricola, report_conflicts, report_relations]:
        path.parent.mkdir(parents=True, exist_ok=True)

    consolidated.to_csv(output_consolidated, index=False, encoding="utf-8-sig")
    principal.to_csv(output_principal, index=False, encoding="utf-8-sig")
    agricola.to_csv(output_agricola, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(report_conflicts, engine="openpyxl") as writer:
        duplicates_same.to_excel(writer, index=False, sheet_name="duplicados_evento")
        conflicts_same.to_excel(writer, index=False, sheet_name="conflictos_valores")
        consolidated.groupby("evento_id", dropna=False).size().reset_index(name="filas_consolidadas").to_excel(
            writer, index=False, sheet_name="resumen_por_evento"
        )
        consolidated[consolidated["sin_event_mapping"]].groupby(["source_file", "periodo"], dropna=False).size().reset_index(name="filas").to_excel(
            writer, index=False, sheet_name="archivos_sin_evento_id"
        )

    archivos_por_evento, roles_por_evento, principales_sin_detalle, detalles_sin_principal = report_tables
    with pd.ExcelWriter(report_relations, engine="openpyxl") as writer:
        archivos_por_evento.to_excel(writer, index=False, sheet_name="archivos_por_evento")
        roles_por_evento.to_excel(writer, index=False, sheet_name="roles_por_evento")
        principales_sin_detalle.to_excel(writer, index=False, sheet_name="principales_sin_detalle")
        detalles_sin_principal.to_excel(writer, index=False, sheet_name="detalles_sin_principal")
        dup_principal.to_excel(writer, index=False, sheet_name="duplicados_principal")
        dup_detalle.to_excel(writer, index=False, sheet_name="duplicados_detalle")
        conflicts_same.to_excel(writer, index=False, sheet_name="conflictos_consolidacion")


def run_pipeline(
    input_path: Path,
    mapping_path: Path,
    output_consolidated: Path,
    output_principal: Path,
    output_agricola: Path,
    report_conflicts: Path,
    report_relations: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_inputs(input_path, mapping_path)
    consolidated, duplicates_same, conflicts_same = consolidate_same_level(df)
    principal, agricola, dup_principal, dup_detalle = split_complementary(df)
    report_tables = relation_reports(df, principal, agricola)
    write_outputs(
        consolidated,
        principal,
        agricola,
        duplicates_same,
        conflicts_same,
        dup_principal,
        dup_detalle,
        report_tables,
        output_consolidated,
        output_principal,
        output_agricola,
        report_conflicts,
        report_relations,
    )
    return consolidated, principal, agricola, df


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Consolidar y relacionar registros raw_clean por evento.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--output-consolidated", type=Path, default=DEFAULT_OUTPUT_CONSOLIDATED)
    parser.add_argument("--output-principal", type=Path, default=DEFAULT_OUTPUT_PRINCIPAL)
    parser.add_argument("--output-agricola", type=Path, default=DEFAULT_OUTPUT_AGRICOLA)
    parser.add_argument("--report-conflicts", type=Path, default=DEFAULT_REPORT_CONFLICTS)
    parser.add_argument("--report-relations", type=Path, default=DEFAULT_REPORT_RELATIONS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    consolidated, principal, agricola, df = run_pipeline(
        args.input,
        args.mapping,
        args.output_consolidated,
        args.output_principal,
        args.output_agricola,
        args.report_conflicts,
        args.report_relations,
    )
    complementary_events = df.loc[df["relation_type"].eq("complementary_detail"), "evento_id"].dropna().nunique()
    same_level_events = df.loc[df["relation_type"].eq("consolidate_same_level"), "evento_id"].dropna().nunique()
    print(f"Archivo consolidado mismo nivel generado: {args.output_consolidated}")
    print(f"Filas consolidado mismo nivel/standalone: {len(consolidated)}")
    print(f"Tabla principal generada: {args.output_principal}")
    print(f"Filas principal: {len(principal)}")
    print(f"Tabla agricola detalle generada: {args.output_agricola}")
    print(f"Filas agricola detalle: {len(agricola)}")
    print(f"Eventos con archivos complementarios: {complementary_events}")
    print(f"Eventos con archivos consolidados del mismo nivel: {same_level_events}")
    print(f"Reporte relaciones generado: {args.report_relations}")


if __name__ == "__main__":
    main()
