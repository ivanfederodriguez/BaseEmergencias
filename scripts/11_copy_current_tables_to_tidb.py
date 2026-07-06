"""
Copia tablas actuales desde un TiDB origen hacia el TiDB destino.

No modifica historicos, staging ni vistas. Solo reemplaza de forma controlada
las tablas operativas listadas en CURRENT_TABLES dentro del destino.
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
REPORT_PATH = PROJECT_ROOT / "data_intermediate" / "reporte_copia_tablas_actuales.xlsx"

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

PROTECTED_PREFIXES = ("stg_", "vw_hist_", "vw_all_")
CHUNKSIZE = 5000
ZERO_DATE_REPLACEMENTS = {
    "0000-00-00": "1970-01-01",
    "0000-00-00 00:00:00": "1970-01-01 00:00:00",
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


def ssl_connect_args(prefix: str = "") -> dict:
    ssl_ca = env_value(f"{prefix}TIDB_SSL_CA", "TIDB_SSL_CA")
    if not ssl_ca:
        print(f"{prefix}TIDB_SSL_CA no definido; se intentara conectar sin ssl_ca.")
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
        missing_labels = {
            "SOURCE_TIDB_USER": user,
            "SOURCE_TIDB_PASSWORD": password,
            "SOURCE_TIDB_HOST": host,
            "SOURCE_TIDB_PORT": port,
            "SOURCE_TIDB_DATABASE": database,
        }
        connect_args = ssl_connect_args("SOURCE_")
    elif kind == "dest":
        user = env_value("TIDB_USER")
        password = env_value("TIDB_PASSWORD", "TIDB_PASS")
        host = env_value("TIDB_HOST")
        port = env_value("TIDB_PORT", default="4000")
        database = env_value("TIDB_DATABASE", "TIDB_DB")
        missing_labels = {
            "TIDB_USER": user,
            "TIDB_PASSWORD/TIDB_PASS": password,
            "TIDB_HOST": host,
            "TIDB_PORT": port,
            "TIDB_DATABASE/TIDB_DB": database,
        }
        connect_args = ssl_connect_args("")
    else:
        raise ValueError(kind)

    missing = [name for name, value in missing_labels.items() if not value]
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
    with engine.begin() as conn:
        return bool(conn.execute(text("""
            SELECT COUNT(*)
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :table
              AND TABLE_TYPE = 'BASE TABLE'
        """), {"table": table}).scalar())


def table_columns(engine: Engine, table: str) -> pd.DataFrame:
    return query_df(engine, """
        SELECT COLUMN_NAME, COLUMN_TYPE, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :table
        ORDER BY ORDINAL_POSITION
    """, {"table": table})


def row_count(engine: Engine, table: str) -> int:
    with engine.begin() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar())


def show_create_table(engine: Engine, table: str) -> str:
    with engine.begin() as conn:
        row = conn.execute(text(f"SHOW CREATE TABLE `{table}`")).fetchone()
    return row[1]


def sanitize_create_sql(sql: str, table: str) -> str:
    # Source and destination are TiDB/MySQL compatible. Keep the table name
    # quoted and remove any database qualification if SHOW CREATE includes one.
    replacements = [
        f"CREATE TABLE `{table}`",
        f"CREATE TABLE IF NOT EXISTS `{table}`",
    ]
    out = sql
    for marker in replacements:
        if marker in out:
            out = out.replace(marker, f"CREATE TABLE `{table}`", 1)
            break
    return out


def safe_replace_table(dest: Engine, table: str, create_sql: str) -> None:
    if table.startswith(PROTECTED_PREFIXES):
        raise RuntimeError(f"Proteccion activa: no se permite reemplazar {table}")
    if table not in CURRENT_TABLES:
        raise RuntimeError(f"Tabla fuera de lista permitida: {table}")
    with dest.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        conn.execute(text(create_sql))


def insert_chunk(dest: Engine, table: str, chunk: pd.DataFrame) -> int:
    if chunk.empty:
        return 0
    chunk = chunk.astype(object).where(pd.notna(chunk), None)
    chunk = chunk.replace(ZERO_DATE_REPLACEMENTS)
    columns = list(chunk.columns)
    param_names = [f"c{i}" for i in range(len(columns))]
    column_sql = ", ".join(f"`{column}`" for column in columns)
    values_sql = ", ".join(f":{param}" for param in param_names)
    insert_sql = text(f"INSERT INTO `{table}` ({column_sql}) VALUES ({values_sql})")
    records = [
        {param: row[column] for param, column in zip(param_names, columns)}
        for _, row in chunk.iterrows()
    ]
    with dest.begin() as conn:
        conn.execute(insert_sql, records)
    return len(records)


def sanitize_preview(df: pd.DataFrame) -> pd.DataFrame:
    def clean_value(value):
        if isinstance(value, (bytes, bytearray, memoryview)):
            return f"<binary {len(value)} bytes>"
        if value is None or pd.isna(value):
            return None
        text = str(value)
        text = "".join(ch if ch == "\n" or ch == "\t" or ord(ch) >= 32 else " " for ch in text)
        return text[:1000]

    return df.map(clean_value)


def copy_table(source: Engine, dest: Engine, table: str) -> dict:
    if not table_exists(source, table):
        raise RuntimeError(f"No existe en origen: {table}")

    create_sql = sanitize_create_sql(show_create_table(source, table), table)
    safe_replace_table(dest, table, create_sql)

    copied = 0
    for chunk in pd.read_sql_query(f"SELECT * FROM `{table}`", source, chunksize=CHUNKSIZE):
        copied += insert_chunk(dest, table, chunk)

    source_rows = row_count(source, table)
    dest_rows = row_count(dest, table)
    return {
        "tabla": table,
        "filas_origen": source_rows,
        "filas_copiadas": copied,
        "filas_destino": dest_rows,
        "ok": int(source_rows == dest_rows == copied),
    }


def main() -> None:
    source = make_engine("source")
    dest = make_engine("dest")

    source_table_rows = []
    copied_rows = []
    compare_rows = []
    error_rows = []
    preview_frames = []

    for table in CURRENT_TABLES:
        exists = table_exists(source, table)
        columns = table_columns(source, table) if exists else pd.DataFrame()
        source_table_rows.append({
            "tabla": table,
            "existe_origen": int(exists),
            "columnas_origen": len(columns),
            "filas_origen": row_count(source, table) if exists else None,
        })
        if not exists:
            error_rows.append({"tabla": table, "error": "tabla_no_existe_en_origen"})
            continue

        try:
            result = copy_table(source, dest, table)
            copied_rows.append(result)
            compare_rows.append({
                "tabla": table,
                "filas_origen": result["filas_origen"],
                "filas_destino": result["filas_destino"],
                "diferencia": result["filas_destino"] - result["filas_origen"],
            })
            preview = sanitize_preview(query_df(dest, f"SELECT * FROM `{table}` LIMIT 20"))
            preview.insert(0, "tabla", table)
            preview_frames.append(preview)
            print(f"{table}: {result['filas_destino']:,} filas copiadas")
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            error_rows.append({"tabla": table, "error": message[:30000]})
            print(f"{table}: ERROR {type(exc).__name__}: {exc}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(REPORT_PATH, engine="openpyxl") as writer:
        summary = pd.DataFrame([{
            "tablas_requeridas": len(CURRENT_TABLES),
            "tablas_en_origen": sum(row["existe_origen"] for row in source_table_rows),
            "tablas_copiadas_ok": sum(row.get("ok", 0) for row in copied_rows),
            "tablas_con_error": len(error_rows),
        }])
        summary.to_excel(writer, index=False, sheet_name="resumen")
        pd.DataFrame(source_table_rows).to_excel(writer, index=False, sheet_name="tablas_origen")
        pd.DataFrame(copied_rows).to_excel(writer, index=False, sheet_name="tablas_copiadas")
        pd.DataFrame(compare_rows).to_excel(writer, index=False, sheet_name="conteos_origen_destino")
        pd.DataFrame(error_rows).to_excel(writer, index=False, sheet_name="errores")
        if preview_frames:
            pd.concat(preview_frames, ignore_index=True).to_excel(writer, index=False, sheet_name="preview_tablas")
        else:
            pd.DataFrame().to_excel(writer, index=False, sheet_name="preview_tablas")

    print(f"Reporte generado: {REPORT_PATH}")
    if error_rows:
        print(f"Copia finalizada con advertencias/errores en {len(error_rows)} tabla(s). Ver reporte.")


if __name__ == "__main__":
    main()
