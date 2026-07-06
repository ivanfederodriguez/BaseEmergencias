# Plan para ubicar y migrar datos actuales del dashboard

Fecha de revision: 2026-07-03

## Alcance

Esta revision identifica si el repositorio contiene los datos actuales que consume el dashboard Streamlit y que scripts existen para crear, importar o migrar esas tablas al mismo TiDB donde ya estan cargados los historicos.

No se modificaron:

- Streamlit (`dashboard/app.py`, `dashboard/pages/`, `dashboard/utils.py`)
- vistas SQL
- tablas MySQL/TiDB
- datos historicos
- dumps o archivos de datos

## Donde espera el dashboard los datos actuales

El dashboard usa `dashboard/utils.py` como capa de conexion.

Configuracion actual detectada:

| Variable | Valor operativo |
|---|---|
| `DATA_SOURCE` | `local` |
| `MYSQL_HOST` | `127.0.0.1` |
| `MYSQL_PORT` | `3306` |
| `MYSQL_DATABASE` | `emergencias` |
| `TIDB_DB` | `emergencias` |

Con `DATA_SOURCE=local`, Streamlit espera una base MySQL local:

```text
mysql+pymysql://MYSQL_USER:MYSQL_PASSWORD@127.0.0.1:3306/emergencias
```

En la auditoria previa, MySQL local no respondio:

```text
Can't connect to MySQL server on '127.0.0.1'
```

Por lo tanto, los datos actuales no estan accesibles localmente desde esta sesion.

## Tablas actuales que necesita el dashboard

### Minimas para las paginas principales

| Tabla | Uso |
|---|---|
| `ddjj_personas` | Unidad central de DDJJ, filtros, KPIs, detalle, mapa y analisis. |
| `productores` | Productores, busqueda, KPIs y relaciones con DDJJ. |
| `resoluciones` | Filtros por resolucion/decreto y agrupaciones. |
| `agricultura` | Detalle agricola y analisis de superficies. |
| `bovinos` | Detalle y analisis ganadero bovino. |
| `adremas` | Catastro, adremas por DDJJ y KPI. |
| `establecimientos` | Mapa, georreferenciacion y relacion con DDJJ. |
| `tipoactividad` | Catalogo de actividades. |
| `tipojuridico` | Catalogo juridico de productores. |
| `cultivos` | Catalogo de cultivos. |
| `cultivostipo` | Tipo de cultivo. |

### Auxiliares usadas por el dashboard

Tambien son necesarias para que todas las paginas funcionen:

- `tipodocumento`
- `domicilios`
- `provincias`
- `departamentos`
- `localidades`
- `ponderaciones_ddjj`
- `rubro_tipos`
- `ovinos`
- `porcinos`
- `avicultura`
- `apicultura`
- `forestacion`
- `perdidas_mejoras`
- `perdidas_invernaculos`
- `perdidas_plurianuales`
- `tipotenencia`
- `documentacion`
- `fotos`

## Revision de scripts existentes

| Script | Crea tablas actuales | Importa datos actuales | Genera mock | Sube a TiDB | Requiere archivo externo | Observacion |
|---|---:|---:|---:|---:|---:|---|
| `transformar.py` | No | No | No | No | Si, dump SQL original | Limpia un dump original y genera `dump_limpio.sql`. |
| `importar_local.ps1` | Si, desde dump | Si | No | No | Si, `dump_limpio.sql` | Recrea base MySQL local. Destructivo para esa base. |
| `importar_local.sh` | Si, desde dump | Si | No | No | Si, `dump_limpio.sql` | Igual que PowerShell, para Unix/Linux/macOS. |
| `subir_a_tidb.py` | Si, desde dump | Si | No | Si | Si, `dump_limpio.sql` | Importa un dump completo a TiDB via PyMySQL. |
| `subir_a_tidb.sh` | Si, desde dump | Si | No | Si | Si, `dump_limpio.sql` | Usa cliente `mysql` y fallback a `subir_a_tidb.py`. |
| `importar_tablas_tidb.py` | Parcial | Parcial | No | Si | Si, `dump_limpio.sql` | Solo tiene rangos hardcodeados para `cultivosestado` y `ddjj_personas`. No sirve para migracion completa sin actualizar rangos. |
| `generar_mock.py` | Si | Si, pero ficticios | Si | No | No | Crea una base local de prueba. No contiene datos reales actuales. |
| `requirements.txt` | No | No | No | No | No | Dependencias Python. |

