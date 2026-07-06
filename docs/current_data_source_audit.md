# Auditoria de fuente actual del dashboard Streamlit

Fecha de revision: 2026-07-03

## Alcance

Esta auditoria busca identificar donde estan los datos operativos actuales que consume el dashboard Streamlit y como conectarlos o migrarlos al mismo TiDB donde ya existen las tablas historicas staging, las vistas `vw_hist_*` y las vistas `vw_all_*`.

No se modificaron:

- `dashboard/app.py`
- `dashboard/pages/`
- `dashboard/utils.py`
- vistas SQL
- tablas MySQL/TiDB
- archivos `.env` o secrets
- CSV, dumps o Excel originales

## Fuente actual detectada

El dashboard decide la conexion en `dashboard/utils.py`, mediante:

- `.env` en la raiz del proyecto.
- `st.secrets` en Streamlit Cloud, copiados a `os.environ`.
- Variable `DATA_SOURCE`.

Configuracion detectada en `.env`:

| Variable | Estado |
|---|---|
| `DATA_SOURCE` | `local` |
| `MYSQL_HOST` | definido como host local |
| `MYSQL_PORT` | definido como puerto MySQL local |
| `MYSQL_USER` | definido |
| `MYSQL_PASSWORD` | vacio |
| `MYSQL_DATABASE` | `emergencias` |
| `TIDB_HOST` | definido |
| `TIDB_PORT` | definido |
| `TIDB_USER` | definido |
| `TIDB_PASS` | definido |
| `TIDB_DB` | `emergencias` |
| `TIDB_SSL_CA` | no definido activo en `.env` |

Conclusion: localmente, el dashboard esta configurado para leer una base MySQL local llamada `emergencias`, no TiDB.

## Resultado de conexion local

Se intento conectar a la base configurada por el dashboard:

- host: `127.0.0.1`
- puerto: `3306`
- base: `emergencias`

Resultado:

```text
CONNECTION_ERROR: Can't connect to MySQL server on '127.0.0.1'
```

Interpretacion:

- El servidor MySQL local no esta levantado, no escucha en ese puerto, o no esta accesible desde esta sesion.
- Por eso no se pudo verificar directamente si las tablas operativas existen localmente.
- La configuracion y el README indican que la fuente actual prevista es MySQL local importado desde `dump_limpio.sql`.

## Estado en TiDB

En el esquema TiDB activo solo se detectaron:

- `stg_emergencias_productores_consolidated`
- `stg_emergencias_declaraciones_principal`
- `stg_emergencias_agricolas_detalle`
- `vw_hist_*`
- `vw_all_*`

No existen en ese esquema TiDB las tablas operativas actuales:

- `ddjj_personas`
- `productores`
- `resoluciones`
- `agricultura`
- `bovinos`
- `adremas`
- `establecimientos`
- `tipoactividad`
- `tipojuridico`
- `cultivos`
- `cultivostipo`

Por eso las vistas `vw_all_*` contienen actualmente solo `origen_dato = 'historico'`.

## Queries actuales del dashboard

### `dashboard/app.py`

Usa:

- `list_resoluciones()` desde `utils.py`.
- `kpis_generales()` desde `utils.py`.
- `ddjj_personas`
- `resoluciones`

Consultas principales:

```sql
SELECT DISTINCT departamento
FROM ddjj_personas
WHERE departamento <> ''
ORDER BY departamento;
```

```sql
SELECT DISTINCT YEAR(fecha) AS año
FROM ddjj_personas
WHERE fecha > '2000-01-01'
ORDER BY año DESC;
```

```sql
SELECT MIN(fecha) AS mn, MAX(fecha) AS mx
FROM ddjj_personas
WHERE fecha > '2000-01-01';
```

```sql
SELECT r.numero_resolucion, r.nombre_resolucion, COUNT(*) AS ddjj
FROM ddjj_personas dj
JOIN resoluciones r ON r.id_resolucion = dj.id_resolucion
WHERE ...
GROUP BY r.numero_resolucion, r.nombre_resolucion;
```

