"""Listado catastral de Adremas con filtros."""
from __future__ import annotations

import streamlit as st

from utils import list_actividades, run_query

st.set_page_config(page_title="Adremas", layout="wide")
st.title("Adremas (parcelas catastrales)")

with st.sidebar:
    st.header("Filtros")
    q = st.text_input("Adrema o productor contiene", "")
    deps = run_query(
        "SELECT DISTINCT departamento FROM adremas WHERE departamento<>'' "
        "ORDER BY departamento"
    )
    dep_sel = st.multiselect("Departamento", deps["departamento"].tolist())
    sup_min = st.number_input("Superficie mínima (ha)", min_value=0, value=0, step=10)
    limite = st.slider("Filas máximas", 50, 5000, 500, step=50)

conds = ["a.adrema<>''"]
params: dict = {"limite": limite, "sup_min": sup_min}
if q:
    conds.append(
        "(a.adrema LIKE :q OR p.ProductorDenominacion LIKE :q)"
    )
    params["q"] = f"%{q}%"
if dep_sel:
    placeholders = []
    for i, d in enumerate(dep_sel):
        k = f"d{i}"
        placeholders.append(f":{k}")
        params[k] = d
    conds.append(f"a.departamento IN ({','.join(placeholders)})")
conds.append("a.superficie >= :sup_min")
where = "WHERE " + " AND ".join(conds)

df = run_query(
    f"""
    SELECT a.adrema, a.superficie,
           ta.TipoActividadDesc AS actividad,
           tt.descripcion       AS tenencia,
           a.departamento,
           e.nombre_estab, e.paraje_estab,
           p.ProductorDenominacion AS productor,
           p.CUITCUIL,
           a.ddjj AS id_ddjj
    FROM adremas a
    LEFT JOIN tipoactividad ta ON ta.TipoActividadId = a.actividad
    LEFT JOIN tipotenencia tt  ON tt.id              = a.tenencia
    LEFT JOIN establecimientos e ON e.id_establecimiento = a.id_establecimiento
    LEFT JOIN ddjj_personas dj ON dj.id_ddjj = a.ddjj
    LEFT JOIN productores   p  ON p.ProductorId = dj.id_productor
    {where}
    ORDER BY a.superficie DESC
    LIMIT :limite
    """,
    params,
)

st.caption(
    f"{len(df):,} adremas · superficie total: "
    f"{int(df['superficie'].fillna(0).sum()):,} ha"
)
st.dataframe(df, use_container_width=True, hide_index=True, height=620)

st.download_button(
    "Descargar CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="adremas.csv",
    mime="text/csv",
)
