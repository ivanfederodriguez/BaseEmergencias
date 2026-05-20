"""Análisis agregado: cultivos, ganadería, mejoras."""
from __future__ import annotations

import plotly.express as px
import streamlit as st

from utils import run_query

st.set_page_config(page_title="Análisis", layout="wide")
st.title("Análisis agregado")

# Filtro por resolución
res = run_query(
    "SELECT id_resolucion, numero_resolucion, nombre_resolucion "
    "FROM resoluciones ORDER BY fec_res DESC"
)
opciones = ["(todas)"] + [
    f"{r.id_resolucion} — {r.numero_resolucion}" for r in res.itertuples()
]
sel = st.selectbox("Resolución", opciones)
id_res = None
if sel != "(todas)":
    id_res = int(sel.split(" — ", 1)[0])

filtro_res = ""
params: dict = {}
if id_res is not None:
    filtro_res = "AND dj.id_resolucion = :id_res"
    params["id_res"] = id_res

# ---------- Cultivos: hectáreas afectadas vs sembradas ----------
st.subheader("Cultivos — superficie sembrada vs afectada")
df = run_query(
    f"""
    SELECT ct.CultivoTipoDesc AS tipo_cultivo,
           SUM(a.sup_sembrada) AS sembrada,
           SUM(a.sup_afectada) AS afectada
    FROM agricultura a
    LEFT JOIN cultivostipo ct ON ct.id = a.tipo_cultivo
    JOIN ddjj_personas dj ON dj.id_ddjj = a.ddjj
    WHERE 1=1 {filtro_res}
    GROUP BY ct.CultivoTipoDesc
    HAVING sembrada > 0
    ORDER BY afectada DESC
    """,
    params,
)
if not df.empty:
    df_m = df.melt(id_vars="tipo_cultivo", var_name="medida", value_name="hectareas")
    fig = px.bar(df_m, x="tipo_cultivo", y="hectareas", color="medida", barmode="group")
    fig.update_layout(height=420, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

# ---------- Ganadería: cabezas vs mortandad ----------
st.subheader("Bovinos — cabezas declaradas vs mortandad")
df = run_query(
    f"""
    SELECT
      'Vacas' AS categoria, SUM(b.cantivaca) AS cabezas, SUM(b.mortavaca) AS perdidas
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    UNION ALL SELECT 'Vaquillonas', SUM(cantivaqui), SUM(mortavaqui)
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    UNION ALL SELECT 'Terneros', SUM(cantiterne), SUM(mortaterne)
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    UNION ALL SELECT 'Novillos', SUM(cantinovi), SUM(mortanovi)
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    UNION ALL SELECT 'Novillitos', SUM(cantinovilli), SUM(mortanovilli)
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    UNION ALL SELECT 'Toros', SUM(cantitoro), SUM(mortatoro)
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    UNION ALL SELECT 'Búfalos', SUM(cantibufa), SUM(mortabufa)
      FROM bovinos b JOIN ddjj_personas dj ON dj.id_ddjj=b.idddjj WHERE 1=1 {filtro_res}
    """,
    params,
)
if not df.empty:
    df_m = df.melt(id_vars="categoria", var_name="medida", value_name="cantidad")
    fig = px.bar(df_m, x="categoria", y="cantidad", color="medida", barmode="group")
    fig.update_layout(height=380, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

# ---------- Top mejoras perdidas ----------
st.subheader("Top tipos de mejora declaradas")
df = run_query(
    f"""
    SELECT pm.mejora, COUNT(*) AS declaraciones,
           ROUND(AVG(pm.vestimado),0) AS valor_prom,
           ROUND(AVG(pm.pesper),1) AS pct_perdida_prom
    FROM perdidas_mejoras pm
    JOIN ddjj_personas dj ON dj.id_ddjj = pm.idddjj
    WHERE 1=1 {filtro_res}
    GROUP BY pm.mejora
    ORDER BY declaraciones DESC
    LIMIT 15
    """,
    params,
)
if not df.empty:
    fig = px.bar(df, x="declaraciones", y="mejora", orientation="h",
                 hover_data=["valor_prom", "pct_perdida_prom"])
    fig.update_layout(height=460, yaxis=dict(autorange="reversed"),
                      margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, hide_index=True, use_container_width=True)

# ---------- Tipo jurídico de productores ----------
st.subheader("Productores por tipo jurídico y actividad")
df = run_query(
    """
    SELECT COALESCE(tj.TipoJuridicoDesc,'(s/d)') AS tipo_juridico,
           COALESCE(ta.TipoActividadDesc,'(s/d)') AS actividad,
           COUNT(*) AS n
    FROM productores p
    LEFT JOIN tipojuridico   tj ON tj.TipoJuridicoId   = p.TipoJuridicoId
    LEFT JOIN tipoactividad  ta ON ta.TipoActividadId  = p.EsPrincipalActividadEconomica
    GROUP BY tipo_juridico, actividad
    ORDER BY n DESC
    """
)
if not df.empty:
    fig = px.treemap(df, path=["tipo_juridico", "actividad"], values="n")
    fig.update_layout(height=500, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