```sql
SELECT dj.departamento, COUNT(*) AS ddjj, ROUND(AVG(dj.pondf),1) AS pondf_prom
FROM ddjj_personas dj
WHERE ...
GROUP BY dj.departamento;
```

```sql
SELECT dj.pondf
FROM ddjj_personas dj
WHERE ...
```

```sql
SELECT DATE_FORMAT(dj.fecha,'%Y-%m') AS mes, COUNT(*) AS ddjj, ROUND(AVG(dj.pondf),1) AS pondf_prom
FROM ddjj_personas dj
WHERE ...
GROUP BY mes;
```

### `dashboard/utils.py`

Consultas auxiliares:

```sql
SELECT id_resolucion, nombre_resolucion, numero_resolucion, fec_res
FROM resoluciones
ORDER BY fec_res DESC;
```

```sql
SELECT DepartamentoId, DepartamentoDesc, ProvinciaId
FROM departamentos
ORDER BY DepartamentoDesc;
```

```sql
SELECT TipoActividadId AS id, TipoActividadDesc AS descripcion
FROM tipoactividad
ORDER BY TipoActividadDesc;
```

```sql
SELECT id_rubro, nombre
FROM rubro_tipos
ORDER BY id_rubro;
```

```sql
SELECT
  (SELECT COUNT(*) FROM productores) AS productores,
  (SELECT COUNT(*) FROM ddjj_personas) AS ddjj,
  (SELECT COUNT(*) FROM resoluciones) AS resoluciones,
  (SELECT COUNT(*) FROM establecimientos) AS establecimientos,
  (SELECT COUNT(*) FROM adremas) AS adremas,
  (SELECT ROUND(AVG(pondf),2) FROM ddjj_personas WHERE pondf>0) AS pondf_promedio;
```

### `dashboard/pages/1_Productores.py`

Tablas:

- `productores`
- `tipodocumento`
- `tipoactividad`
- `tipojuridico`
- `domicilios`
- `provincias`
- `departamentos`
- `localidades`
- `ddjj_personas`
- `resoluciones`

Uso:

- Busqueda de productores.
- Filtro por actividad.
- Conteo de DDJJ por productor.
- DDJJ asociadas al productor seleccionado.

### `dashboard/pages/2_Detalle_DDJJ.py`

Tablas:

- `ddjj_personas`
- `productores`
- `resoluciones`
- `ponderaciones_ddjj`
- `rubro_tipos`
- `agricultura`
- `cultivostipo`
- `cultivos`
- `bovinos`
- `ovinos`
- `porcinos`
- `avicultura`
- `apicultura`
- `forestacion`
- `perdidas_mejoras`
- `perdidas_invernaculos`
- `perdidas_plurianuales`
- `adremas`
- `tipoactividad`
- `tipotenencia`
- `establecimientos`
- `documentacion`
- `fotos`

Uso:

- Detalle completo de una DDJJ por `id_ddjj`.
- Cabecera administrativa y productor.
- Detalle agricola, ganadero, forestal, mejoras, adremas y adjuntos.

### `dashboard/pages/3_Adremas.py`

Tablas:

- `adremas`
- `tipoactividad`
- `tipotenencia`
- `establecimientos`
- `ddjj_personas`
- `productores`

Uso:

- Listado catastral con filtro por departamento, superficie y texto.

### `dashboard/pages/4_Mapa.py`

Tablas:

- `establecimientos`
- `ddjj_personas`
- `productores`
- `tipoactividad`

Uso:

- Mapa de establecimientos con coordenadas.
- Color por `pondf` o actividad principal.

### `dashboard/pages/5_Analisis.py`

Tablas:

- `resoluciones`
- `agricultura`
- `cultivostipo`
- `ddjj_personas`
- `bovinos`
- `perdidas_mejoras`
- `productores`
- `tipojuridico`
- `tipoactividad`

Uso:

- Superficie sembrada vs afectada.
- Cabezas bovinas vs mortandad por categoria.
- Mejoras declaradas.
- Productores por tipo juridico y actividad.

## Tablas actuales requeridas

### Requeridas por las tareas indicadas

