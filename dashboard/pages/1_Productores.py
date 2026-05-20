"""Listado y búsqueda de productores."""
from __future__ import annotations

import streamlit as st

from utils import list_actividades, run_query

st.set_page_config(page_title="Productores", layout="wide")
st.title("Productores")

with st.sidebar:
    st.header("Búsqueda")
    q = st.text_input("Nombre / CUIT / Documento", "")
    actividades = list_actividades()
    act_sel = st.multiselect(
        "Actividad principal",
        actividades["descripcion"].tolist(),
    )
    limite = st.slider("Filas máximas", 50, 2000, 200, step=50)

conds = []
params: dict = {"limite": limite}
if q:
    conds.append(
        "(p.ProductorDenominacion LIKE :q OR p.CUITCUIL LIKE :q "
        "OR p.DocumentoNro LIKE :q)"
    )
    params["q"] = f"%{q}%"
if act_sel:
    placeholders = []
    for i, a in enumerate(act_sel):
        k = f"a{i}"
        placeholders.append(f":{k}")
        params[k] = a
    conds.append(f"ta.TipoActividadDesc IN ({','.join(placeholders)})")

where = ("WHERE " + " AND ".join(conds)) if conds else ""

sql = f"""
SELECT
    p.ProductorId         AS id,
    p.ProductorDenominacion AS productor,
    p.CUITCUIL            AS cuit,
    td.TipoDocumentoDescripcion AS tipo_doc,
    p.DocumentoNro        AS documento,
    p.Sexo                AS sexo,
    ta.TipoActividadDesc  AS actividad,
    tj.TipoJuridicoDesc   AS tipo_juridico,
    pr.ProvinciaDesc      AS provincia,
    dep.DepartamentoDesc  AS departamento,
    loc.LocalidadDesc     AS localidad,
    p.renspa              AS renspa,
    (SELECT COUNT(*) FROM ddjj_personas dj WHERE dj.id_productor=p.ProductorId) AS ddjj
FROM productores p
LEFT JOIN tipodocumento td  ON td.TipoDocumentoId = p.TipoDocumentoId
LEFT JOIN tipoactividad ta  ON ta.TipoActividadId = p.EsPrincipalActividadEconomica
LEFT JOIN tipojuridico tj   ON tj.TipoJuridicoId = p.TipoJuridicoId
LEFT JOIN domicilios d      ON d.DomicilioId = p.DomicilioId
LEFT JOIN provincias pr     ON pr.ProvinciaId = d.ProvinciaId
LEFT JOIN departamentos dep ON dep.DepartamentoId = d.DepartamentoId
LEFT JOIN localidades loc   ON loc.LocalidadId = d.LocalidadId
{where}
ORDER BY p.ProductorDenominacion
LIMIT :limite
"""

df = run_query(sql, params)
st.caption(f"Mostrando **{len(df)}** productores (límite {limite}).")
st.dataframe(df, use_container_width=True, hide_index=True, height=620)

if not df.empty:
    sel = st.selectbox(
        "Ver DDJJ de un productor",
        [""] + df["id"].astype(str).tolist(),
        format_func=lambda x: (
            "" if not x
            else f"#{x} — {df.set_index('id').loc[int(x), 'productor']}"
        ),
    )
    if sel:
        pid = int(sel)
        st.subheader("DDJJ de este productor")
        ddjj = run_query(
            """
            SELECT dj.id_ddjj, dj.fecha, r.numero_resolucion, dj.pondf,
                   dj.departamento, dj.localidad, dj.cargado, dj.estado
            FROM ddjj_personas dj
            LEFT JOIN resoluciones r ON r.id_resolucion = dj.id_resolucion
            WHERE dj.id_productor = :pid
            ORDER BY dj.fecha DESC
            """,
            {"pid": pid},
        )
        st.dataframe(ddjj, use_container_width=True, hide_index=True)
        st.info(
            "Copiar un `id_ddjj` y pegarlo en la página **Detalle DDJJ** "
            "para ver el detalle completo."
        )
