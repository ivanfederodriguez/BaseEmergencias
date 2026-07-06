"""
Valida tablas staging en TiDB contra los CSV locales armonizados.
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
DATA_DIR = PROJECT_ROOT / "data_clean"
REPORT_PATH = PROJECT_ROOT / "data_intermediate" / "reporte_validacion_tidb_staging.xlsx"

TABLES = {
    "stg_emergencias_productores_consolidated": DATA_DIR / "emergencias_productores_consolidated.csv",
    "stg_emergencias_declaraciones_principal": DATA_DIR / "emergencias_declaraciones_principal.csv",
    "stg_emergencias_agricolas_detalle": DATA_DIR / "emergencias_agricolas_detalle.csv",
}

KEYS = {
    "stg_emergencias_productores_consolidated": ["evento_id", "codigo"],
    "stg_emergencias_declaraciones_principal": ["evento_id", "iddj"],
    "stg_emergencias_agricolas_detalle": ["evento_id", "iddj", "especie", "categoria"],
}


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


def ssl_connect_args() -> dict:
    ssl_ca = env_value("TIDB_SSL_CA")
    if not ssl_ca:
        print("TIDB_SSL_CA no definido; se intentara conectar sin ssl_ca.")
        print("Si usas TiDB Cloud, descarga el certificado CA y define TIDB_SSL_CA=certs/isrgrootx1.pem")
        return {}

    ca_path = Path(ssl_ca)
    if not ca_path.is_absolute():
        ca_path = PROJECT_ROOT / ca_path
    if not ca_path.exists():
        raise FileNotFoundError(
            f"TIDB_SSL_CA apunta a un archivo inexistente: {ca_path}\n"
            "Si usas TiDB Cloud, descarga el certificado CA y define TIDB_SSL_CA=certs/isrgrootx1.pem"
        )
    return {"ssl": {"ca": str(ca_path)}}


def connection_url(user: str, password: str, host: str, port: str, database: str | None = None) -> str:
    db_part = f"/{database}" if database else ""
    return f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}{db_part}?charset=utf8mb4"


def ensure_database(user: str, password: str, host: str, port: str, database: str, connect_args: dict) -> None:
    server_engine = create_engine(
        connection_url(user, password, host, port),
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )
    try:
        with server_engine.begin() as conn:
            conn.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    finally:
        server_engine.dispose()


def make_engine() -> Engine:
    load_env_file(PROJECT_ROOT / ".env")
    user = env_value("TIDB_USER")
    password = env_value("TIDB_PASSWORD", "TIDB_PASS")
    host = env_value("TIDB_HOST")
    port = env_value("TIDB_PORT", default="4000")
    database = env_value("TIDB_DATABASE", "TIDB_DB")
    missing = [name for name, value in {
        "TIDB_USER": user,
        "TIDB_PASSWORD": password,
        "TIDB_HOST": host,
        "TIDB_PORT": port,
        "TIDB_DATABASE": database,
    }.items() if not value]
    if missing:
        raise RuntimeError(f"Faltan variables en .env: {', '.join(missing)}")

    connect_args = ssl_connect_args()
    ensure_database(user, password, host, port, database, connect_args)
    url = connection_url(user, password, host, port, database)
    return create_engine(url, pool_pre_ping=True, future=True, connect_args=connect_args)


def read_local(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def scalar(engine: Engine, sql: str, params: dict | None = None):
    with engine.begin() as conn:
        return conn.execute(text(sql), params or {}).scalar()


def query_df(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def duplicate_sql(table: str, key_cols: list[str]) -> str:
    key_expr = ", ".join(f"`{col}`" for col in key_cols)
    not_null = " AND ".join(f"`{col}` IS NOT NULL" for col in key_cols)
    return f"""
        SELECT {key_expr}, COUNT(*) AS duplicados
        FROM `{table}`
        WHERE {not_null}
        GROUP BY {key_expr}
        HAVING COUNT(*) > 1
        ORDER BY duplicados DESC
        LIMIT 5000
    """


def main() -> None:
    engine = make_engine()
    summary_rows = []
    compare_rows = []
    anio_frames = []
    evento_frames = []
    flags_frames = []
    dup_frames = []
    null_frames = []

    for table, csv_path in TABLES.items():
        local = read_local(csv_path)
        local_rows = len(local)
        local_events = local["evento_id"].nunique(dropna=True) if "evento_id" in local.columns else 0
        local_sources = local["source_file"].nunique(dropna=True) if "source_file" in local.columns else 0
        local_min_year = pd.to_numeric(local.get("anio"), errors="coerce").min()
        local_max_year = pd.to_numeric(local.get("anio"), errors="coerce").max()
        local_critical = int(local.get("severidad_maxima", pd.Series(dtype=str)).astype(str).str.lower().eq("critico").sum())
        local_event_nulls = int(local["evento_id"].isna().sum()) if "evento_id" in local.columns else local_rows

        tidb_rows = scalar(engine, f"SELECT COUNT(*) FROM `{table}`")
        tidb_events = scalar(engine, f"SELECT COUNT(DISTINCT evento_id) FROM `{table}`")
        tidb_sources = scalar(engine, f"SELECT COUNT(DISTINCT source_file) FROM `{table}`")
        year_range = query_df(engine, f"SELECT MIN(anio) AS anio_min, MAX(anio) AS anio_max FROM `{table}`")
        tidb_critical = scalar(engine, f"SELECT COUNT(*) FROM `{table}` WHERE LOWER(COALESCE(severidad_maxima, '')) = 'critico'")
        tidb_event_nulls = scalar(engine, f"SELECT COUNT(*) FROM `{table}` WHERE evento_id IS NULL")

        summary_rows.append({
            "tabla": table,
            "filas_tidb": tidb_rows,
            "eventos_tidb": tidb_events,
            "anio_min_tidb": year_range.loc[0, "anio_min"],
            "anio_max_tidb": year_range.loc[0, "anio_max"],
            "source_file_tidb": tidb_sources,
            "criticos_tidb": tidb_critical,
            "evento_id_nulos_tidb": tidb_event_nulls,
        })
        compare_rows.append({
            "tabla": table,
            "filas_local": local_rows,
            "filas_tidb": tidb_rows,
            "diferencia_filas": tidb_rows - local_rows,
            "eventos_local": local_events,
            "eventos_tidb": tidb_events,
            "source_file_local": local_sources,
            "source_file_tidb": tidb_sources,
            "anio_min_local": local_min_year,
            "anio_min_tidb": year_range.loc[0, "anio_min"],
            "anio_max_local": local_max_year,
            "anio_max_tidb": year_range.loc[0, "anio_max"],
            "criticos_local": local_critical,
            "criticos_tidb": tidb_critical,
            "evento_id_nulos_local": local_event_nulls,
            "evento_id_nulos_tidb": tidb_event_nulls,
        })

        anio = query_df(engine, f"SELECT anio, COUNT(*) AS filas FROM `{table}` GROUP BY anio ORDER BY anio")
        anio.insert(0, "tabla", table)
        anio_frames.append(anio)

        evento = query_df(engine, f"SELECT evento_id, COUNT(*) AS filas FROM `{table}` GROUP BY evento_id ORDER BY filas DESC")
        evento.insert(0, "tabla", table)
        evento_frames.append(evento)

        flags = query_df(engine, f"SELECT severidad_maxima, COUNT(*) AS filas FROM `{table}` GROUP BY severidad_maxima ORDER BY filas DESC")
        flags.insert(0, "tabla", table)
        flags_frames.append(flags)

        dups = query_df(engine, duplicate_sql(table, KEYS[table]))
        dups.insert(0, "tabla", table)
        dup_frames.append(dups)

        nulls = query_df(engine, f"""
            SELECT
                SUM(evento_id IS NULL) AS evento_id_nulos,
                SUM(source_file IS NULL) AS source_file_nulos,
                SUM(source_sheet IS NULL) AS source_sheet_nulos
            FROM `{table}`
        """)
        nulls.insert(0, "tabla", table)
        null_frames.append(nulls)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(REPORT_PATH, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="resumen_tablas")
        pd.DataFrame(compare_rows).to_excel(writer, index=False, sheet_name="conteos_local_vs_tidb")
        pd.concat(anio_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="filas_por_anio_tidb")
        pd.concat(evento_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="filas_por_evento_tidb")
        pd.concat(flags_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="flags_tidb")
        pd.concat(dup_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="duplicados_tidb")
        pd.concat(null_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="nulos_clave_tidb")

    print(f"Reporte generado: {REPORT_PATH}")
    print(pd.DataFrame(compare_rows).to_string(index=False))


if __name__ == "__main__":
    main()
