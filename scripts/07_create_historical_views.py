"""
Crea vistas SQL historicas sobre las tablas staging de TiDB.

No modifica tablas staging ni cambia el dashboard Streamlit.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = PROJECT_ROOT / "sql" / "01_create_historical_views.sql"

EXPECTED_VIEWS = [
    "vw_hist_resoluciones",
    "vw_hist_ddjj_personas",
    "vw_hist_productores",
    "vw_hist_tipoactividad",
    "vw_hist_agricultura",
    "vw_hist_cultivostipo",
    "vw_hist_cultivos",
    "vw_hist_ganaderia_resumen",
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


def split_sql_statements(sql_text: str) -> list[str]:
    statements = []
    buffer = []
    in_single = False
    in_double = False

    for char in sql_text:
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        if char == ";" and not in_single and not in_double:
            statement = "".join(buffer).strip()
            if statement:
                statements.append(statement)
            buffer = []
        else:
            buffer.append(char)

    tail = "".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def main() -> None:
    if not SQL_PATH.exists():
        raise FileNotFoundError(SQL_PATH)

    engine = make_engine()
    sql_text = SQL_PATH.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))

        created = conn.execute(
            text(
                """
                SELECT TABLE_NAME
                FROM information_schema.VIEWS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME IN (
                    'vw_hist_resoluciones',
                    'vw_hist_ddjj_personas',
                    'vw_hist_productores',
                    'vw_hist_tipoactividad',
                    'vw_hist_agricultura',
                    'vw_hist_cultivostipo',
                    'vw_hist_cultivos',
                    'vw_hist_ganaderia_resumen'
                  )
                ORDER BY TABLE_NAME
                """
            )
        ).fetchall()

    created_names = [row.TABLE_NAME for row in created]
    print("Vistas creadas/verificadas:")
    for view in EXPECTED_VIEWS:
        status = "OK" if view in created_names else "NO ENCONTRADA"
        print(f"- {view}: {status}")


if __name__ == "__main__":
    main()
