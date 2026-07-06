# Dependencias de datos del dashboard Streamlit

Fecha de revision: 2026-07-03

## Alcance

Esta revision inspecciona el codigo actual del dashboard Streamlit sin modificarlo. El objetivo es documentar que tablas, columnas, filtros, KPIs y consultas espera la aplicacion existente, y proponer una capa minima de vistas SQL para conectar en una etapa posterior las tablas historicas cargadas en TiDB staging.

No se modificaron:

- `dashboard/app.py`
- `dashboard/pages/`
- `dashboard/utils.py`
- `.env`
- `secrets.toml`
- `DATA_SOURCE`
- tablas productivas o staging en TiDB

## Archivos revisados

| Archivo | Rol |
|---|---|
| `dashboard/app.py` | Pagina principal del dashboard, filtros globales, KPIs y graficos generales. |
| `dashboard/utils.py` | Capa de conexion, lectura de `.env`/`st.secrets`, helpers de filtros y KPIs. |
| `dashboard/pages/1_Productores.py` | Busqueda/listado de productores y declaraciones asociadas. |
| `dashboard/pages/2_Detalle_DDJJ.py` | Detalle de una declaracion jurada por `id_ddjj`. |
| `dashboard/pages/3_Adremas.py` | Listado catastral de adremas/parcelas. |
| `dashboard/pages/4_Mapa.py` | Mapa de establecimientos georreferenciados. |
| `dashboard/pages/5_Analisis.py` | Analisis agregado de cultivos, ganaderia, mejoras y productores. |

## Archivo principal del dashboard

El archivo principal es:

- `dashboard/app.py`

Ejecucion indicada por el propio archivo:

```bash
cd dashboard
streamlit run app.py
```

## Paginas detectadas

| Pagina | Archivo |
|---|---|
| Productores | `dashboard/pages/1_Productores.py` |
| Detalle DDJJ | `dashboard/pages/2_Detalle_DDJJ.py` |
| Adremas | `dashboard/pages/3_Adremas.py` |
| Mapa | `dashboard/pages/4_Mapa.py` |
| Analisis | `dashboard/pages/5_Analisis.py` |

## Conexion y configuracion

La conexion esta centralizada en `dashboard/utils.py`.

Funciones principales:

- `get_engine()`: crea un `SQLAlchemy Engine` cacheado.
- `run_query(sql, params)`: ejecuta consultas SQL y devuelve `pandas.DataFrame`.
- `db_info()`: informa origen activo.
- `list_resoluciones()`, `list_departamentos()`, `list_actividades()`, `list_rubros()`, `list_departamentos_ddjj()`: helpers para filtros.
- `kpis_generales()`: KPIs de portada.

Fuentes de configuracion:

- `.env` en la raiz del proyecto.
- `st.secrets` en Streamlit Cloud, copiado a variables de entorno cuando existe.

Variable de seleccion de origen:

- `DATA_SOURCE = local | tidb`

Variables esperadas para TiDB en el dashboard:

- `TIDB_HOST`
- `TIDB_PORT`
- `TIDB_USER`
- `TIDB_PASS`
- `TIDB_DB`
- `TIDB_SSL_CA`

Observacion: los scripts de carga staging usan `TIDB_PASSWORD`/`TIDB_DATABASE`, mientras que el dashboard actual espera `TIDB_PASS`/`TIDB_DB`. Para una integracion posterior conviene unificar o admitir ambos alias, pero no se modifica en esta etapa.

## Tablas actuales consumidas

El dashboard actual consume un esquema relacional normalizado. Tablas detectadas:

