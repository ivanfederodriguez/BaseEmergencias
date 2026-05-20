"""
Capa de acceso a datos del dashboard.

Lee la conexión del .env (DATA_SOURCE = 'local' | 'tidb') y expone:
- get_engine(): SQLAlchemy Engine cacheado.
- run_query(sql, **params): pd.DataFrame cacheado.
- fix_coord(s): repara coordenadas guardadas como varchar con el punto perdido.
- helpers: listas para filtros (resoluciones, departamentos, etc).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Cargar .env desde la raíz del proyecto (un nivel arriba de dashboard/)
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _connection_url() -> tuple[str, dict]:
    """Construye la URL SQLAlchemy según DATA_SOURCE."""
    source = os.getenv("DATA_SOURCE", "local").lower()

    if source == "tidb":
        host = os.getenv("TIDB_HOST")
        port = int(os.getenv("TIDB_PORT", "4000"))
        user = os.getenv("TIDB_USER")
        pwd = os.getenv("TIDB_PASS")
        db = os.getenv("TIDB_DB")
        ssl_ca = os.getenv("TIDB_SSL_CA", "/etc/ssl/cert.pem")
        if not all([host, user, pwd, db]):
            raise RuntimeError(
                "DATA_SOURCE=tidb pero faltan variables TIDB_* en .env"
            )
        url = (
            f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}"
            "?charset=utf8mb4"
        )
        connect_args = {"ssl": {"ca": ssl_ca}}
        return url, connect_args

    # local
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    pwd = os.getenv("MYSQL_PASSWORD", "")
    db = os.getenv("MYSQL_DATABASE", "emergencias")
    url = f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"
    return url, {}


@st.cache_resource(show_spinner=False)
def get_engine():
    url, connect_args = _connection_url()
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@st.cache_data(ttl=600, show_spinner=False)
def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Ejecuta una query y devuelve un DataFrame, con caché de 10 min."""
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})


def db_info() -> dict:
    """Devuelve metadatos del origen activo."""
    source = os.getenv("DATA_SOURCE", "local").lower()
    if source == "tidb":
        return {
            "source": "TiDB Cloud",
            "host": os.getenv("TIDB_HOST"),
            "db": os.getenv("TIDB_DB"),
        }
    return {
        "source": "MySQL local",
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "db": os.getenv("MYSQL_DATABASE", "emergencias"),
    }


# ---------- Helpers de dominio ----------


def fix_coord(s) -> float | None:
    """Repara coordenadas guardadas como varchar con punto faltante.

    Ej: '-2769864082' → -27.69864082 ; '-290000000000' → -29.0
    """
    if s is None:
        return None
    s = str(s).strip()
    if s in ("", "0", "0.0", "NULL"):
        return None
    try:
        val = float(s)
    except ValueError:
        return None
    if -180 <= val <= 180 and val != 0:
        return val
    sign = -1 if s.startswith("-") else 1
    digits = s.lstrip("-").replace(".", "")
    if len(digits) < 3:
        return None
    fixed = digits[:2] + "." + digits[2:]
    try:
        out = sign * float(fixed)
    except ValueError:
        return None
    if -180 <= out <= 180:
        return out
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def list_resoluciones() -> pd.DataFrame:
    return run_query(
        "SELECT id_resolucion, nombre_resolucion, numero_resolucion, fec_res "
        "FROM resoluciones ORDER BY fec_res DESC"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def list_departamentos() -> pd.DataFrame:
    return run_query(
        "SELECT DepartamentoId, DepartamentoDesc, ProvinciaId "
        "FROM departamentos ORDER BY DepartamentoDesc"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def list_actividades() -> pd.DataFrame:
    return run_query(
        "SELECT TipoActividadId AS id, TipoActividadDesc AS descripcion "
        "FROM tipoactividad ORDER BY TipoActividadDesc"
    )


@st.cache_data(ttl=3600, show_spinner=False)
def list_rubros() -> pd.DataFrame:
    return run_query("SELECT id_rubro, nombre FROM rubro_tipos ORDER BY id_rubro")


@st.cache_data(ttl=3600, show_spinner=False)
def list_departamentos_ddjj() -> list[str]:
    df = run_query(
        "SELECT DISTINCT departamento FROM ddjj_personas "
        "WHERE departamento <> '' ORDER BY departamento"
    )
    return df["departamento"].tolist()


# ---------- Queries de alto nivel ----------


@st.cache_data(ttl=600, show_spinner=False)
def kpis_generales() -> dict:
    df = run_query(
        """
        SELECT
          (SELECT COUNT(*) FROM productores) AS productores,
          (SELECT COUNT(*) FROM ddjj_personas) AS ddjj,
          (SELECT COUNT(*) FROM resoluciones) AS resoluciones,
          (SELECT COUNT(*) FROM establecimientos) AS establecimientos,
          (SELECT COUNT(*) FROM adremas) AS adremas,
          (SELECT ROUND(AVG(pondf),2) FROM ddjj_personas WHERE pondf>0) AS pondf_promedio
        """
    )
    return df.iloc[0].to_dict()
