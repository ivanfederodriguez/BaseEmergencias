"""
Transforma Excel historicos de emergencias agropecuarias a una tabla comun.

No modifica archivos originales ni carga datos a TiDB. Usa config/file_formats.csv
para decidir que parser aplicar a cada archivo.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = PROJECT_ROOT / "data_raw"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "file_formats.csv"
DEFAULT_EVENT_MAPPING = PROJECT_ROOT / "config" / "event_mapping.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data_clean" / "emergencias_productores_raw_clean.csv"

OUTPUT_COLUMNS = [
    "evento_id",
    "periodo",
    "anio",
    "dto",
    "fecha_origen",
    "source_file",
    "source_sheet",
    "dataset_role",
    "relation_type",
    "iddj",
    "codigo",
    "solicitud_id",
    "productor_nombre",
    "documento_nro",
    "cuit_cuil",
    "departamento",
    "localidad",
    "paraje",
    "seccion",
    "renspa",
    "actividad",
    "cultivo",
    "especie",
    "categoria",
    "superficie_total",
    "superficie_agricola_uso",
    "superficie_agricola_afectada",
    "superficie_ganadera_uso",
    "superficie_ganadera_afectada",
    "existencias",
    "mortandad",
    "produccion_estimada",
    "produccion_obtenida",
    "porcentaje_afectacion_ganadera",
    "superficie_plantada_sembrada",
    "superficie_afectada",
    "porcentaje_afectacion",
    "observaciones",
    "flag_anio_corregido",
    "flag_anio_fuera_rango",
    "flag_superficie_negativa",
    "flag_agricola_afectada_mayor_uso",
    "flag_ganadera_afectada_mayor_uso",
    "flag_mortandad_mayor_existencias",
    "flag_superficie_total_menor_afectadas",
    "flag_revision_manual",
    "severidad_maxima",
]


def clean_text(value: object) -> str | pd.NA:
    if pd.isna(value):
        return pd.NA
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "s/d", "sd", "sin dato"}:
        return pd.NA
    text = re.sub(r"\s+", " ", text)
    return text.upper()


def clean_numeric(value: object) -> float | pd.NA:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "s/d", "sd", "-"}:
        return pd.NA

    text = re.sub(r"[^0-9,\.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return pd.NA

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return pd.NA


def extract_anio(value: object) -> int | pd.NA:
    if pd.isna(value):
        return pd.NA
    match = re.search(r"(19|20)\d{2}", str(value))
    return int(match.group(0)) if match else pd.NA


def extract_dto(value: object) -> str | pd.NA:
    if pd.isna(value):
        return pd.NA
    text = str(value)
    text = re.sub(r"\b(19|20)\d{2}\b", " ", text)
    matches = re.findall(r"\d{1,5}(?:[-/]\d{1,5})*", text)
    return matches[0] if matches else pd.NA


def normalize_column_name(column: object) -> str:
    text = unicodedata.normalize("NFKD", str(column))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.upper().strip()
    text = re.sub(r"[^A-Z0-9]+", "_", text)
    return text.strip("_")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_column_name(col) for col in df.columns]
    return df


def first_existing(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for candidate in candidates:
        if candidate in df.columns:
            return df[candidate]
    return pd.Series([pd.NA] * len(df), index=df.index)


def build_periodo(anio: pd.Series, dto: pd.Series) -> pd.Series:
    anio_text = anio.astype("string").str.replace(r"\.0$", "", regex=True)
    dto_text = dto.astype("string")
    periodo = anio_text.fillna("") + np.where(dto_text.notna(), "-" + dto_text.fillna(""), "")
    return periodo.replace("", pd.NA)


def empty_output_frame(length: int) -> pd.DataFrame:
    return pd.DataFrame({column: pd.Series([pd.NA] * length) for column in OUTPUT_COLUMNS})


def finalize_frame(df: pd.DataFrame, source_file: str, source_sheet: str) -> pd.DataFrame:
    out = df.reindex(columns=OUTPUT_COLUMNS).copy()
    out["source_file"] = source_file
    out["source_sheet"] = source_sheet

    text_columns = [
        "periodo",
        "dto",
        "iddj",
        "codigo",
        "solicitud_id",
        "productor_nombre",
        "documento_nro",
        "cuit_cuil",
        "departamento",
        "localidad",
        "paraje",
        "seccion",
        "renspa",
        "actividad",
        "cultivo",
        "especie",
        "categoria",
        "observaciones",
    ]
    numeric_columns = [
        "superficie_total",
        "superficie_agricola_uso",
        "superficie_agricola_afectada",
        "superficie_ganadera_uso",
        "superficie_ganadera_afectada",
        "existencias",
        "mortandad",
        "produccion_estimada",
        "produccion_obtenida",
        "porcentaje_afectacion_ganadera",
        "superficie_plantada_sembrada",
        "superficie_afectada",
        "porcentaje_afectacion",
    ]

    for column in text_columns:
        out[column] = out[column].map(clean_text)
    for column in numeric_columns:
        out[column] = out[column].map(clean_numeric)

    out["anio"] = out["anio"].map(extract_anio)
    out = out.dropna(how="all", subset=[c for c in OUTPUT_COLUMNS if c not in {"source_file", "source_sheet"}])
    return out[OUTPUT_COLUMNS]


def read_sheet(path: Path, sheet_name: str | int = 0) -> pd.DataFrame:
    return normalize_columns(pd.read_excel(path, sheet_name=sheet_name))


def parse_formato_1998(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    decreto = first_existing(raw, ["ANO_DECRETO", "AÑO_DECRETO", "ANO_DTO", "AÑO_DTO"])
    out["anio"] = decreto.map(extract_anio)
    out["dto"] = decreto.map(extract_dto)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["CODIGO", "IDDJ"])
    out["iddj"] = first_existing(raw, ["IDDJ", "CODIGO"])
    out["documento_nro"] = first_existing(raw, ["DNI", "DOC_NRO", "DOCUMENTO_NRO"])
    out["cuit_cuil"] = first_existing(raw, ["CUIT", "CUITCUIL", "CUIT_CUIL"])
    out["productor_nombre"] = first_existing(raw, ["APELLIDO_Y_NOMBRE", "AYN", "PRODUCTORDENOMINACION"])
    out["localidad"] = first_existing(raw, ["LOCALIZACION", "LOCALIDAD", "LOCALIDADDESC"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["departamento"] = first_existing(raw, ["DEPARTAMENTO", "DEPARTAMENTODESC"])
    out["actividad"] = first_existing(raw, ["ACTIVIDAD"])
    if out["actividad"].isna().all() and "CULTIVO" in raw.columns:
        out["actividad"] = "AGRICULTURA_FORESTAL"
    out["cultivo"] = first_existing(raw, ["CULTIVO", "CULTIVODESC", "TIPO_CULTIVO"])
    out["especie"] = first_existing(raw, ["CULTIVO", "ESPECIE", "CULTIVODESC", "TIPO_CULTIVO"])
    out["superficie_total"] = first_existing(raw, ["SUPTOT", "SUPERFICIE_TOTAL"])
    out["superficie_ganadera_uso"] = first_existing(raw, ["SUPGAN", "SUP_EN_USO_GAN"])
    out["superficie_ganadera_afectada"] = first_existing(raw, ["SUPGANAFECT", "SUP_AFECTADA_TOTAL_GAN"])
    out["existencias"] = first_existing(raw, ["N_CABEZAS", "TOTAL_CABEZAS", "EXISTENC"])
    out["superficie_agricola_uso"] = first_existing(raw, ["SUP_AG", "SUPAG", "SUPERFICIE_EN_USO_AGR", "SUP_PLANT_SEMB"])
    out["superficie_agricola_afectada"] = first_existing(raw, ["SUPAFECT", "SUP_AFECT", "SUPERFICIE_AFECTADA_AGR", "SUP_AFEC"])
    out["superficie_plantada_sembrada"] = first_existing(raw, ["SUP_PLANT_SEMB"])
    out["superficie_afectada"] = first_existing(raw, ["SUP_AFEC"])
    out["porcentaje_afectacion"] = first_existing(raw, ["PORC_CALC", "PORC_AFEC"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


def parse_formato_juradas(path: Path) -> pd.DataFrame:
    sheet_name = "JURADAS"
    raw = read_sheet(path, sheet_name=sheet_name)
    out = empty_output_frame(len(raw))
    file_period = path.stem
    out["anio"] = extract_anio(file_period)
    out["dto"] = extract_dto(file_period)
    out["fecha_origen"] = first_existing(raw, ["FECHA", "FECHA_CARGA"])
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["IDDJ", "CODIGO"])
    out["iddj"] = first_existing(raw, ["IDDJ", "CODIGO"])
    out["documento_nro"] = first_existing(raw, ["DOC_NRO", "DNI", "DOCUMENTO_NRO"])
    out["productor_nombre"] = first_existing(raw, ["AYN", "APELLIDO_Y_NOMBRE", "PRODUCTORDENOMINACION"])
    out["paraje"] = first_existing(raw, ["OTRA_LOC_PARAJE", "PARAJE", "PARAJEDESC"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["superficie_total"] = first_existing(raw, ["SUPTOT", "SUPERFICIE_TOTAL"])
    out["superficie_agricola_uso"] = first_existing(raw, ["SUPAG", "SUP_AG", "SUPERFICIE_EN_USO_AGR"])
    out["superficie_agricola_afectada"] = first_existing(raw, ["SUPAFECT", "SUP_AFECT", "SUPERFICIE_AFECTADA_AGR"])
    out["superficie_ganadera_uso"] = first_existing(raw, ["SUPGAN", "SUP_EN_USO_GAN"])
    out["superficie_ganadera_afectada"] = first_existing(raw, ["SUPGANAFECT", "SUP_AFECTADA_TOTAL_GAN"])
    out["porcentaje_afectacion_ganadera"] = first_existing(raw, ["POR_AFECTACION_GAN"])
    out["observaciones"] = first_existing(raw, ["OBS", "OBSERVACIONES"])
    return finalize_frame(out, path.name, sheet_name)


def parse_formato_detalle_agricola_2001(path: Path) -> pd.DataFrame:
    workbook = pd.ExcelFile(path)
    frames: list[pd.DataFrame] = []
    for sheet_name in workbook.sheet_names:
        raw = normalize_columns(pd.read_excel(path, sheet_name=sheet_name))
        if raw.empty:
            continue

        out = empty_output_frame(len(raw))
        out["evento_id"] = "DTO_2001_133"
        out["anio"] = 2001
        out["dto"] = "133"
        out["periodo"] = "2001-133"
        out["iddj"] = first_existing(raw, ["IDDJ"])
        out["codigo"] = first_existing(raw, ["IDDJ"])
        out["productor_nombre"] = first_existing(raw, ["AYN", "PRODUCTORDENOMINACION", "APELLIDO_Y_NOMBRE"])
        out["documento_nro"] = first_existing(raw, ["DOC_NRO", "DNI", "DOCUMENTO_NRO"])
        out["departamento"] = first_existing(raw, ["DEPARTAMENTO", "DEPARTAMENTODESC"])
        out["seccion"] = first_existing(raw, ["SECCION"])
        out["actividad"] = "AGRICULTURA"
        out["cultivo"] = first_existing(raw, ["ESPECIE", "CULTIVO"])
        out["especie"] = first_existing(raw, ["ESPECIE", "CULTIVO"])
        out["categoria"] = first_existing(raw, ["CATEGORIA"])
        out["superficie_plantada_sembrada"] = first_existing(raw, ["SUP_PLANT_SEMB"])
        out["superficie_afectada"] = first_existing(raw, ["SUP_AFEC"])
        out["porcentaje_afectacion"] = first_existing(raw, ["PORC_AFEC", "PORC_CALC"])
        out["superficie_agricola_uso"] = out["superficie_plantada_sembrada"]
        out["superficie_agricola_afectada"] = out["superficie_afectada"]
        frames.append(finalize_frame(out, path.name, sheet_name))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)


def parse_formato_multisheet_2015(path: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    workbook = pd.ExcelFile(path)
    for sheet_name in workbook.sheet_names:
        raw = normalize_columns(pd.read_excel(path, sheet_name=sheet_name))
        if raw.empty:
            continue

        out = empty_output_frame(len(raw))
        decreto = first_existing(raw, ["ANO_DTO", "AÑO_DTO"])
        out["anio"] = decreto.map(extract_anio).fillna(extract_anio(path.stem))
        out["dto"] = decreto.map(extract_dto).fillna(extract_dto(path.stem))
        out["periodo"] = build_periodo(out["anio"], out["dto"])
        out["codigo"] = first_existing(raw, ["CODIGO", "IDDJ"])
        out["iddj"] = first_existing(raw, ["IDDJ", "CODIGO"])
        out["productor_nombre"] = first_existing(raw, ["PRODUCTORDENOMINACION", "NOMBRE_RAZON_SOCIAL"])
        out["documento_nro"] = first_existing(raw, ["DOCUMENTONRO", "DNI", "DOC_NRO"])
        out["cuit_cuil"] = first_existing(raw, ["CUITCUIL", "CUIT_CUIL", "CUIT"])
        out["departamento"] = first_existing(raw, ["DEPARTAMENTODESC", "DEPARTAMENTO"])
        out["localidad"] = first_existing(raw, ["LOCALIDADDESC", "LOCALIDAD"])
        out["paraje"] = first_existing(raw, ["PARAJEDESC", "PARAJE"])
        out["actividad"] = sheet_name
        out["cultivo"] = first_existing(raw, ["CULTIVODESC", "TIPO_CULTIVO"])
        out["superficie_agricola_uso"] = first_existing(raw, ["SUPERFICIEPLANTADA", "SUPUSO"])
        out["superficie_agricola_afectada"] = first_existing(raw, ["SUPERFICIEAFECTADA", "SUPAFECT"])
        out["superficie_ganadera_uso"] = first_existing(raw, ["SUPUSO"])
        out["superficie_ganadera_afectada"] = first_existing(raw, ["SUPAFECT"])
        out["existencias"] = first_existing(raw, ["EXISTENC", "TOTAL_CABEZAS"])
        out["mortandad"] = first_existing(raw, ["MORTANDAD"])
        out["produccion_estimada"] = first_existing(raw, ["PRODUCCIONESTIMADA"])
        out["produccion_obtenida"] = first_existing(raw, ["PRODUCCIONOBTENIDA"])

        if normalize_column_name(sheet_name) in {"AGRIC", "AGRICOLA", "AGRICULTURA"}:
            out["superficie_ganadera_uso"] = pd.NA
            out["superficie_ganadera_afectada"] = pd.NA
        else:
            out["superficie_agricola_uso"] = pd.NA
            out["superficie_agricola_afectada"] = pd.NA

        frames.append(finalize_frame(out, path.name, sheet_name))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)


def parse_formato_moderno_multisheet(path: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    workbook = pd.ExcelFile(path)
    for sheet_name in workbook.sheet_names:
        raw = normalize_columns(pd.read_excel(path, sheet_name=sheet_name))
        if raw.empty:
            continue

        out = empty_output_frame(len(raw))
        decreto = first_existing(raw, ["ANO_DTO", "AÑO_DTO", "ANO_DEC", "AÑO_DEC", "ANO_DCTO", "AÑO_DCTO", "ANO", "AÑO"])
        out["anio"] = decreto.map(extract_anio).fillna(extract_anio(path.stem))
        out["dto"] = decreto.map(extract_dto).fillna(extract_dto(path.stem))
        out["periodo"] = build_periodo(out["anio"], out["dto"])
        out["solicitud_id"] = first_existing(raw, ["SOLICITUDID", "SOLICITUD_ID"])
        out["codigo"] = first_existing(raw, ["CODIGO", "IDDJ"])
        out["iddj"] = first_existing(raw, ["IDDJ", "CODIGO"])
        out["productor_nombre"] = first_existing(raw, ["PRODUCTORDENOMINACION", "NOMBRE_RAZON_SOCIAL"])
        out["documento_nro"] = first_existing(raw, ["DOCUMENTONRO", "DNI", "DOC_NRO"])
        out["cuit_cuil"] = first_existing(raw, ["CUITCUIL", "CUIT_CUIL", "CUIT"])
        out["departamento"] = first_existing(raw, ["DEPARTAMENTODESC", "DEPARTAMENTO"])
        out["localidad"] = first_existing(raw, ["LOCALIDADDESC", "LOCALIDAD"])
        out["paraje"] = first_existing(raw, ["PARAJEDESC", "PARAJE"])
        out["actividad"] = first_existing(raw, ["ACTIVIDAD"])
        if out["actividad"].isna().all():
            out["actividad"] = sheet_name
        out["cultivo"] = first_existing(raw, ["CULTIVODESC", "TIPO_CULTIVO"])
        out["especie"] = first_existing(raw, ["CULTIVODESC", "TIPO_CULTIVO"])
        out["superficie_agricola_uso"] = first_existing(raw, ["SUPERFICIEPLANTADA", "SUPUSO"])
        out["superficie_agricola_afectada"] = first_existing(raw, ["SUPERFICIEAFECTADA", "SUPAFECT"])
        out["superficie_ganadera_uso"] = first_existing(raw, ["SUPUSO"])
        out["superficie_ganadera_afectada"] = first_existing(raw, ["SUPAFECT"])
        out["existencias"] = first_existing(raw, ["EXISTENC", "TOTAL_CABEZAS", "EXIST_CABEZAS_OVINOS", "EXIST_CABEZAS_VACUNOS"])
        out["mortandad"] = first_existing(raw, ["MORTANDAD", "MORTANDAD_OVINOS", "MORTANDAD_VACUNOS"])
        out["produccion_estimada"] = first_existing(raw, ["PRODUCCIONESTIMADA"])
        out["produccion_obtenida"] = first_existing(raw, ["PRODUCCIONOBTENIDA"])
        out["superficie_plantada_sembrada"] = first_existing(raw, ["SUPERFICIEPLANTADA"])
        out["superficie_afectada"] = first_existing(raw, ["SUPERFICIEAFECTADA", "SUPAFECT"])

        has_agric = first_existing(raw, ["SUPERFICIEPLANTADA", "SUPERFICIEAFECTADA", "CULTIVODESC"]).notna().any()
        has_gan = first_existing(raw, ["SUPUSO", "SUPAFECT", "EXISTENC", "MORTANDAD", "EXIST_CABEZAS_OVINOS", "EXIST_CABEZAS_VACUNOS"]).notna().any()

        if has_agric and not has_gan:
            out["superficie_ganadera_uso"] = pd.NA
            out["superficie_ganadera_afectada"] = pd.NA
        elif has_gan and not has_agric:
            out["superficie_agricola_uso"] = pd.NA
            out["superficie_agricola_afectada"] = pd.NA

        frames.append(finalize_frame(out, path.name, sheet_name))

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)


def parse_formato_ganadero_ancho(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    out["anio"] = extract_anio(path.stem)
    out["dto"] = extract_dto(path.stem)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["COD"])
    out["iddj"] = first_existing(raw, ["COD"])
    out["documento_nro"] = first_existing(raw, ["N_DOC", "DOC"])
    out["cuit_cuil"] = first_existing(raw, ["CUIL_O_CUIT"])
    out["productor_nombre"] = first_existing(raw, ["AYN"])
    out["departamento"] = first_existing(raw, ["DPTO_EXPL", "DPTO"])
    out["localidad"] = first_existing(raw, ["LOCALIZ_EXP", "LOCALIZACION"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["actividad"] = "GANADERIA"
    out["superficie_total"] = first_existing(raw, ["SUP_TOT", "SUP_TOT_EX", "SUP_TOT"])
    out["superficie_ganadera_uso"] = first_existing(raw, ["SUP_GAN"])
    out["superficie_ganadera_afectada"] = first_existing(raw, ["SUP_GAN_AF"])
    out["existencias"] = first_existing(raw, ["EXIS_GAN", "EXIS"])
    out["porcentaje_afectacion_ganadera"] = first_existing(raw, ["PORC_AF", "AF"])
    out["observaciones"] = first_existing(raw, ["OBSERVACIONES", "OBS"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


def parse_formato_ganadero_resumido(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    out["anio"] = extract_anio(path.stem)
    out["dto"] = extract_dto(path.stem)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["COD"])
    out["iddj"] = first_existing(raw, ["COD"])
    out["documento_nro"] = first_existing(raw, ["DOC", "N_DOC"])
    out["productor_nombre"] = first_existing(raw, ["AYN"])
    out["departamento"] = first_existing(raw, ["DPTO"])
    out["localidad"] = first_existing(raw, ["LOCALIZACION"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["actividad"] = "GANADERIA"
    out["superficie_total"] = first_existing(raw, ["SUP_TOT", "SUP_TOT"])
    out["superficie_ganadera_uso"] = first_existing(raw, ["SUP_GAN"])
    out["superficie_ganadera_afectada"] = first_existing(raw, ["SUP_GAN_AF"])
    out["existencias"] = first_existing(raw, ["EXIS"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


def parse_formato_agricola_monte_caseros(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    out["anio"] = extract_anio(path.stem)
    out["dto"] = extract_dto(path.stem)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["COD"])
    out["iddj"] = first_existing(raw, ["COD"])
    out["documento_nro"] = first_existing(raw, ["DOC", "N_DOC"])
    out["cuit_cuil"] = first_existing(raw, ["CUIL_O_CUIT"])
    out["productor_nombre"] = first_existing(raw, ["AYN"])
    out["departamento"] = first_existing(raw, ["DPTO"])
    out["localidad"] = first_existing(raw, ["LOCALIZACION", "LOC_PJE_PART"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["actividad"] = "AGRICULTURA"
    out["superficie_total"] = first_existing(raw, ["SUP_TOT"])
    out["superficie_agricola_uso"] = first_existing(raw, ["SUP_SEM"])
    out["superficie_agricola_afectada"] = first_existing(raw, ["SUP_AF"])
    out["superficie_plantada_sembrada"] = out["superficie_agricola_uso"]
    out["superficie_afectada"] = out["superficie_agricola_afectada"]
    out["porcentaje_afectacion"] = first_existing(raw, ["AF"])
    out["observaciones"] = first_existing(raw, ["OBS"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


def parse_formato_tabaco_2007(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    out["anio"] = extract_anio(path.stem)
    out["dto"] = extract_dto(path.stem)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["COD"])
    out["iddj"] = first_existing(raw, ["COD"])
    out["cuit_cuil"] = first_existing(raw, ["CUIT"])
    out["productor_nombre"] = first_existing(raw, ["AYN"])
    out["departamento"] = first_existing(raw, ["DPTO"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["paraje"] = first_existing(raw, ["PARAJE"])
    out["actividad"] = "AGRICULTURA"
    out["cultivo"] = "TABACO"
    out["especie"] = "TABACO"
    out["superficie_total"] = first_existing(raw, ["SUP_TOT_EX", "SUP_TOT"])
    out["superficie_agricola_uso"] = first_existing(raw, ["PLANTADA"])
    out["superficie_agricola_afectada"] = first_existing(raw, ["COSECHADA"])
    out["superficie_plantada_sembrada"] = out["superficie_agricola_uso"]
    out["superficie_afectada"] = out["superficie_agricola_afectada"]
    out["produccion_estimada"] = first_existing(raw, ["PROD_EST"])
    out["produccion_obtenida"] = first_existing(raw, ["PROD_OB"])
    out["porcentaje_afectacion"] = first_existing(raw, ["PORC_AF", "EMERG"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


def parse_formato_detalle_agricola_2007_xls(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    out["anio"] = extract_anio(path.stem)
    out["dto"] = extract_dto(path.stem)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["iddj"] = first_existing(raw, ["IDDJ"])
    out["codigo"] = first_existing(raw, ["IDDJ"])
    out["documento_nro"] = first_existing(raw, ["DOC_NRO"])
    out["cuit_cuil"] = first_existing(raw, ["ING_BRUTOS"])
    out["productor_nombre"] = first_existing(raw, ["AYN"])
    out["departamento"] = first_existing(raw, ["DPTO_ESTAB", "DPTO_PARTICULAR"])
    out["localidad"] = first_existing(raw, ["LOC_PJE_PART", "DOM_ESTAB"])
    out["paraje"] = first_existing(raw, ["DOM_ESTAB"])
    out["seccion"] = first_existing(raw, ["SECCION"])
    out["actividad"] = "AGRICULTURA"
    out["cultivo"] = first_existing(raw, ["ESPECIE"])
    out["especie"] = first_existing(raw, ["ESPECIE"])
    out["categoria"] = first_existing(raw, ["CATEGORIA"])
    out["superficie_total"] = first_existing(raw, ["SUPTOT"])
    out["superficie_agricola_uso"] = first_existing(raw, ["SUP_PLANT_SEMB"])
    out["superficie_plantada_sembrada"] = out["superficie_agricola_uso"]
    out["produccion_estimada"] = first_existing(raw, ["PROD_ESTIM"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


def parse_formato_2019(path: Path) -> pd.DataFrame:
    raw = read_sheet(path)
    out = empty_output_frame(len(raw))
    out["anio"] = extract_anio(path.stem)
    out["dto"] = extract_dto(path.stem)
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out["codigo"] = first_existing(raw, ["CODIGO", "IDDJ"])
    out["iddj"] = first_existing(raw, ["IDDJ", "CODIGO"])
    out["documento_nro"] = first_existing(raw, ["DNI", "DOCUMENTO_NRO", "DOC_NRO"])
    out["productor_nombre"] = first_existing(raw, ["NOMBRE_RAZON_SOCIAL", "APELLIDO_Y_NOMBRE", "AYN"])
    out["cuit_cuil"] = first_existing(raw, ["CUIT", "CUITCUIL", "CUIT_CUIL"])
    out["departamento"] = first_existing(raw, ["DEPARTAMENTO", "DEPARTAMENTODESC"])
    out["localidad"] = first_existing(raw, ["LOCALIDAD", "LOCALIDADDESC"])
    out["paraje"] = first_existing(raw, ["PARAJE", "PARAJEDESC"])
    out["renspa"] = first_existing(raw, ["RENSPA"])
    out["actividad"] = first_existing(raw, ["MIXTO", "ACTIVIDAD"])
    out["cultivo"] = first_existing(raw, ["TIPO_CULTIVO", "CULTIVODESC"])
    out["superficie_total"] = first_existing(raw, ["SUPERFICIE_TOTAL", "SUPTOT"])
    out["superficie_agricola_uso"] = first_existing(raw, ["SUPERFICIE_EN_USO_AGR", "SUPAG"])
    out["superficie_ganadera_uso"] = first_existing(raw, ["SUP_EN_USO_GAN", "SUPGAN"])
    out["superficie_agricola_afectada"] = first_existing(raw, ["SUPERFICIE_AFECTADA_AGR", "SUPAFECT"])
    out["superficie_ganadera_afectada"] = first_existing(raw, ["SUP_AFECTADA_TOTAL_GAN", "SUPGANAFECT"])
    out["existencias"] = first_existing(raw, ["TOTAL_CABEZAS", "N_CABEZAS", "EXISTENC"])
    return finalize_frame(out, path.name, str(pd.ExcelFile(path).sheet_names[0]))


PARSERS: dict[str, Callable[[Path], pd.DataFrame]] = {
    "formato_1998": parse_formato_1998,
    "formato_juradas": parse_formato_juradas,
    "formato_detalle_agricola_2001": parse_formato_detalle_agricola_2001,
    "formato_moderno_multisheet": parse_formato_moderno_multisheet,
    "formato_ganadero_ancho": parse_formato_ganadero_ancho,
    "formato_ganadero_resumido": parse_formato_ganadero_resumido,
    "formato_agricola_monte_caseros": parse_formato_agricola_monte_caseros,
    "formato_tabaco_2007": parse_formato_tabaco_2007,
    "formato_detalle_agricola_2007_xls": parse_formato_detalle_agricola_2007_xls,
    "formato_multisheet_2015": parse_formato_multisheet_2015,
    "formato_2019": parse_formato_2019,
}


def apply_event_mapping(clean: pd.DataFrame, mapping_path: Path = DEFAULT_EVENT_MAPPING) -> pd.DataFrame:
    if clean.empty or not mapping_path.exists():
        return clean

    mapping = pd.read_csv(mapping_path)
    required = {"source_file", "evento_id", "anio_inicio"}
    if not required.issubset(mapping.columns):
        return clean

    optional_cols = [col for col in ["dataset_role", "relation_type"] if col in mapping.columns]
    mapping = mapping[["source_file", "evento_id", "anio_inicio"] + optional_cols].copy()
    mapping["anio_inicio"] = pd.to_numeric(mapping["anio_inicio"], errors="coerce")

    out = clean.merge(mapping, on="source_file", how="left", suffixes=("", "_map"))
    if "evento_id_map" in out.columns:
        out["evento_id"] = out["evento_id_map"].fillna(out["evento_id"])
        out = out.drop(columns=["evento_id_map"])
    for col in ["dataset_role", "relation_type"]:
        mapped_col = f"{col}_map"
        if mapped_col in out.columns:
            out[col] = out[mapped_col].fillna(out[col])
            out = out.drop(columns=[mapped_col])
        elif col not in out.columns:
            out[col] = pd.NA

    mapped_year = out["anio_inicio"]
    fallback_year = out["evento_id"].map(extract_anio).fillna(out["source_file"].map(extract_anio))
    original_year = out["anio"].copy()
    out["anio"] = mapped_year.fillna(fallback_year).fillna(out["anio"])
    out["anio"] = out["anio"].map(extract_anio)
    out["flag_anio_corregido"] = original_year.notna() & out["anio"].notna() & (original_year.astype("string") != out["anio"].astype("string"))
    out["periodo"] = build_periodo(out["anio"], out["dto"])
    out = out.drop(columns=["anio_inicio"], errors="ignore")
    return out


def add_quality_flags(clean: pd.DataFrame) -> pd.DataFrame:
    out = clean.copy()
    for column in OUTPUT_COLUMNS:
        if column not in out.columns:
            out[column] = pd.NA

    numeric_cols = [
        "anio",
        "superficie_total",
        "superficie_agricola_uso",
        "superficie_agricola_afectada",
        "superficie_ganadera_uso",
        "superficie_ganadera_afectada",
        "existencias",
        "mortandad",
    ]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    surface_cols = [
        "superficie_total",
        "superficie_agricola_uso",
        "superficie_agricola_afectada",
        "superficie_ganadera_uso",
        "superficie_ganadera_afectada",
    ]
    out["flag_anio_fuera_rango"] = out["anio"].isna() | out["anio"].lt(1998) | out["anio"].gt(2019)
    out["flag_superficie_negativa"] = out[surface_cols].lt(0).any(axis=1)
    out["flag_agricola_afectada_mayor_uso"] = (
        out["superficie_agricola_afectada"].notna()
        & out["superficie_agricola_uso"].notna()
        & (out["superficie_agricola_afectada"] > out["superficie_agricola_uso"])
    )
    out["flag_ganadera_afectada_mayor_uso"] = (
        out["superficie_ganadera_afectada"].notna()
        & out["superficie_ganadera_uso"].notna()
        & (out["superficie_ganadera_afectada"] > out["superficie_ganadera_uso"])
    )
    out["flag_mortandad_mayor_existencias"] = (
        out["mortandad"].notna()
        & out["existencias"].notna()
        & (out["mortandad"] > out["existencias"])
    )
    affected_sum = out[["superficie_agricola_afectada", "superficie_ganadera_afectada"]].fillna(0).sum(axis=1)
    out["flag_superficie_total_menor_afectadas"] = out["superficie_total"].notna() & affected_sum.gt(0) & (out["superficie_total"] < affected_sum)

    evento_missing = out["evento_id"].isna()
    structural = out["dataset_role"].eq("detalle_agricola") & out["flag_agricola_afectada_mayor_uso"]
    critical = out["flag_anio_fuera_rango"] | out["flag_superficie_negativa"] | out["flag_mortandad_mayor_existencias"] | evento_missing
    high = out["flag_ganadera_afectada_mayor_uso"] | (out["flag_superficie_total_menor_afectadas"] & out["dataset_role"].eq("principal"))
    medium = out["flag_agricola_afectada_mayor_uso"] & out["dataset_role"].eq("principal")

    out["severidad_maxima"] = "ok"
    out.loc[structural, "severidad_maxima"] = "estructural"
    out.loc[medium, "severidad_maxima"] = "medio"
    out.loc[high, "severidad_maxima"] = "alto"
    out.loc[critical, "severidad_maxima"] = "critico"
    out["flag_revision_manual"] = out["severidad_maxima"].isin(["critico", "alto", "medio"])

    return out[OUTPUT_COLUMNS]


def transform_files(input_dir: Path, config_path: Path, output_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    config = pd.read_csv(config_path)
    required = {"archivo", "formato"}
    missing_columns = required.difference(config.columns)
    if missing_columns:
        raise ValueError(f"Faltan columnas en config: {sorted(missing_columns)}")

    frames: list[pd.DataFrame] = []
    status_records: list[dict[str, object]] = []

    for row in config.itertuples(index=False):
        archivo = str(row.archivo)
        formato = str(row.formato)
        path = input_dir / archivo
        parser = PARSERS.get(formato)

        if parser is None:
            status_records.append({"archivo": archivo, "formato": formato, "estado": "formato_no_implementado", "filas": 0, "error": None})
            continue
        if not path.exists():
            status_records.append({"archivo": archivo, "formato": formato, "estado": "archivo_no_encontrado", "filas": 0, "error": str(path)})
            continue

        try:
            parsed = parser(path)
            frames.append(parsed)
            status_records.append({"archivo": archivo, "formato": formato, "estado": "ok", "filas": len(parsed), "error": None})
        except Exception as exc:
            status_records.append({"archivo": archivo, "formato": formato, "estado": "error", "filas": 0, "error": f"{type(exc).__name__}: {exc}"})

    clean = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)
    clean = apply_event_mapping(clean)
    clean = add_quality_flags(clean)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(output_path, index=False, encoding="utf-8-sig")
    return clean, pd.DataFrame(status_records)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transformar Excel historicos a tabla limpia comun.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean, status = transform_files(args.input_dir, args.config, args.output)
    print(f"Archivo limpio generado: {args.output}")
    print(f"Filas limpias generadas: {len(clean)}")
    print("Estado por archivo:")
    print(status.to_string(index=False))


if __name__ == "__main__":
    main()