| Tabla | Uso principal |
|---|---|
| `ddjj_personas` | Declaraciones juradas, filtros globales, fechas, departamento, porcentaje de dano, vinculo con productor y resolucion. |
| `resoluciones` | Filtro por resolucion y agrupaciones por decreto/resolucion. |
| `productores` | Listado de productores, datos personales/productivos y vinculo con DDJJ. |
| `tipodocumento` | Descripcion del tipo de documento del productor. |
| `tipoactividad` | Actividad principal y etiquetas de adremas/mapa. |
| `tipojuridico` | Tipo juridico de productor. |
| `domicilios` | Domicilio del productor. |
| `provincias` | Provincia del domicilio. |
| `departamentos` | Departamento del domicilio. |
| `localidades` | Localidad del domicilio. |
| `ponderaciones_ddjj` | Perdidas ponderadas por rubro. |
| `rubro_tipos` | Descripcion de rubros. |
| `agricultura` | Superficie sembrada/afectada y produccion agricola por DDJJ. |
| `cultivostipo` | Tipo de cultivo. |
| `cultivos` | Cultivo especifico. |
| `bovinos` | Existencias, mortandad y produccion bovina por categorias. |
| `ovinos` | Existencias, mortandad y produccion ovina. |
| `porcinos` | Existencias, mortandad y produccion porcina. |
| `avicultura` | Existencias/perdidas avicolas. |
| `apicultura` | Colmenas afectadas y miel. |
| `forestacion` | Superficie/productos forestales afectados. |
| `perdidas_mejoras` | Mejoras declaradas y perdidas. |
| `perdidas_invernaculos` | Perdidas en invernaculos. |
| `perdidas_plurianuales` | Perdidas en plurianuales. |
| `adremas` | Parcelas catastrales, superficie, actividad, tenencia, vinculo con DDJJ. |
| `tipotenencia` | Descripcion de tenencia. |
| `establecimientos` | Establecimientos, paraje, coordenadas y vinculo con DDJJ. |
| `documentacion` | Documentacion adjunta a la DDJJ. |
| `fotos` | Fotos adjuntas a la DDJJ. |

## Consultas y columnas requeridas por archivo

### `dashboard/app.py`

Filtros:

- `resoluciones`: `id_resolucion`, `nombre_resolucion`, `numero_resolucion`, `fec_res`.
- `ddjj_personas`: `departamento`, `fecha`, `id_resolucion`, `pondf`.

KPIs:

- Conteo de `productores`.
- Conteo de `ddjj_personas`.
- Conteo de `resoluciones`.
- Conteo de `establecimientos`.
- Conteo de `adremas`.
- Promedio de `ddjj_personas.pondf`.

Graficos:

- DDJJ por resolucion: `ddjj_personas.id_resolucion`, `resoluciones.numero_resolucion`, `resoluciones.nombre_resolucion`.
- Top departamentos: `ddjj_personas.departamento`, `ddjj_personas.pondf`.
- Distribucion de dano: `ddjj_personas.pondf`.
- Evolucion mensual: `ddjj_personas.fecha`, `ddjj_personas.pondf`.

### `dashboard/pages/1_Productores.py`

Filtros:

- Texto sobre `productores.ProductorDenominacion`, `productores.CUITCUIL`, `productores.DocumentoNro`.
- Actividad desde `tipoactividad`.

Columnas esperadas:

- `productores`: `ProductorId`, `ProductorDenominacion`, `CUITCUIL`, `DocumentoNro`, `Sexo`, `TipoDocumentoId`, `EsPrincipalActividadEconomica`, `TipoJuridicoId`, `DomicilioId`, `renspa`.
- `tipodocumento`: `TipoDocumentoId`, `TipoDocumentoDesc`.
- `tipoactividad`: `TipoActividadId`, `TipoActividadDesc`.
- `tipojuridico`: `TipoJuridicoId`, `TipoJuridicoDesc`.
- `domicilios`: `DomicilioId`, `ProvinciaId`, `DepartamentoId`, `LocalidadId`.
- `provincias`: `ProvinciaId`, `ProvinciaDesc`.
- `departamentos`: `DepartamentoId`, `DepartamentoDesc`.
- `localidades`: `LocalidadId`, `LocalidadDesc`.
- `ddjj_personas`: `id_ddjj`, `fecha`, `id_productor`, `pondf`, `departamento`, `localidad`, `cargado`, `estado`.
- `resoluciones`: `id_resolucion`, `numero_resolucion`.

