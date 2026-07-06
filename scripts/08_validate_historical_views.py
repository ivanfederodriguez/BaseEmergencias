"""
Valida las vistas historicas creadas sobre TiDB staging.
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
REPORT_PATH = PROJECT_ROOT / "data_intermediate" / "reporte_validacion_historical_views.xlsx"

VIEWS = [
    "vw_hist_resoluciones",
    "vw_hist_ddjj_personas",
    "vw_hist_productores",
    "vw_hist_tipoactividad",
    "vw_hist_agricultura",
    "vw_hist_cultivostipo",
    "vw_hist_cultivos",
    "vw_hist_ganaderia_resumen",
]

KEY_COLUMNS = {
    "vw_hist_resoluciones": ["evento_id"],
    "vw_hist_ddjj_personas": ["ddjj_hist_id", "evento_id"],
    "vw_hist_productores": ["productor_hist_id"],
    "vw_hist_tipoactividad": ["actividad_hist_id"],
    "vw_hist_agricultura": ["agricultura_hist_id", "evento_id"],
    "vw_hist_cultivostipo": ["cultivo_tipo_hist_id"],
    "vw_hist_cultivos": ["cultivo_hist_id"],
    "vw_hist_ganaderia_resumen": ["ganaderia_hist_id", "evento_id"],
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

    missing = [
        name
        for name, value in {
            "TIDB_USER": user,
            "TIDB_PASSWORD": password,
            "TIDB_HOST": host,
            "TIDB_PORT": port,
            "TIDB_DATABASE": database,
        }.items()
        if not value
    ]
    if missing:
        raise RuntimeError(f"Faltan variables en .env: {', '.join(missing)}")

    connect_args = ssl_connect_args()
    ensure_database(user, password, host, port, database, connect_args)
    return create_engine(
        connection_url(user, password, host, port, database),
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )


def query_df(engine: Engine, sql: str, params: dict | None = None) -> pd.DataFrame:
    with engine.begin() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def view_columns(engine: Engine, view: str) -> list[str]:
    df = query_df(
        engine,
        """
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :view
        ORDER BY ORDINAL_POSITION
        """,
        {"view": view},
    )
    return df["COLUMN_NAME"].tolist()


def main() -> None:
    engine = make_engine()
    summary_rows = []
    rows_frames = []
    events_frames = []
    years_frames = []
    null_frames = []
    flags_frames = []
    preview_frames = []

    for view in VIEWS:
        columns = view_columns(engine, view)
        if not columns:
            summary_rows.append({
                "vista": view,
                "existe": 0,
                "filas": 0,
                "vacia": 1,
                "eventos": None,
                "anio_min": None,
                "anio_max": None,
                "criticos": None,
                "observacion": "vista no encontrada",
            })
            continue

        row_count = int(query_df(engine, f"SELECT COUNT(*) AS n FROM `{view}`").loc[0, "n"])
        events = None
        anio_min = None
        anio_max = None
        criticos = None

        if "evento_id" in columns:
            events = int(query_df(engine, f"SELECT COUNT(DISTINCT evento_id) AS n FROM `{view}`").loc[0, "n"])
            events_df = query_df(engine, f"SELECT evento_id, COUNT(*) AS filas FROM `{view}` GROUP BY evento_id ORDER BY filas DESC LIMIT 5000")
            events_df.insert(0, "vista", view)
            events_frames.append(events_df)

        if "anio" in columns:
            years = query_df(engine, f"SELECT anio, COUNT(*) AS filas FROM `{view}` GROUP BY anio ORDER BY anio")
            years.insert(0, "vista", view)
            years_frames.append(years)
            year_range = query_df(engine, f"SELECT MIN(anio) AS anio_min, MAX(anio) AS anio_max FROM `{view}`")
            anio_min = year_range.loc[0, "anio_min"]
            anio_max = year_range.loc[0, "anio_max"]

        if "severidad_maxima" in columns:
            flags = query_df(engine, f"SELECT severidad_maxima, COUNT(*) AS filas FROM `{view}` GROUP BY severidad_maxima ORDER BY filas DESC")
            flags.insert(0, "vista", view)
            flags_frames.append(flags)
            criticos = int(query_df(engine, f"SELECT COUNT(*) AS n FROM `{view}` WHERE LOWER(COALESCE(severidad_maxima, '')) = 'critico'").loc[0, "n"])

        null_exprs = []
        for col in KEY_COLUMNS[view]:
            if col in columns:
                null_exprs.append(f"SUM(`{col}` IS NULL OR `{col}` = '') AS `{col}_nulos`")
        if null_exprs:
            nulls = query_df(engine, f"SELECT {', '.join(null_exprs)} FROM `{view}`")
            nulls.insert(0, "vista", view)
            null_frames.append(nulls)

        preview = query_df(engine, f"SELECT * FROM `{view}` LIMIT 25")
        preview.insert(0, "vista", view)
        preview_frames.append(preview)

        rows_frames.append(pd.DataFrame([{"vista": view, "filas": row_count}]))
        summary_rows.append({
            "vista": view,
            "existe": 1,
            "filas": row_count,
            "vacia": int(row_count == 0),
            "eventos": events,
            "anio_min": anio_min,
            "anio_max": anio_max,
            "criticos": criticos,
            "observacion": "",
        })

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(REPORT_PATH, engine="openpyxl") as writer:
        summary = pd.DataFrame(summary_rows)
        summary.to_excel(writer, index=False, sheet_name="resumen_vistas")
        pd.concat(rows_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="filas_por_vista")
        pd.concat(events_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="eventos_por_vista")
        pd.concat(years_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="anios_por_vista")
        pd.concat(null_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="nulos_clave")
        pd.concat(flags_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="flags_calidad")
        pd.concat(preview_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="preview_vistas")

    print(f"Reporte generado: {REPORT_PATH}")
    print(pd.DataFrame(summary_rows).to_string(index=False))


if __name__ == "__main__":
    main()