## Detalle por script

### `transformar.py`

Funcion:

- Recibe un dump SQL original.
- Elimina tablas administrativas/staging/backup por defecto:
  - `ddjj_personas_temp`
  - `productos_bkp`
  - `AnalisisOvinos`
  - `usuarios_notix`
  - `menu_admin`
  - `submenu_admin`
  - `permisos_admin`
  - `permisos_submenu_admin`
- Convierte `MyISAM` a `InnoDB`.
- Fuerza `utf8mb4`.
- Elimina instrucciones problematicas para importacion (`LOCK TABLES`, GTID, `DEFINER`, etc.).
- Genera `dump_limpio.sql`.

No contiene datos por si mismo.

### `importar_local.ps1` / `importar_local.sh`

Funcion:

- Leen variables `MYSQL_*`.
- Esperan `dump_limpio.sql`.
- Recrean la base local:

```sql
DROP DATABASE IF EXISTS emergencias;
CREATE DATABASE emergencias;
```

- Importan el dump.

Riesgo:

- Son destructivos para la base local configurada. No deben ejecutarse sin respaldo.

### `subir_a_tidb.py` / `subir_a_tidb.sh`

Funcion:

- Esperan un dump limpio.
- Crean la base TiDB si no existe.
- Importan el dump completo.
- Verifican conteos de tablas clave (`productores`, `ddjj_personas`, `adremas`, `resoluciones`).

Riesgo:

- Importar un dump completo al mismo esquema TiDB puede crear o reemplazar tablas operativas y convivir con las staging/vistas historicas.
- No debe ejecutarse hasta confirmar el dump correcto y definir si se importa al mismo esquema o a un esquema separado.

### `importar_tablas_tidb.py`

Funcion:

- Extrae rangos de lineas de `dump_limpio.sql`.
- Actualmente solo define:

```python
RANGES = {
    "cultivosestado": (405, 479),
    "ddjj_personas": (479, 585),
}
```

Limitacion:

- No sirve para migrar todas las tablas actuales sin recalcular rangos para el dump disponible.
- Es fragil: depende de numeros de linea del dump.

### `generar_mock.py`

Funcion:

- Crea tablas compatibles de forma parcial en MySQL local.
- Inserta datos semilla ficticios para desarrollo.

Conclusion:

- No sirve para cargar datos actuales reales.
- Puede ser util solo para pruebas locales del dashboard si no hay base real.
- Ademas, algunas columnas mock no coinciden exactamente con lo que el dashboard consulta, por ejemplo `tipodocumento` y `tipotenencia` pueden requerir ajuste si se usara para pruebas.

## Archivos de datos encontrados

### Encontrados

Archivos historicos y de pipeline:

- `data_raw/*.xlsx` y `data_raw/*.xls`: historicos Excel de emergencias.
- `data_clean/*.csv`: salidas armonizadas historicas.
- `data_intermediate/*.xlsx`: reportes de inventario, calidad, validacion y auditoria.
- `config/*.csv`: configuracion del pipeline historico.

SQL de vistas:

- `sql/01_create_historical_views.sql`
- `sql/02_create_unified_views.sql`

### No encontrados

No se encontro en el repositorio:

- `dump_limpio.sql`
- dump SQL original operativo
- `*.sql`
- `*.sql.gz`
- `*.dump`
- CSV operativos de `ddjj_personas`, `productores`, `resoluciones`, etc.
- Excel operativo con esas tablas normalizadas.

Esto es consistente con `.gitignore`, que excluye:

```text
*.sql
*.sql.gz
*.dump
```

## Evidencia documental de que existio una base real

`ANALISIS_BASE_DATOS.md` documenta una base operativa MySQL con:

- 52 tablas base + 4 vistas.
- Total aproximado: 1,2 millones de filas.
- `productores`: 24.449 filas.
- `ddjj_personas`: 32.423 filas.
- `establecimientos`: 32.363 filas.
- `adremas`: 41.169 filas.
- `ponderaciones_ddjj`: 97.018 filas.
- `resoluciones`: 7 filas.