### `dashboard/pages/2_Detalle_DDJJ.py`

Clave de navegacion:

- `ddjj_personas.id_ddjj`.

Cabecera:

- `ddjj_personas`: `id_ddjj`, `fecha`, `pondf`, `cargado`, `estado`, `id_productor`, `id_resolucion`, `provincia`, `departamento`, `localidad`, `paraje`.
- `productores`: `ProductorDenominacion`, `CUITCUIL`, `DocumentoNro`.
- `resoluciones`: `numero_resolucion`, `nombre_resolucion`.

Detalle productivo:

- `ponderaciones_ddjj`: `rubro`, `estimados`, `obtenidos`, `perdidas_ponde`, `idddjj`.
- `rubro_tipos`: `id_rubro`, `nombre`.
- `agricultura`: `id_agricultura`, `tipo_cultivo`, `id_cultivo`, `sup_sembrada`, `sup_afectada`, `prod_estimada`, `prod_obtenida`, `estado`, `porcentaje`, `ddjj`.
- `cultivostipo`: `id`, `CultivoTipoDesc`.
- `cultivos`: `id`, `CultivoDesc`.
- `bovinos`: `idddjj`, `cantivaca`, `cantivaqui`, `cantiterne`, `cantinovi`, `cantinovilli`, `cantitoro`, `cantibufa`, `prodespe`, `prodobte`, `carnestimada`, `carneobtenida`, `carneperdida`.
- `ovinos`: `idddjj`, `canticabe`, `mortacabe`, `prodcor`, `corobte`, `prodlana`, `lanaobte`, `perdilana`.
- `porcinos`: `idddjj`, `canticabe`, `mortacabe`, `prodcor`, `corobte`.
- `avicultura`: `idddjj`, `existencia`, `perdida`, `prodnor`, `prodobte`.
- `apicultura`: `idddjj`, `cantcol`, `canafec`, `prodnormiel`, `prodobtemiel`, `mielperdida`.
- `forestacion`: `idddjj`, `supuso`, `supafe`, `superdida`, `prodmaes`, `prodmaob`, `premaes`, `prodinper`, `prodines`, `prodinob`, `preines`, `prodfuen`, `prodfueo`, `prefuen`.
- `perdidas_mejoras`: `idddjj`, `mejora`, `vestimado`, `incidencia`, `pesesp`, `pesper`.
- `perdidas_invernaculos`: `idddjj`, `cobertura_plasticas`, `estructuras`, `supsemb`, `supafect`, `coberplastiperdi`, `danoplastiperdi`.
- `perdidas_plurianuales`: `ddjj`, `cobertura_plantas`, `coberperdi`, `dano_planta`, `danoperdi`.

Adjuntos:

- `adremas`: `ddjj`, `adrema`, `superficie`, `actividad`, `tenencia`, `id_establecimiento`.
- `tipotenencia`: `id`, `descripcion`.
- `establecimientos`: `id_establecimiento`, `nombre_estab`, `paraje_estab`.
- `documentacion`: `idddjj`, `codigo`, `documentacion`, `marcar`.
- `fotos`: `iddjj`, `id`, `file`.

### `dashboard/pages/3_Adremas.py`

Filtros:

- `adremas.departamento`.
- Texto sobre `adremas.adrema` y `productores.ProductorDenominacion`.
- `adremas.superficie`.

Columnas esperadas:

- `adremas`: `adrema`, `superficie`, `actividad`, `tenencia`, `departamento`, `id_establecimiento`, `ddjj`.
- `tipoactividad`: `TipoActividadId`, `TipoActividadDesc`.
- `tipotenencia`: `id`, `descripcion`.
- `establecimientos`: `id_establecimiento`, `nombre_estab`, `paraje_estab`.
- `ddjj_personas`: `id_ddjj`, `id_productor`.
- `productores`: `ProductorId`, `ProductorDenominacion`, `CUITCUIL`.

