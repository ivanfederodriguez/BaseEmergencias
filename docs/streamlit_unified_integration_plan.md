# Integracion Streamlit con vistas unificadas

## Contexto

El dashboard ya consumia tablas operativas actuales desde TiDB/MySQL. La nueva capa historica quedo disponible en TiDB mediante vistas `vw_hist_*` y vistas unificadas `vw_all_*`, que combinan registros actuales e historicos con la columna `origen_dato`.

El objetivo de esta etapa fue habilitar el uso configurable de `vw_all_*` sin redisenar el dashboard, sin reemplazar tablas fisicas y sin tocar paginas con dependencias geograficas o identificadores operativos no homologados.

## Archivos modificados

- `dashboard/utils.py`
- `dashboard/app.py`
- `dashboard/pages/5_Analisis.py`
- `dashboard/.streamlit/secrets.toml.example`

## Configuracion agregada

Se agrego `DATA_MODE`:

- `DATA_MODE = "actual"`: mantiene el comportamiento historico del dashboard y usa tablas operativas.
- `DATA_MODE = "unificado"`: usa vistas `vw_all_*` en las consultas preparadas para integrar datos actuales e historicos.

Ejemplo local o Streamlit secrets:

```toml
DATA_SOURCE = "tidb"
DATA_MODE = "unificado"
```

## Capa de tablas configurable

En `dashboard/utils.py` se agregaron:

- `data_mode()`
- `is_unified_mode()`
- `table(name)`

Mapeo en modo `actual`:

- `resoluciones` -> `resoluciones`
- `ddjj_personas` -> `ddjj_personas`
- `productores` -> `productores`
- `tipoactividad` -> `tipoactividad`
- `agricultura` -> `agricultura`
- `cultivos` -> `cultivos`
- `cultivostipo` -> `cultivostipo`
- `ganaderia_resumen` -> `bovinos`

Mapeo en modo `unificado`:

- `resoluciones` -> `vw_all_resoluciones`
- `ddjj_personas` -> `vw_all_ddjj_personas`
- `productores` -> `vw_all_productores`
- `tipoactividad` -> `vw_all_tipoactividad`
- `agricultura` -> `vw_all_agricultura`
- `cultivos` -> `vw_all_cultivos`
- `cultivostipo` -> `vw_all_cultivostipo`
- `ganaderia_resumen` -> `vw_all_ganaderia_resumen`

## Queries cambiadas

### `dashboard/app.py`

La pagina principal ahora usa:

- `vw_all_ddjj_personas` cuando `DATA_MODE="unificado"`.
- `vw_all_resoluciones` cuando `DATA_MODE="unificado"`.
- KPI de productores, DDJJ y resoluciones desde `vw_all_*` en modo unificado.

Se agrego un filtro lateral opcional:

- `origen_dato`: todos, actual, historico.

Las consultas adaptadas son:

- DDJJ por resolucion.
- Top 15 departamentos.
- Distribucion de porcentaje de dano.
- Evolucion mensual de DDJJ.
- Filtros de resolucion, departamento, anio y fecha.

### `dashboard/pages/5_Analisis.py`

En modo `unificado`, se adaptaron:

- Cultivos: usa `vw_all_agricultura`.
- Ganaderia: usa `vw_all_ganaderia_resumen`.
- Resoluciones: usa `vw_all_resoluciones`.

Se mantienen en tablas actuales:

- Top tipos de mejora declaradas.
- Productores por tipo juridico y actividad.

La razon es metodologica: no existe todavia una vista historica equivalente para mejoras ni una homologacion completa de tipo juridico historico.

## Paginas compatibles con datos unificados

- `dashboard/app.py`: compatible con datos actuales + historicos.
- `dashboard/pages/5_Analisis.py`: compatible parcialmente; cultivos y ganaderia usan vistas unificadas.

## Paginas que siguen usando tablas actuales

- `dashboard/pages/1_Productores.py`
- `dashboard/pages/2_Detalle_DDJJ.py`
- `dashboard/pages/3_Adremas.py`
- `dashboard/pages/4_Mapa.py`

Estas paginas dependen de una o mas de las siguientes condiciones:

- IDs operativos como `id_productor` o `id_ddjj`.
- Relaciones directas con tablas actuales no historicas.
- `adremas`.
- `establecimientos`.
- Coordenadas y mapas.
- Detalles administrativos sin equivalente historico trazable.

Por eso se mantienen con datos actuales en esta etapa.

## Vistas usadas

- `vw_all_resoluciones`
- `vw_all_ddjj_personas`
- `vw_all_productores`
- `vw_all_agricultura`
- `vw_all_ganaderia_resumen`

Disponibles pero no conectadas todavia a paginas especificas:

- `vw_all_tipoactividad`
- `vw_all_cultivos`
- `vw_all_cultivostipo`

## Riesgos detectados

- Las vistas historicas no tienen `adremas`, `establecimientos` ni coordenadas suficientes para mapas.
- Algunos historicos tienen identificadores conceptuales (`evento_id`, `iddj`, `codigo`) y no los mismos IDs numericos que el esquema actual.
- Las paginas de detalle requieren una normalizacion mas fina antes de poder navegar historicos como si fueran declaraciones actuales.
- Los graficos agregados pueden mezclar eventos actuales e historicos; por eso se agrego el filtro `origen_dato`.
- La vista unificada de ganaderia historica esta resumida y no replica todas las categorias bovinas actuales.

## Recomendacion de integracion minima

1. Probar localmente con `DATA_SOURCE=tidb` y `DATA_MODE=unificado`.
2. Revisar visualmente la pagina principal y `Analisis`.
3. Confirmar que las paginas `Productores`, `Detalle DDJJ`, `Adremas` y `Mapa` sigan funcionando con datos actuales.
4. Si la prueba es correcta, actualizar secrets reales de Streamlit Cloud agregando solo `DATA_MODE = "unificado"`.
5. En una etapa posterior, disenar vistas historicas especificas para detalle de productores, detalle de DDJJ y mapas, sin forzar datos geograficos inexistentes.
