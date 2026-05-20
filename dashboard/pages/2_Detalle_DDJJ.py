"""Detalle completo de una DDJJ (productor + rubros + adjuntos)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import run_query

st.set_page_config(page_title="Detalle DDJJ", layout="wide")
st.title("Detalle de una DDJJ")

ddjj_id = st.number_input(
    "Número de DDJJ (id_ddjj)", min_value=1, step=1, value=59
)

cab = run_query(
    """
    SELECT dj.id_ddjj, dj.fecha, dj.pondf, dj.cargado, dj.estado,
           p.ProductorDenominacion AS productor, p.CUITCUIL, p.DocumentoNro,
           r.nombre_resolucion, r.numero_resolucion, r.fec_res,
           dj.provincia, dj.departamento, dj.localidad, dj.paraje
    FROM ddjj_personas dj
    LEFT JOIN productores  p ON p.ProductorId   = dj.id_productor
    LEFT JOIN resoluciones r ON r.id_resolucion = dj.id_resolucion
    WHERE dj.id_ddjj = :id
    """,
    {"id": int(ddjj_id)},
)

if cab.empty:
    st.warning("No existe esa DDJJ.")
    st.stop()

row = cab.iloc[0]
c1, c2, c3 = st.columns([2, 2, 1])
c1.markdown(f"### {row['productor'] or 's/d'}")
c1.write(
    f"**CUIT:** {row['CUITCUIL'] or '—'}  ·  **Doc:** {row['DocumentoNro'] or '—'}"
)
c2.write(
    f"**Resolución:** {row['nombre_resolucion'] or '—'}  \n"
    f"**Número:** {row['numero_resolucion'] or '—'}  \n"
    f"**Fecha res.:** {row['fec_res']}"
)
c3.metric("% daño (pondf)", f"{(row['pondf'] or 0):.2f}%")

st.write(
    f"**Ubicación declarada:** {row['provincia']} · {row['departamento']} · "
    f"{row['localidad']} · {row['paraje']}  ·  **Fecha DDJJ:** {row['fecha']}"
)
st.divider()

# ---- Ponderaciones por rubro ----
st.subheader("Ponderaciones por rubro")
pond = run_query(
    """
    SELECT rt.nombre AS rubro, p.estimados, p.obtenidos, p.perdidas_ponde AS perdida_pct
    FROM ponderaciones_ddjj p
    JOIN rubro_tipos rt ON rt.id_rubro = p.rubro
    WHERE p.id_ddjj = :id
    ORDER BY p.rubro
    """,
    {"id": int(ddjj_id)},
)
st.dataframe(pond, use_container_width=True, hide_index=True)

# ---- Tabs por rubro ----
t_ag, t_gan, t_for, t_otr, t_adj = st.tabs(
    ["Agricultura", "Ganadería", "Forestal", "Mejoras / Invernaculos", "Adremas / Adjuntos"]
)

with t_ag:
    df = run_query(
        """
        SELECT a.id_agricultura, ct.CultivoTipoDesc AS tipo,
               c.cultivodesc AS cultivo, a.sup_sembrada, a.sup_afectada,
               a.prod_estimada, a.prod_obtenida, a.estado, a.porcentaje
        FROM agricultura a
        LEFT JOIN cultivostipo ct ON ct.id = a.tipo_cultivo
        LEFT JOIN cultivos      c ON c.id  = a.id_cultivo
        WHERE a.ddjj = :id
        """,
        {"id": int(ddjj_id)},
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

with t_gan:
    bv = run_query(
        """SELECT cantivaca, cantivaqui, cantiterne, cantinovi, cantinovilli,
                  cantitoro, cantibufa, prodespe, prodobte,
                  carnestimada, carneobtenida, carneperdida
           FROM bovinos WHERE idddjj=:id""",
        {"id": int(ddjj_id)},
    )
    ov = run_query(
        "SELECT canticabe, mortacabe, prodcor, corobte, prodlana, lanaobte, "
        "perdilana FROM ovinos WHERE idddjj=:id",
        {"id": int(ddjj_id)},
    )
    po = run_query(
        "SELECT canticabe, mortacabe, prodcor, corobte FROM porcinos "
        "WHERE idddjj=:id",
        {"id": int(ddjj_id)},
    )
    av = run_query(
        "SELECT existencia, perdida, prodnor, prodobte FROM avicultura "
        "WHERE idddjj=:id",
        {"id": int(ddjj_id)},
    )
    ap = run_query(
        "SELECT cantcol, canafec, prodnormiel, prodobtemiel, mielperdida "
        "FROM apicultura WHERE idddjj=:id",
        {"id": int(ddjj_id)},
    )
    st.write("**Bovinos**"); st.dataframe(bv, hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.write("**Ovinos**"); st.dataframe(ov, hide_index=True, use_container_width=True)
        st.write("**Aves**"); st.dataframe(av, hide_index=True, use_container_width=True)
    with c2:
        st.write("**Porcinos**"); st.dataframe(po, hide_index=True, use_container_width=True)
        st.write("**Colmenas**"); st.dataframe(ap, hide_index=True, use_container_width=True)

with t_for:
    df = run_query(
        """SELECT supuso, supafe, superdida, prodmaes, prodmaob,
                  madestimada, madeperdida, prodposes, posteperdida,
                  prodreses, resiperdida
           FROM forestacion WHERE idddjj=:id""",
        {"id": int(ddjj_id)},
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

with t_otr:
    mej = run_query(
        "SELECT mejora, vestimado, incidencia, pesesp, pesper "
        "FROM perdidas_mejoras WHERE idddjj=:id",
        {"id": int(ddjj_id)},
    )
    st.write("**Pérdidas en mejoras**")
    st.dataframe(mej, use_container_width=True, hide_index=True)

    inv = run_query(
        "SELECT cobertura_plasticas, estructuras, supsemb, supafect, "
        "coberplastiperdi, danoplastiperdi FROM perdidas_invernaculos "
        "WHERE ddjj=:id",
        {"id": int(ddjj_id)},
    )
    st.write("**Invernáculos**")
    st.dataframe(inv, use_container_width=True, hide_index=True)

    plu = run_query(
        "SELECT cobertura_plantas, coberperdi, dano_planta, danoperdi "
        "FROM perdidas_plurianuales WHERE ddjj=:id",
        {"id": int(ddjj_id)},
    )
    st.write("**Cultivos plurianuales**")
    st.dataframe(plu, use_container_width=True, hide_index=True)

with t_adj:
    adr = run_query(
        """
        SELECT a.adrema, a.superficie, ta.TipoActividadDesc AS actividad,
               tt.descripcion AS tenencia, a.departamento,
               e.nombre_estab, e.paraje_estab
        FROM adremas a
        LEFT JOIN tipoactividad ta ON ta.TipoActividadId = a.actividad
        LEFT JOIN tipotenencia  tt ON tt.id              = a.tenencia
        LEFT JOIN establecimientos e ON e.id_establecimiento = a.id_establecimiento
        WHERE a.ddjj = :id
        """,
        {"id": int(ddjj_id)},
    )
    st.write("**Adremas / parcelas**")
    st.dataframe(adr, use_container_width=True, hide_index=True)

    docs = run_query(
        """
        SELECT codigo, documentacion, marcar
        FROM documentacion WHERE idddjj=:id ORDER BY codigo
        """,
        {"id": int(ddjj_id)},
    )
    st.write(f"**Documentación adjunta** — {len(docs)} ítems")
    st.dataframe(docs, use_container_width=True, hide_index=True)

    fotos = run_query(
        "SELECT id, file FROM fotos WHERE iddjj=:id", {"id": int(ddjj_id)}
    )
    st.write(f"**Fotos** — {len(fotos)} archivo(s)")
    st.dataframe(fotos, use_container_width=True, hide_index=True)