### `dashboard/pages/4_Mapa.py`

Filtros:

- `establecimientos.departamento_estab`.
- Selector visual entre `pondf` y actividad principal.

Columnas esperadas:

- `establecimientos`: `id_establecimiento`, `nombre_estab`, `departamento_estab`, `latitud`, `longitud`, `ddjj`.
- `ddjj_personas`: `id_ddjj`, `id_productor`, `pondf`.
- `productores`: `ProductorId`, `ProductorDenominacion`, `CUITCUIL`, `EsPrincipalActividadEconomica`.
- `tipoactividad`: `TipoActividadId`, `TipoActividadDesc`.

Limitacion para historicos: las tablas staging historicas no contienen coordenadas ni una estructura catastral completa de establecimientos/adremas.

### `dashboard/pages/5_Analisis.py`

Filtro:

- Resolucion desde `resoluciones`.

Graficos:

- Cultivos: `agricultura.sup_sembrada`, `agricultura.sup_afectada`, `cultivostipo.CultivoTipoDesc`, `ddjj_personas.id_resolucion`.
- Bovinos: columnas especificas por categoria en `bovinos`, vinculadas por `ddjj_personas.id_ddjj`.
- Mejoras: `perdidas_mejoras.mejora`, `vestimado`, `pesper`.
- Productores por tipo juridico y actividad: `productores.TipoJuridicoId`, `productores.EsPrincipalActividadEconomica`, `tipojuridico`, `tipoactividad`.

Limitacion para historicos: la staging historica conserva existencias/mortandad totales y actividad/cultivo armonizados, pero no siempre trae categorias bovinas detalladas equivalentes a `cantivaca`, `cantivaqui`, etc.

## Tablas staging historicas disponibles

| Tabla staging | Contenido validado |
|---|---|
| `stg_emergencias_productores_consolidated` | Base consolidada principal historica, 104.700 filas, 35 eventos, 1998-2019. |
| `stg_emergencias_declaraciones_principal` | Declaraciones principales para evento complementario DTO_2001_133, 32 filas. |
| `stg_emergencias_agricolas_detalle` | Detalle agricola DTO_2001_133, 47 filas. |

Columnas relevantes para integracion:

- Identificacion/trazabilidad: `evento_id`, `anio`, `dto`, `source_file`, `source_sheet`, `dataset_role`, `relation_type`, `codigo`, `iddj`, `solicitud_id`.
- Productor: `productor_nombre`, `documento_nro`, `cuit_cuil`.
- Ubicacion: `departamento`, `localidad`, `paraje`, `seccion`, `renspa`.
- Productivo: `actividad`, `cultivo`, `especie`, `categoria`, superficies, existencias, mortandad, producciones.
- Calidad: flags de calidad y `severidad_maxima`.

## Brecha entre dashboard actual y staging historico

El dashboard actual no puede consumir directamente las tablas staging porque espera:

1. Un esquema normalizado con claves numericas (`id_ddjj`, `ProductorId`, `id_resolucion`).
2. Tablas separadas por dominio (`productores`, `ddjj_personas`, `agricultura`, `bovinos`, `adremas`, `establecimientos`, etc.).
3. Catalogos auxiliares (`tipoactividad`, `resoluciones`, `cultivostipo`, `tipojuridico`).
4. Coordenadas y adremas para mapa/catastro, que no estan completas en los historicos.

Las tablas staging historicas, en cambio, son una capa armonizada y trazable por archivo/evento. La integracion mas prudente es crear vistas SQL de compatibilidad, no cargar todavia en tablas finales ni reestructurar Streamlit.

## Propuesta de vistas SQL minimas

### Vistas necesarias para portada y filtros globales

1. `vw_hist_resoluciones`

