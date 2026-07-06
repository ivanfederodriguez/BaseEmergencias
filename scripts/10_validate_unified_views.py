"""
Valida vistas unificadas vw_all_* en TiDB.
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
REPORT_PATH = PROJECT_ROOT / "data_intermediate" / "reporte_validacion_unified_views.xlsx"

VIEWS = [
    "vw_all_resoluciones",
    "vw_all_ddjj_personas",
    "vw_all_productores",
    "vw_all_tipoactividad",
    "vw_all_agricultura",
    "vw_all_cultivos",
    "vw_all_cultivostipo",
    "vw_all_ganaderia_resumen",
]

KEY_COLUMNS = {
    "vw_all_resoluciones": ["resolucion_all_id"],
    "vw_all_ddjj_personas": ["ddjj_all_id"],
    "vw_all_productores": ["productor_all_id"],
    "vw_all_tipoactividad": ["actividad_all_id"],
    "vw_all_agricultura": ["agricultura_all_id"],
    "vw_all_cultivos": ["cultivo_all_id"],
    "vw_all_cultivostipo": ["cultivo_tipo_all_id"],
    "vw_all_ganaderia_resumen": ["ganaderia_all_id"],
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


def duplicate_query(view: str, key: str) -> str:
    return f"""
        SELECT origen_dato, `{key}` AS clave, COUNT(*) AS duplicados
        FROM `{view}`
        WHERE `{key}` IS NOT NULL AND `{key}` <> ''
        GROUP BY origen_dato, `{key}`
        HAVING COUNT(*) > 1
        ORDER BY duplicados DESC
        LIMIT 5000
    """


def main() -> None:
    engine = make_engine()
    summary_rows = []
    origen_frames = []
    year_frames = []
    event_frames = []
    null_frames = []
    duplicate_frames = []
    flag_frames = []
    preview_frames = []

    for view in VIEWS:
        columns = view_columns(engine, view)
        if not columns:
            summary_rows.append({
                "vista": view,
                "existe": 0,
                "filas": 0,
                "vacia": 1,
                "origenes": None,
                "historicos": None,
                "actuales": None,
                "observacion": "vista no encontrada",
            })
            continue

        total = int(query_df(engine, f"SELECT COUNT(*) AS n FROM `{view}`").loc[0, "n"])
        by_origin = query_df(engine, f"SELECT origen_dato, COUNT(*) AS filas FROM `{view}` GROUP BY origen_dato ORDER BY origen_dato")
        by_origin.insert(0, "vista", view)
        origen_frames.append(by_origin)

        actual_rows = int(by_origin.loc[by_origin["origen_dato"].eq("actual"), "filas"].sum()) if not by_origin.empty else 0
        hist_rows = int(by_origin.loc[by_origin["origen_dato"].eq("historico"), "filas"].sum()) if not by_origin.empty else 0

        if "anio" in columns:
            years = query_df(engine, f"SELECT origen_dato, anio, COUNT(*) AS filas FROM `{view}` GROUP BY origen_dato, anio ORDER BY origen_dato, anio")
            years.insert(0, "vista", view)
            year_frames.append(years)

        if "evento_id" in columns:
            events = query_df(engine, f"SELECT origen_dato, evento_id, COUNT(*) AS filas FROM `{view}` WHERE evento_id IS NOT NULL GROUP BY origen_dato, evento_id ORDER BY origen_dato, filas DESC LIMIT 5000")
            events.insert(0, "vista", view)
            event_frames.append(events)

        null_exprs = []
        for key in KEY_COLUMNS[view]:
            if key in columns:
                null_exprs.append(f"SUM(`{key}` IS NULL OR `{key}` = '') AS `{key}_nulos`")
        if "origen_dato" in columns and null_exprs:
            nulls = query_df(engine, f"SELECT origen_dato, {', '.join(null_exprs)} FROM `{view}` GROUP BY origen_dato")
            nulls.insert(0, "vista", view)
            null_frames.append(nulls)

        for key in KEY_COLUMNS[view]:
            if key in columns:
                dups = query_df(engine, duplicate_query(view, key))
                dups.insert(0, "vista", view)
                dups.insert(1, "clave_validada", key)
                duplicate_frames.append(dups)

        if "severidad_maxima" in columns:
            flags = query_df(
                engine,
                f"""
                SELECT origen_dato, severidad_maxima, COUNT(*) AS filas
                FROM `{view}`
                WHERE origen_dato = 'historico'
                GROUP BY origen_dato, severidad_maxima
                ORDER BY filas DESC
                """,
            )
            flags.insert(0, "vista", view)
            flag_frames.append(flags)

        preview = query_df(engine, f"SELECT * FROM `{view}` LIMIT 25")
        preview.insert(0, "vista", view)
        preview_frames.append(preview)

        summary_rows.append({
            "vista": view,
            "existe": 1,
            "filas": total,
            "vacia": int(total == 0),
            "origenes": ",".join(by_origin["origen_dato"].astype(str).tolist()),
            "historicos": hist_rows,
            "actuales": actual_rows,
            "observacion": "sin filas actuales en TiDB" if actual_rows == 0 else "",
        })

    empty = pd.DataFrame()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(REPORT_PATH, engine="openpyxl") as writer:
        summary = pd.DataFrame(summary_rows)
        summary.to_excel(writer, index=False, sheet_name="resumen_vistas")
        (pd.concat(origen_frames, ignore_index=True) if origen_frames else empty).to_excel(writer, index=False, sheet_name="filas_por_origen")
        (pd.concat(year_frames, ignore_index=True) if year_frames else empty).to_excel(writer, index=False, sheet_name="anios_por_origen")
        (pd.concat(event_frames, ignore_index=True) if event_frames else empty).to_excel(writer, index=False, sheet_name="eventos_por_origen")
        (pd.concat(null_frames, ignore_index=True) if null_frames else empty).to_excel(writer, index=False, sheet_name="nulos_clave")
        (pd.concat(duplicate_frames, ignore_index=True) if duplicate_frames else empty).to_excel(writer, index=False, sheet_name="duplicados")
        (pd.concat(flag_frames, ignore_index=True) if flag_frames else empty).to_excel(writer, index=False, sheet_name="flags_historicos")
        (pd.concat(preview_frames, ignore_index=True) if preview_frames else empty).to_excel(writer, index=False, sheet_name="preview_vistas")

    print(f"Reporte generado: {REPORT_PATH}")
    print(pd.DataFrame(summary_rows).to_string(index=False))


if __name__ == "__main__":
    main()