| Tabla | Requerida por |
|---|---|
| `ddjj_personas` | Home, Productores, Detalle DDJJ, Mapa, Analisis |
| `productores` | Home KPI, Productores, Detalle DDJJ, Adremas, Mapa, Analisis |
| `resoluciones` | Home, Productores, Detalle DDJJ, Analisis |
| `agricultura` | Detalle DDJJ, Analisis |
| `bovinos` | Detalle DDJJ, Analisis |
| `adremas` | Home KPI, Detalle DDJJ, Adremas |
| `establecimientos` | Home KPI, Detalle DDJJ, Adremas, Mapa |
| `tipoactividad` | Productores, Detalle DDJJ, Adremas, Mapa, Analisis |
| `tipojuridico` | Productores, Analisis |
| `cultivos` | Detalle DDJJ |
| `cultivostipo` | Detalle DDJJ, Analisis |

### Requeridas adicionalmente por el dashboard

| Tabla | Uso |
|---|---|
| `tipodocumento` | Productores |
| `domicilios` | Productores |
| `provincias` | Productores |
| `departamentos` | Productores/helpers |
| `localidades` | Productores |
| `ponderaciones_ddjj` | Detalle DDJJ |
| `rubro_tipos` | Detalle DDJJ/helpers |
| `ovinos` | Detalle DDJJ |
| `porcinos` | Detalle DDJJ |
| `avicultura` | Detalle DDJJ |
| `apicultura` | Detalle DDJJ |
| `forestacion` | Detalle DDJJ |
| `perdidas_mejoras` | Detalle DDJJ, Analisis |
| `perdidas_invernaculos` | Detalle DDJJ |
| `perdidas_plurianuales` | Detalle DDJJ |
| `tipotenencia` | Detalle DDJJ, Adremas |
| `documentacion` | Detalle DDJJ |
| `fotos` | Detalle DDJJ |

## Evidencia documental del modelo operativo

`ANALISIS_BASE_DATOS.md` documenta que la base operativa esperada tiene, entre otras:

- `productores`: 24.449 filas.
- `ddjj_personas`: 32.423 filas.
- `establecimientos`: 32.363 filas.
- `adremas`: 41.169 filas.
- `ponderaciones_ddjj`: 97.018 filas.
- `resoluciones`: 7 filas.

Esos valores son documentales, no fueron verificados contra una base viva en esta auditoria porque MySQL local no estaba accesible y TiDB no contiene esas tablas.

## Scripts de importacion existentes

Se detectaron scripts ya preparados para trabajar con la base operativa:

| Archivo | Funcion |
|---|---|
| `transformar.py` | Limpia un dump SQL original y genera `dump_limpio.sql`. |
| `importar_local.ps1` | Importa `dump_limpio.sql` a MySQL local en Windows. Recrea la base local. |
| `importar_local.sh` | Importa `dump_limpio.sql` a MySQL local en Unix/Linux/macOS. Recrea la base local. |
| `subir_a_tidb.sh` | Sube `dump_limpio.sql` a TiDB usando cliente `mysql` o fallback PyMySQL. |
| `subir_a_tidb.py` | Sube un dump completo a TiDB mediante PyMySQL. |
| `importar_tablas_tidb.py` | Importa rangos especificos de `dump_limpio.sql` a TiDB. Actualmente contiene rangos para `cultivosestado` y `ddjj_personas`. |

Riesgo importante: `importar_local.ps1` y `importar_local.sh` recrean la base local (`DROP DATABASE IF EXISTS`). No deben ejecutarse sin respaldo y confirmacion especifica.

## Dumps SQL o CSV disponibles

No se encontro `dump_limpio.sql` ni otro dump `.sql` operativo en la raiz del proyecto.

Esto es esperable porque `.gitignore` excluye:

- `*.sql`
- `*.sql.gz`
- `*.dump`

Archivos CSV disponibles:

- `data_clean/*.csv`: corresponden al pipeline historico armonizado, no a la base operativa actual del dashboard.
- `config/*.csv`: configuracion del pipeline historico.

Conclusion: para migrar los datos actuales hace falta recuperar o generar el dump operativo (`dump_limpio.sql` o dump original + `transformar.py`).

## Si las tablas existen localmente

No pudo confirmarse por conexion directa.