Objetivo: exponer eventos historicos como resoluciones/decretos.

Columnas esperadas:

- `id_resolucion`
- `numero_resolucion`
- `nombre_resolucion`
- `fec_res`
- `evento_id`
- `anio`

Fuente sugerida:

- `SELECT DISTINCT evento_id, dto, anio FROM stg_emergencias_productores_consolidated`
- Union opcional con `stg_emergencias_declaraciones_principal`

2. `vw_hist_ddjj_personas`

Objetivo: representar cada registro historico consolidado como declaracion compatible con los filtros actuales.

Columnas minimas:

- `id_ddjj`
- `fecha`
- `pondf`
- `id_resolucion`
- `id_productor`
- `provincia`
- `departamento`
- `localidad`
- `paraje`
- `cargado`
- `estado`
- `evento_id`
- `source_file`
- `source_sheet`
- `severidad_maxima`

Reglas sugeridas:

- `fecha`: construir como `MAKEDATE(anio, 1)` o `STR_TO_DATE(CONCAT(anio, '-01-01'), '%Y-%m-%d')`, porque el ano del evento ya fue corregido metodologicamente.
- `pondf`: usar porcentaje de afectacion disponible. Prioridad sugerida: `porcentaje_afectacion_ganadera`, luego porcentaje agricola si existiera; si no, `NULL`.
- `id_resolucion`: clave deterministica derivada de `evento_id`.
- `id_ddjj`: clave deterministica estable. Preferir `evento_id + codigo`, luego `evento_id + iddj`, luego hash de productor/documento/departamento/actividad/cultivo.
- `estado`: conservar como texto tecnico, por ejemplo `historico`.
- `cargado`: fecha de carga o `fecha_carga`.

### Vistas necesarias para pagina Productores

3. `vw_hist_productores`

Objetivo: exponer productores historicos en forma compatible con la pagina de busqueda.

Columnas minimas:

- `ProductorId`
- `ProductorDenominacion`
- `CUITCUIL`
- `DocumentoNro`
- `Sexo`
- `TipoDocumentoId`
- `EsPrincipalActividadEconomica`
- `TipoJuridicoId`
- `DomicilioId`
- `renspa`

Fuente sugerida:

- Productores deduplicados desde `stg_emergencias_productores_consolidated`.
- Para claves, usar hash estable de `documento_nro`, `cuit_cuil` y `productor_nombre`.

4. `vw_hist_tipoactividad`

Objetivo: catalogo minimo de actividades historicas.

Columnas:

- `TipoActividadId`
- `TipoActividadDesc`

Fuente sugerida:

- Valores distintos de `actividad`.

### Vistas necesarias para detalle productivo

5. `vw_hist_agricultura`

Objetivo: exponer filas agricolas compatibles con `agricultura`.

Columnas minimas:

- `id_agricultura`
- `ddjj`
- `tipo_cultivo`
- `id_cultivo`
- `sup_sembrada`
- `sup_afectada`
- `prod_estimada`
- `prod_obtenida`
- `estado`
- `porcentaje`

Fuente sugerida:

- `stg_emergencias_agricolas_detalle`.
- Registros agricolas de `stg_emergencias_productores_consolidated` cuando `cultivo` o `superficie_agricola_*` existan.

6. `vw_hist_cultivostipo` y `vw_hist_cultivos`

Objetivo: catalogos minimos para etiquetas de cultivos.

Columnas:

- `cultivostipo`: `id`, `CultivoTipoDesc`.
- `cultivos`: `id`, `CultivoDesc`.

Fuente sugerida:

- Valores distintos de `cultivo`, `especie` y/o `categoria`, segun disponibilidad.

7. `vw_hist_bovinos_resumen` o `vw_hist_bovinos`

Objetivo: representar ganaderia historica. Esta vista requiere cuidado porque el dashboard actual espera categorias bovinas especificas.

