"""
Dashboard de Emergencias Agropecuarias — Home

Ejecutar:
    cd dashboard && streamlit run app.py
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import (
    db_info,
    kpis_generales,
    list_resoluciones,
    run_query,
)

st.set_page_config(
    page_title="Emergencias Agropecuarias",
    page_icon="AG",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Encabezado ----------
info = db_info()
st.title("Sistema de Emergencias Agropecuarias")
st.caption(f"Conectado a: **{info['source']}** · `{info['host']}` · base `{info['db']}`")

# ---------- KPIs ----------
kpis = kpis_generales()
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Productores", f"{int(kpis['productores']):,}")
c2.metric("DDJJ", f"{int(kpis['ddjj']):,}")
c3.metric("Resoluciones", f"{int(kpis['resoluciones']):,}")
c4.metric("Establecimientos", f"{int(kpis['establecimientos']):,}")
c5.metric("Adremas", f"{int(kpis['adremas']):,}")
c6.metric("% daño promedio", f"{kpis['pondf_promedio'] or 0:.1f}%")

st.divider()

# ---------- Filtros globales ----------
with st.sidebar:
    st.header("Filtros")
    resoluciones = list_resoluciones()
    res_options = ["(todas)"] + [
        f"{row.id_resolucion} — {row.nombre_resolucion}" for row in resoluciones.itertuples()
    ]
    res_sel = st.selectbox("Resolución", res_options)
    res_id = None
    if res_sel != "(todas)":
        res_id = int(res_sel.split(" — ", 1)[0])

    deps_df = run_query(
        "SELECT DISTINCT departamento FROM ddjj_personas "
        "WHERE departamento <> '' ORDER BY departamento"
    )
    dep_sel = st.multiselect("Departamento", deps_df["departamento"].tolist())

    pondf_min, pondf_max = st.slider(
        "% de daño (pondf)", min_value=0, max_value=100, value=(0, 100), step=5
    )

    fechas_df = run_query(
        "SELECT MIN(fecha) AS mn, MAX(fecha) AS mx FROM ddjj_personas WHERE fecha > '2000-01-01'"
    )
    fmin = pd.to_datetime(fechas_df.iloc[0]["mn"]).date()
    fmax = pd.to_datetime(fechas_df.iloc[0]["mx"]).date()
    rango = st.date_input("Rango de fechas", (fmin, fmax), min_value=fmin, max_value=fmax)
    if isinstance(rango, tuple) and len(rango) == 2:
        f_desde, f_hasta = rango
    else:
        f_desde, f_hasta = fmin, fmax

    st.session_state["filtros"] = {
        "id_resolucion": res_id,
        "departamentos": dep_sel,
        "pondf_min": pondf_min,
        "pondf_max": pondf_max,
        "f_desde": str(f_desde),
        "f_hasta": str(f_hasta),
    }

# WHERE dinámico para reutilizar
def where_filtros(prefix="dj.") -> tuple[str, dict]:
    f = st.session_state.get("filtros", {})
    conds = [f"{prefix}fecha BETWEEN :f_desde AND :f_hasta"]
    params = {"f_desde": f["f_desde"], "f_hasta": f["f_hasta"]}
    if f.get("id_resolucion"):
        conds.append(f"{prefix}id_resolucion = :id_res")
        params["id_res"] = f["id_resolucion"]
    if f.get("departamentos"):
        placeholders = []
        for i, d in enumerate(f["departamentos"]):
            k = f"dep{i}"
            placeholders.append(f":{k}")
            params[k] = d
        conds.append(f"{prefix}departamento IN ({','.join(placeholders)})")
    conds.append(f"{prefix}pondf BETWEEN :p_min AND :p_max")
    params["p_min"] = f["pondf_min"]
    params["p_max"] = f["pondf_max"]
    return " AND ".join(conds), params


where_sql, params = where_filtros()

# ---------- DDJJ por Resolución ----------
st.subheader("DDJJ por Resolución")
df_res = run_query(
    f"""
    SELECT r.numero_resolucion AS resolucion, r.nombre_resolucion AS nombre,
           COUNT(*) AS ddjj
    FROM ddjj_personas dj
    JOIN resoluciones r ON r.id_resolucion = dj.id_resolucion
    WHERE {where_sql}
    GROUP BY r.numero_resolucion, r.nombre_resolucion
    ORDER BY ddjj DESC
    """,
    params,
)
if not df_res.empty:
    fig = px.bar(df_res, x="resolucion", y="ddjj", hover_data=["nombre"],
                 labels={"resolucion": "Resolución", "ddjj": "DDJJ"})
    fig.update_layout(height=380, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sin datos para los filtros seleccionados.")

# ---------- DDJJ por Departamento (top 15) ----------
left, right = st.columns(2)
with left:
    st.subheader("Top 15 Departamentos")
    df_dep = run_query(
        f"""
        SELECT dj.departamento, COUNT(*) AS ddjj,
               ROUND(AVG(dj.pondf),1) AS pondf_prom
        FROM ddjj_personas dj
        WHERE {where_sql} AND dj.departamento<>''
        GROUP BY dj.departamento
        ORDER BY ddjj DESC
        LIMIT 15
        """,
        params,
    )
    if not df_dep.empty:
        fig = px.bar(df_dep, x="ddjj", y="departamento", orientation="h",
                     hover_data=["pondf_prom"],
                     labels={"ddjj": "DDJJ", "departamento": "", "pondf_prom": "% prom."})
        fig.update_layout(height=460, yaxis=dict(autorange="reversed"),
                          margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ---------- Distribución de % daño ----------
with right:
    st.subheader("Distribución de % de daño")
    df_p = run_query(
        f"""
        SELECT dj.pondf
        FROM ddjj_personas dj
        WHERE {where_sql} AND dj.pondf > 0
        """,
        params,
    )
    if not df_p.empty:
        fig = px.histogram(df_p, x="pondf", nbins=20,
                           labels={"pondf": "% de daño"})
        fig.update_layout(height=460, margin=dict(t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ---------- DDJJ por mes ----------
st.subheader("Evolución mensual de DDJJ")
df_t = run_query(
    f"""
    SELECT DATE_FORMAT(dj.fecha,'%Y-%m') AS mes, COUNT(*) AS ddjj,
           ROUND(AVG(dj.pondf),1) AS pondf_prom
    FROM ddjj_personas dj
    WHERE {where_sql}
    GROUP BY mes
    ORDER BY mes
    """,
    params,
)
if not df_t.empty:
    fig = px.line(df_t, x="mes", y="ddjj", markers=True,
                  hover_data=["pondf_prom"])
    fig.update_layout(height=360, margin=dict(t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(
    "Usá el menú lateral para navegar entre: Productores · Detalle DDJJ · "
    "Adremas · Mapa · Análisis."
)
