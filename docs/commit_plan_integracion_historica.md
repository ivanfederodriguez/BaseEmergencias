# Plan de commit - integracion historica/unificada

## Contexto

Este plan prepara un commit selectivo para subir solo la integracion historica/unificada del dashboard y del pipeline TiDB. No incluye datos, reportes intermedios, credenciales ni scripts puntuales de cargas paralelas.

`git` no estuvo disponible en la terminal local usada para esta revision, por lo que la clasificacion se hizo por inventario de archivos y carpetas del workspace.

## Incluir en commit

### Dashboard

- `dashboard/app.py`
- `dashboard/utils.py`
- `dashboard/pages/5_Analisis.py`
- `dashboard/.streamlit/secrets.toml.example`

Motivo: habilitan `DATA_MODE`, vistas unificadas, filtros de origen y mejoras metodologicas/visuales de la pagina Analisis.

### SQL

- `sql/01_create_historical_views.sql`
- `sql/02_create_unified_views.sql`

Motivo: crean vistas historicas y unificadas, incluyendo la correccion metodologica de `vw_hist_agricultura`.

### Scripts del pipeline historico/TiDB

- `scripts/00_inventory_excel.py`
- `scripts/01_transform_historical_files.py`
- `scripts/02_quality_report.py`
- `scripts/03_consolidate_events.py`
- `scripts/04_quality_report_consolidated.py`
- `scripts/05_upload_to_tidb_staging.py`
- `scripts/06_validate_tidb_staging.py`
- `scripts/07_create_historical_views.py`
- `scripts/08_validate_historical_views.py`
- `scripts/09_create_unified_views.py`
- `scripts/10_validate_unified_views.py`
- `scripts/11_copy_current_tables_to_tidb.py`
- `scripts/12_validate_current_tables_in_dest.py`

Motivo: implementan inventario, transformacion, consolidacion, staging TiDB, validacion y vistas historicas/unificadas.

### Configuracion metodologica

- `config/file_formats.csv`
- `config/event_mapping.csv`

Motivo: documentan parsers y relacion evento/archivo para reproducibilidad.

No incluir por defecto:

- `config/file_formats_backup.csv`
- `config/event_mapping_backup.csv`

Motivo: son respaldos locales generados durante el proceso, no configuracion activa.

### Documentacion generada

- `docs/current_data_source_audit.md`
- `docs/current_data_migration_plan.md`
- `docs/dump_search_report.md`
- `docs/streamlit_data_dependencies.md`
- `docs/streamlit_unified_integration_plan.md`
- `docs/visual_cleanup_plan.md`
- `docs/commit_plan_integracion_historica.md`

Motivo: registran dependencias, decisiones metodologicas, migracion de tablas actuales, integracion unificada y limpieza visual.

## Excluir del commit

### Credenciales y secretos

- `.env`
- `dashboard/.streamlit/secrets.toml`
- cualquier archivo que contenga passwords, tokens, hosts privados con credenciales o certificados privados.

Motivo: seguridad.

### Datos y reportes generados

- `data_raw/`
- `data_clean/`
- `data_intermediate/`
- `*.xlsx`
- dumps reales `*.sql`, `*.sql.gz`, `*.dump`, `*.bak`, `*.zip`, `*.rar`, `*.7z`

Motivo: datos administrativos, reportes pesados o sensibles, no codigo reproducible.

### Entornos y caches

- `.venv/`
- `.venv_local/`
- `__pycache__/`
- `*.pyc`
- `dashboard/__MACOSX/`

Motivo: artefactos locales o de sistema.

### Archivos no usados en esta integracion

- `generar_mock.py`
- `importar_local.ps1`
- `importar_local.sh`
- `importar_tablas_tidb.py`
- `subir_a_tidb.py`
- `subir_a_tidb.sh`
- `transformar.py`

Motivo: pertenecen al flujo original o a pruebas previas; no fueron parte directa de esta integracion historica/unificada.

## Dejar fuera por ahora / flujo paralelo de compañero

Si existen en el worktree antes del commit, no incluir:

- `Anibal/`
- `carpeta general/`
- `crear_mock_data.py`
- `importar_excel_dto_2016.py`
- `importar_excel_dto_2017_235.py`
- `importar_excel_dto_2018.py`
- `reparar_agri_2017.py`
- `reparar_ponde_2017.py`
- cualquier otro script puntual de DTO 2016, DTO 2017 o DTO 2018 no usado por el pipeline normalizado.

Motivo: son otro flujo de carga puntual y pueden solaparse metodologicamente con la integracion historica ya armonizada.

## Comando recomendado

Ejecutar desde la raiz del repo, en un entorno donde `git` este disponible:

```powershell
git add -- `
  dashboard/app.py `
  dashboard/utils.py `
  dashboard/pages/5_Analisis.py `
  dashboard/.streamlit/secrets.toml.example `
  sql/01_create_historical_views.sql `
  sql/02_create_unified_views.sql `
  scripts/00_inventory_excel.py `
  scripts/01_transform_historical_files.py `
  scripts/02_quality_report.py `
  scripts/03_consolidate_events.py `
  scripts/04_quality_report_consolidated.py `
  scripts/05_upload_to_tidb_staging.py `
  scripts/06_validate_tidb_staging.py `
  scripts/07_create_historical_views.py `
  scripts/08_validate_historical_views.py `
  scripts/09_create_unified_views.py `
  scripts/10_validate_unified_views.py `
  scripts/11_copy_current_tables_to_tidb.py `
  scripts/12_validate_current_tables_in_dest.py `
  config/file_formats.csv `
  config/event_mapping.csv `
  docs/current_data_source_audit.md `
  docs/current_data_migration_plan.md `
  docs/dump_search_report.md `
  docs/streamlit_data_dependencies.md `
  docs/streamlit_unified_integration_plan.md `
  docs/visual_cleanup_plan.md `
  docs/commit_plan_integracion_historica.md
```

Luego revisar:

```powershell
git status --short
git diff --cached --stat
git diff --cached -- . ':!*.xlsx' ':!data_raw/**' ':!data_clean/**' ':!data_intermediate/**'
```

Commit sugerido:

```powershell
git commit -m "Integrar historicos agropecuarios en TiDB y dashboard unificado"
```

## Advertencias de seguridad

- Revisar que `.env` no este staged.
- Revisar que no haya `secrets.toml` real staged.
- Revisar que no haya archivos Excel, CSV limpios, reportes intermedios ni dumps SQL staged.
- Revisar que no haya nombres de productores, DNI, CUIT o datos administrativos en documentacion nueva, salvo agregados metodologicos.
- Si `git status --short` muestra archivos no listados en este plan, no agregarlos hasta clasificarlos.