Columnas minimas si se fuerza compatibilidad con `bovinos`:

- `idddjj`
- `cantivaca`, `mortavaca`
- `cantivaqui`, `mortavaqui`
- `cantiterne`, `mortaterne`
- `cantinovi`, `mortanovi`
- `cantinovilli`, `mortanovilli`
- `cantitoro`, `mortatoro`
- `cantibufa`, `mortabufa`
- `prodespe`, `prodobte`, `carnestimada`, `carneobtenida`, `carneperdida`

Limitacion: los historicos armonizados tienen mayormente `existencias` y `mortandad` totales. No conviene distribuir automaticamente esos totales entre categorias bovinas sin regla documental. Para mantener prudencia, la primera vista deberia exponer un resumen ganadero y adaptar luego el grafico, o completar solo una categoria generica claramente documentada.

### Vistas opcionales o no reconstruibles con staging actual

8. `vw_hist_ponderaciones_ddjj`

Puede construirse parcialmente desde porcentajes y producciones, pero no hay equivalencia completa con rubros originales.

9. `vw_hist_adremas`

No recomendable como vista historica completa en esta etapa. Las tablas staging no contienen adrema catastral completa, tenencia ni establecimiento normalizado en todos los casos.

10. `vw_hist_establecimientos`

No recomendable para mapa en esta etapa. Faltan coordenadas confiables.

11. `vw_hist_perdidas_mejoras`, `vw_hist_perdidas_invernaculos`, `vw_hist_perdidas_plurianuales`, `vw_hist_documentacion`, `vw_hist_fotos`

No hay informacion suficiente en staging historico para reconstruirlas sin crear filas vacias o artificiales.

## Estrategia recomendada de integracion

### Opcion conservadora

Crear vistas historicas con prefijo `vw_hist_` y luego hacer cambios minimos en el dashboard para seleccionar entre:

- esquema operativo actual;
- esquema historico por vistas.

Ventaja: no se pisan tablas existentes y se conserva trazabilidad.

Riesgo: requiere pequenos cambios posteriores en queries del dashboard.

### Opcion de compatibilidad total

Crear vistas con los mismos nombres que las tablas esperadas (`ddjj_personas`, `productores`, `resoluciones`, etc.) en una base separada de TiDB dedicada al historico.

Ventaja: menos cambios en Streamlit si se cambia solo la base.

Riesgo: puede inducir a pensar que la informacion historica tiene el mismo nivel de detalle que la base operativa. No es recomendable para mapa/adremas/detalle ganadero sin aclaraciones.

## Minimo conjunto de vistas para una primera integracion util

Para que la portada, filtros principales, productores y parte del analisis funcionen con historicos, el conjunto minimo es:

1. `vw_hist_resoluciones`
2. `vw_hist_ddjj_personas`
3. `vw_hist_productores`
4. `vw_hist_tipoactividad`
5. `vw_hist_agricultura`
6. `vw_hist_cultivostipo`
7. `vw_hist_cultivos`

Para ganaderia:

8. `vw_hist_ganaderia_resumen`

Esta octava vista deberia alimentar una adaptacion posterior del grafico ganadero, en vez de simular categorias bovinas que no estan documentadas en todos los Excel historicos.

Para mapa/adremas:

- Mantener las paginas actuales conectadas al esquema operativo existente hasta contar con una tabla historica de establecimientos/adremas georreferenciada.

## Recomendacion metodologica

La integracion no deberia reemplazar directamente el esquema operativo. La mejor opcion tecnica es una capa SQL de vistas historicas con nombres explicitos y documentacion de equivalencias:

- evento historico como resolucion;
- registro consolidado como DDJJ historica;
- productor deduplicado como productor historico;
- agricultura/ganaderia historica como resumen productivo, no como detalle operativo completo;
- flags de calidad preservados como columnas consultables.

Esto permite avanzar hacia TiDB/Streamlit sin perder trazabilidad ni mezclar niveles de granularidad.