Pero esos datos no estan materializados en archivos del repo ni accesibles en MySQL local durante esta revision.

## Que falta para cargar las tablas actuales a TiDB

Falta una fuente real de datos actuales:

1. Un dump SQL original de la base operativa, o
2. `dump_limpio.sql` ya generado, o
3. Acceso a MySQL local/servidor donde existan las tablas actuales, o
4. Exportes CSV confiables de todas las tablas requeridas.

Sin esa fuente, no se puede cargar `origen_dato = 'actual'` en TiDB sin inventar datos.

## Recomendacion concreta de migracion

### Recomendacion principal

Migrar directo a TiDB desde un dump operativo real.

Razon:

- El objetivo es que Streamlit pueda usar una fuente unificada.
- MySQL local ahora no responde.
- TiDB ya contiene historicos, staging y vistas.
- Evita depender de una base local para despliegue.

Flujo recomendado:

1. Ubicar el dump operativo original o `dump_limpio.sql`.
2. Si es dump original, generar dump limpio:

```bash
python transformar.py dump_original.sql -o dump_limpio.sql
```

3. Antes de subir, decidir esquema de destino:

- Opcion A: mismo esquema `emergencias`, conservando tablas operativas con sus nombres originales.
- Opcion B: esquema separado, por ejemplo `emergencias_actual`, y luego vistas cross-schema.

Para menor riesgo, conviene Opcion B si TiDB permite consultas cross-schema en el entorno usado. Si se usa el mismo esquema, hay que verificar que no se pisen staging/vistas ya creadas.

4. Subir a TiDB:

```bash
python subir_a_tidb.py dump_limpio.sql
```

5. Validar existencia y conteos de tablas actuales.

6. Ajustar `vw_all_*` para incorporar realmente la rama `origen_dato = 'actual'`.

7. Recien despues evaluar un cambio minimo en Streamlit.

### Recomendacion alternativa

Si la base real esta en MySQL local y solo estaba apagada:

1. Levantar MySQL/XAMPP.
2. Verificar que `emergencias` tenga las tablas esperadas.
3. Exportar dump:

```bash
mysqldump -h 127.0.0.1 -P 3306 -u root emergencias > dump_actual.sql
```

4. Limpiar y subir:

```bash
python transformar.py dump_actual.sql -o dump_limpio.sql
python subir_a_tidb.py dump_limpio.sql
```

## Riesgos

1. `importar_local.*` recrea la base local y puede borrar datos si se apunta a una base con informacion no respaldada.
2. `subir_a_tidb.py` importa el dump completo; puede crear tablas operativas en el mismo esquema TiDB y generar conflictos de nombres si existieran.
3. `generar_mock.py` no debe usarse para produccion: crea datos ficticios.
4. El dashboard actual espera muchas tablas auxiliares. Migrar solo `ddjj_personas` no alcanza.
5. No conviene modificar Streamlit hasta que TiDB tenga tanto actuales como historicos validados.

## Respuestas directas

### Existen datos actuales en el repo?

No. En el repositorio no se encontro un dump operativo ni CSV/Excel con las tablas actuales. Lo que existe son scripts para procesar/importar un dump y datos historicos armonizados.

### Hay script para subirlos a TiDB?

Si. Existen:

- `subir_a_tidb.py`
- `subir_a_tidb.sh`

Pero ambos requieren un archivo externo, normalmente `dump_limpio.sql`.

### Conviene usar MySQL local o migrar directo a TiDB?

Conviene migrar directo a TiDB, siempre que se consiga el dump operativo correcto. MySQL local puede servir como verificacion o respaldo, pero ahora no esta accesible y no resuelve la integracion con historicos.

### Que comando habria que ejecutar despues?

Si ya tenes el dump limpio:

```bash
python subir_a_tidb.py dump_limpio.sql
```

Si tenes el dump original:

```bash
python transformar.py dump_original.sql -o dump_limpio.sql
python subir_a_tidb.py dump_limpio.sql
```

Despues de eso, corresponde validar tablas actuales en TiDB y recien ahi actualizar las vistas `vw_all_*`.