Intento realizado:

```text
MYSQL_TARGET: 127.0.0.1:3306 / base emergencias
Resultado: conexion rechazada
```

Interpretacion probable:

- MySQL/XAMPP no esta iniciado; o
- la base esta en otro host/puerto; o
- las variables `MYSQL_*` no apuntan al servidor correcto; o
- la base actual solo existe en otra maquina/servicio.

## Propuesta para migrar tablas actuales a TiDB

### Opcion recomendada: migracion controlada desde dump operativo

1. Obtener el dump original actual de la base operativa.
2. Ejecutar una limpieza reproducible:

```bash
python transformar.py dump_original.sql -o dump_limpio.sql
```

3. Subir a TiDB en una base o esquema de trabajo, no pisando staging historico sin validar:

```bash
python subir_a_tidb.py dump_limpio.sql
```

4. Validar que existan las tablas requeridas:

- `ddjj_personas`
- `productores`
- `resoluciones`
- `agricultura`
- `bovinos`
- `adremas`
- `establecimientos`
- `tipoactividad`
- `tipojuridico`
- `cultivos`
- `cultivostipo`
- y auxiliares usadas por las paginas.

5. Rehacer o ajustar `vw_all_*` para que la rama `actual` lea esas tablas reales.

Ventaja: mantiene el modelo operativo completo y permite que Streamlit conserve su semantica actual.

Riesgo: los scripts actuales de subida completa pueden crear/reemplazar tablas en la misma base. Debe hacerse con respaldo y validacion previa.

### Opcion alternativa: exportar desde MySQL local vivo

Si la base actual esta en MySQL local pero el servicio estaba apagado:

1. Levantar MySQL/XAMPP.
2. Verificar tablas y conteos.
3. Exportar dump:

```bash
mysqldump -h 127.0.0.1 -P 3306 -u root emergencias > dump_actual.sql
```

4. Procesar:

```bash
python transformar.py dump_actual.sql -o dump_limpio.sql
```

5. Subir a TiDB y validar.

### Opcion no recomendada por ahora: modificar Streamlit para mezclar fuentes

No conviene que Streamlit consulte simultaneamente MySQL local para actuales y TiDB para historicos. Aumenta complejidad, latencia, puntos de falla y dificulta despliegue en Streamlit Cloud.

## Riesgos de tocar Streamlit antes de migrar actuales

1. Si se cambia `DATA_SOURCE=tidb` ahora, el dashboard operativo fallara porque TiDB no tiene las tablas actuales esperadas.
2. Las paginas de mapa/adremas dependen de `establecimientos` y coordenadas; los historicos no tienen esa estructura completa.
3. El detalle de DDJJ espera tablas normalizadas y categorias productivas especificas que no siempre existen en historicos.
4. Cambiar queries antes de tener datos actuales en TiDB puede romper filtros, KPIs y graficos ya funcionales.
5. Una integracion apresurada puede mezclar niveles de granularidad: DDJJ operativa vs registro historico consolidado.

## Recomendacion tecnica

No modificar Streamlit todavia.

El siguiente paso deberia ser ubicar el dump operativo actual o levantar MySQL local. Con esa base disponible:

1. Validar conteos de tablas actuales.
2. Migrar tablas actuales a TiDB con nombre original en el mismo esquema o en un esquema separado.
3. Ajustar `vw_all_*` para que incorporen realmente `origen_dato = 'actual'`.
4. Validar `vw_all_*`.
5. Recien despues hacer una modificacion minima en Streamlit para apuntar las consultas a vistas unificadas o a una capa de compatibilidad.

## Version breve para reunion

El dashboard actual no esta leyendo las tablas historicas nuevas. Esta configurado para leer una base MySQL local llamada `emergencias`. En esta sesion esa base no esta accesible porque MySQL local rechazo la conexion. En TiDB ya estan los historicos, pero no estan las tablas operativas actuales. Para unir actual + historico sin romper el dashboard, primero hay que recuperar o generar el dump operativo actual, subir esas tablas a TiDB y luego actualizar las vistas `vw_all_*` para que tengan filas con `origen_dato = 'actual'`.
