"""Mapa de establecimientos georreferenciados."""
from __future__ import annotations

import pandas as pd
import pydeck as pdk
import streamlit as st

from utils import fix_coord, run_query

st.set_page_config(page_title="Mapa", layout="wide")
st.title("Mapa de establecimientos")

with st.sidebar:
    st.header("Filtros del mapa")
    deps = run_query(
        "SELECT DISTINCT departamento_estab FROM establecimientos "
        "WHERE departamento_estab<>'' ORDER BY departamento_estab"
    )
    dep_sel = st.multiselect("Departamento", deps["departamento_estab"].tolist())
    color_por = st.selectbox(
        "Colorear por",
        ["pondf (% daño)", "actividad principal"],
    )

conds = ["e.latitud NOT IN ('','0') AND e.longitud NOT IN ('','0')"]
params: dict = {}
if dep_sel:
    placeholders = []
    for i, d in enumerate(dep_sel):
        k = f"d{i}"
        placeholders.append(f":{k}")
        params[k] = d
    conds.append(f"e.departamento_estab IN ({','.join(placeholders)})")
where = " AND ".join(conds)

df = run_query(
    f"""
    SELECT e.id_establecimiento, e.nombre_estab, e.departamento_estab,
           e.latitud, e.longitud,
           p.ProductorDenominacion AS productor, p.CUITCUIL,
           dj.id_ddjj, dj.pondf,
           ta.TipoActividadDesc AS actividad
    FROM establecimientos e
    LEFT JOIN ddjj_personas dj ON dj.id_ddjj = e.ddjj
    LEFT JOIN productores   p  ON p.ProductorId = dj.id_productor
    LEFT JOIN tipoactividad ta ON ta.TipoActividadId = p.EsPrincipalActividadEconomica
    WHERE {where}
    """,
    params,
)

df["lat"] = df["latitud"].apply(fix_coord)
df["lng"] = df["longitud"].apply(fix_coord)
df = df.dropna(subset=["lat", "lng"])
# Filtrar coords claramente fuera de Argentina/Corrientes
df = df[(df["lat"].between(-55, -21)) & (df["lng"].between(-74, -53))]

st.caption(f"{len(df):,} establecimientos con coordenadas válidas.")

if df.empty:
    st.info("No hay coordenadas válidas para los filtros seleccionados.")
    st.stop()

# Color
if color_por.startswith("pondf"):
    df["pondf_num"] = pd.to_numeric(df["pondf"], errors="coerce").fillna(0)
    # rojo cuanto más alto el daño
    df["r"] = (df["pondf_num"].clip(0, 100) / 100 * 255).astype(int)
    df["g"] = 80
    df["b"] = (255 - df["r"]).clip(0, 255)
else:
    palette = {
        "AG - AGRICULTURA": (76, 175, 80),
        "GA - GANADERIA": (255, 152, 0),
        "BM - BOSQ./MONTES": (33, 150, 243),
    }
    def color(a):
        return palette.get(a, (158, 158, 158))
    df[["r", "g", "b"]] = df["actividad"].apply(lambda a: pd.Series(color(a)))

df["radius"] = 400

view = pdk.ViewState(
    latitude=float(df["lat"].mean()),
    longitude=float(df["lng"].mean()),
    zoom=6.5,
    pitch=0,
)
layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position="[lng, lat]",
    get_radius="radius",
    get_fill_color="[r, g, b, 180]",
    pickable=True,
    radius_min_pixels=3,
    radius_max_pixels=20,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=view,
        map_style="light",
        tooltip={
            "html": (
                "<b>{nombre_estab}</b><br/>"
                "Productor: {productor}<br/>"
                "DDJJ: {id_ddjj} — daño: {pondf}%<br/>"
                "Actividad: {actividad}<br/>"
                "Depto: {departamento_estab}"
            )
        },
    )
)

st.dataframe(
    df[
        ["id_establecimiento", "nombre_estab", "productor", "departamento_estab",
         "actividad", "pondf", "lat", "lng"]
    ],
    use_container_width=True,
    hide_index=True,
)
