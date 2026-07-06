"""
Valida que las tablas actuales copiadas existan en TiDB destino y coincidan
con el TiDB origen en filas y columnas.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "data_intermediate" / "reporte_validacion_tablas_actuales_destino.xlsx"

CURRENT_TABLES = [
    "ddjj_personas",
    "productores",
    "resoluciones",
    "agricultura",
    "bovinos",
    "adremas",
    "establecimientos",
    "tipoactividad",
    "tipojuridico",
    "cultivos",
    "cultivostipo",
    "tipodocumento",
    "provincias",
    "departamentos",
    "localidades",
    "domicilios",
    "ponderaciones_ddjj",
    "rubro_tipos",
    "perdidas_mejoras",
    "tipotenencia",
    "ovinos",
    "porcinos",
    "avicultura",
    "apicultura",
    "forestacion",
    "perdidas_invernaculos",
    "perdidas_plurianuales",
    "documentacion",
    "fotos",
]


def env_value(primary: str, fallback: str | None = None, default: str | None = None) -> str | None:
    return os.environ.get(primary) or (os.environ.get(fallback) if fallback else None) or default


def load_env_file(path: Path) -> None:
    if load_dotenv is not None:
        load_dotenv(path)
        return
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def ssl_connect_args(prefix: str = "") -> dict:
    ssl_ca = env_value(f"{prefix}TIDB_SSL_CA", "TIDB_SSL_CA")
    if not ssl_ca:
        return {}
    ca_path = Path(ssl_ca)
    if not ca_path.is_absolute():
        ca_path = PROJECT_ROOT / ca_path
    if not ca_path.exists():
        raise FileNotFoundError(f"{prefix}TIDB_SSL_CA apunta a un archivo inexistente: {ca_path}")
    return {"ssl": {"ca": str(ca_path)}}


def connection_url(user: str, password: str, host: str, port: str, database: str | None = None) -> str:
    db_part = f"/{database}" if database else ""
    return f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}{db_part}?charset=utf8mb4"


def make_engine(kind: str) -> Engine:
    load_env_file(PROJECT_ROOT / ".env")
    if kind == "source":
        user = env_value("SOURCE_TIDB_USER")
        password = env_value("SOURCE_TIDB_PASSWORD")
        host = env_value("SOURCE_TIDB_HOST")
        port = env_value("SOURCE_TIDB_PORT", default="4000")
        database = env_value("SOURCE_TIDB_DATABASE")
        labels = {
            "SOURCE_TIDB_USER": user,
            "SOURCE_TIDB_PASSWORD": password,
            "SOURCE_TIDB_HOST": host,
            "SOURCE_TIDB_PORT": port,
            "SOURCE_TIDB_DATABASE": database,
        }
        connect_args = ssl_connect_args("SOURCE_")
    else:
        user = env_value("TIDB_USER")
        password = env_value("TIDB_PASSWORD", "TIDB_PASS")
        host = env_value("TIDB_HOST")
        port = env_value("TIDB_PORT", default="4000")
        database = env_value("TIDB_DATABASE", "TIDB_DB")
        labels = {
            "TIDB_USER": user,
            "TIDB_PASSWORD/TIDB_PASS": password,
            "TIDB_HOST": host,
            "TIDB_PORT": port,
            "TIDB_DATABASE/TIDB_DB": database,
        }
        connect_args = ssl_connect_args("")

    missing = [name for name, value in labels.items() if not value]
    if missing:
        raise RuntimeError(f"Faltan variables para TiDB {kind}: {', '.join(missing)}")

    return create_engine(
        connection_url(user, password, host, port, database),
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


def query_df(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def table_exists(engine: Engine, table: str) -> bool:
    return bool(query_df(engine, """
        SELECT COUNT(*) AS n
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :table
          AND TABLE_TYPE = 'BASE TABLE'
    """, {"table": table}).loc[0, "n"])


def table_columns(engine: Engine, table: str) -> list[str]:
    if not table_exists(engine, table):
        return []
    df = query_df(engine, """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :table
        ORDER BY ORDINAL_POSITION
    """, {"table": table})
    return df["COLUMN_NAME"].tolist()


def count_rows(engine: Engine, table: str) -> int | None:
    if not table_exists(engine, table):
        return None
    return int(query_df(engine, f"SELECT COUNT(*) AS n FROM `{table}`").loc[0, "n"])


def main() -> None:
    source = make_engine("source")
    dest = make_engine("dest")

    summary_rows = []
    missing_rows = []
    column_rows = []
    compare_rows = []

    for table in CURRENT_TABLES:
        source_exists = table_exists(source, table)
        dest_exists = table_exists(dest, table)
        source_cols = table_columns(source, table)
        dest_cols = table_columns(dest, table)
        missing_in_dest = [col for col in source_cols if col not in dest_cols]
        extra_in_dest = [col for col in dest_cols if col not in source_cols]
        source_count = count_rows(source, table)
        dest_count = count_rows(dest, table)

        summary_rows.append({
            "tabla": table,
            "existe_origen": int(source_exists),
            "existe_destino": int(dest_exists),
            "filas_origen": source_count,
            "filas_destino": dest_count,
            "diferencia_filas": None if source_count is None or dest_count is None else dest_count - source_count,
            "columnas_origen": len(source_cols),
            "columnas_destino": len(dest_cols),
            "columnas_faltantes_destino": len(missing_in_dest),
            "columnas_extra_destino": len(extra_in_dest),
            "ok": int(source_exists and dest_exists and source_count == dest_count and not missing_in_dest),
        })
        compare_rows.append({
            "tabla": table,
            "filas_origen": source_count,
            "filas_destino": dest_count,
            "diferencia": None if source_count is None or dest_count is None else dest_count - source_count,
        })
        if not dest_exists:
            missing_rows.append({"tabla": table, "problema": "tabla_faltante_destino"})
        if not source_exists:
            missing_rows.append({"tabla": table, "problema": "tabla_faltante_origen"})
        for col in missing_in_dest:
            column_rows.append({"tabla": table, "columna": col, "problema": "faltante_en_destino"})
        for col in extra_in_dest:
            column_rows.append({"tabla": table, "columna": col, "problema": "extra_en_destino"})

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(REPORT_PATH, engine="openpyxl") as writer:
        summary = pd.DataFrame(summary_rows)
        summary.to_excel(writer, index=False, sheet_name="resumen")
        pd.DataFrame(missing_rows).to_excel(writer, index=False, sheet_name="tablas_faltantes")
        pd.DataFrame(column_rows).to_excel(writer, index=False, sheet_name="columnas")
        pd.DataFrame(compare_rows).to_excel(writer, index=False, sheet_name="conteos_origen_destino")

    print(f"Reporte generado: {REPORT_PATH}")
    print(pd.DataFrame(summary_rows).to_string(index=False))
    failures = [row for row in summary_rows if not row["ok"]]
    if failures:
        print(f"Validacion con problemas en {len(failures)} tabla(s). Ver reporte.")


if __name__ == "__main__":
    main()
