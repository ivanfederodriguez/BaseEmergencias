"""
Carga controlada de tablas armonizadas a staging en TiDB/MySQL.

No crea tablas productivas ni modifica Streamlit. Las tablas staging se
truncan antes de cada carga.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.types import Boolean, DateTime, Float, Integer, String, Text

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data_clean"

TABLES = {
    "stg_emergencias_productores_consolidated": DATA_DIR / "emergencias_productores_consolidated.csv",
    "stg_emergencias_declaraciones_principal": DATA_DIR / "emergencias_declaraciones_principal.csv",
    "stg_emergencias_agricolas_detalle": DATA_DIR / "emergencias_agricolas_detalle.csv",
}

INDEX_COLUMNS = [
    "evento_id",
    "anio",
    "departamento",
    "actividad",
    "cultivo",
    "source_file",
    "severidad_maxima",
]

STRING_DTYPES = {
    "evento_id": String(100),
    "dto": String(100),
    "source_file": String(255),
    "source_sheet": String(255),
    "dataset_role": String(50),
    "relation_type": String(50),
    "productor_nombre": String(255),
    "documento_nro": String(50),
    "cuit_cuil": String(50),
    "departamento": String(100),
    "localidad": String(150),
    "paraje": String(150),
    "actividad": String(100),
    "cultivo": String(150),
    "especie": String(150),
    "categoria": String(150),
    "severidad_maxima": String(50),
}

INTEGER_COLUMNS = {"anio"}
DATETIME_COLUMNS = {"fecha_carga"}
TEXT_TYPES = {"text", "tinytext", "mediumtext", "longtext", "blob", "tinyblob", "mediumblob", "longblob"}


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


def normalize_column_name(column: str) -> str:
    normalized = re.sub(r"[^0-9a-zA-Z_]+", "_", str(column).strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_").lower()
    return normalized or "columna"


def prepare_dataframe(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path, low_memory=False)
    df.columns = [normalize_column_name(col) for col in df.columns]
    if "fecha_carga" not in df.columns:
        df["fecha_carga"] = datetime.now(timezone.utc).replace(tzinfo=None)
    return df


def dtype_for_dataframe(df: pd.DataFrame) -> dict:
    dtype = {}
    for column in df.columns:
        if column in STRING_DTYPES:
            dtype[column] = STRING_DTYPES[column]
        elif column in INTEGER_COLUMNS:
            dtype[column] = Integer()
        elif column in DATETIME_COLUMNS:
            dtype[column] = DateTime()
        elif pd.api.types.is_bool_dtype(df[column]):
            dtype[column] = Boolean()
        elif pd.api.types.is_integer_dtype(df[column]):
            dtype[column] = Integer()
        elif pd.api.types.is_float_dtype(df[column]):
            dtype[column] = Float()
        elif pd.api.types.is_object_dtype(df[column]) or pd.api.types.is_string_dtype(df[column]):
            dtype[column] = Text()
    return dtype


def table_exists(engine: Engine, table_name: str) -> bool:
    with engine.begin() as conn:
        return bool(
            conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :table_name
                    """
                ),
                {"table_name": table_name},
            ).scalar()
        )


def indexed_columns_have_valid_types(engine: Engine, table_name: str, index_columns: list[str]) -> bool:
    if not table_exists(engine, table_name):
        return False

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME, DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                """
            ),
            {"table_name": table_name},
        ).fetchall()

    types = {row.COLUMN_NAME: str(row.DATA_TYPE).lower() for row in rows}
    for column in index_columns:
        if column in types and types[column] in TEXT_TYPES:
            return False
    return True


def ensure_staging_schema(engine: Engine, table_name: str, df: pd.DataFrame, dtype: dict) -> None:
    if table_exists(engine, table_name) and not indexed_columns_have_valid_types(engine, table_name, INDEX_COLUMNS):
        print(f"{table_name}: tabla existente con TEXT/BLOB en columnas indexables; se recrea staging.")
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE `{table_name}`"))

    if not table_exists(engine, table_name):
        df.head(0).to_sql(table_name, engine, if_exists="replace", index=False, chunksize=1000, dtype=dtype)


def create_indexes(engine: Engine, table_name: str, columns: list[str]) -> None:
    with engine.begin() as conn:
        column_types = {
            row.COLUMN_NAME: str(row.DATA_TYPE).lower()
            for row in conn.execute(
                text(
                    """
                    SELECT COLUMN_NAME, DATA_TYPE
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = :table_name
                    """
                ),
                {"table_name": table_name},
            ).fetchall()
        }
        for column in INDEX_COLUMNS:
            if column not in columns:
                continue
            if column_types.get(column) in TEXT_TYPES:
                print(f"{table_name}: no se indexa {column} porque es {column_types[column]}.")
                continue
            index_name = f"idx_{table_name}_{column}"
            conn.execute(text(f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table_name}` (`{column}`)"))


def upload_table(engine: Engine, table_name: str, csv_path: Path) -> int:
    df = prepare_dataframe(csv_path)
    dtype = dtype_for_dataframe(df)

    ensure_staging_schema(engine, table_name, df, dtype)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE `{table_name}`"))

    df.to_sql(table_name, engine, if_exists="append", index=False, chunksize=5000, method="multi", dtype=dtype)
    create_indexes(engine, table_name, list(df.columns))
    return len(df)


def main() -> None:
    engine = make_engine()
    print("Conexion a TiDB creada.")
    for table_name, csv_path in TABLES.items():
        rows = upload_table(engine, table_name, csv_path)
        print(f"{table_name}: {rows:,} filas cargadas desde {csv_path.name}")
    print("Carga staging finalizada.")


if __name__ == "__main__":
    main()
