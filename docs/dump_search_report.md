# Reporte de busqueda de dumps SQL operativos

Fecha de revision: 2026-07-03

## Alcance

Busqueda no destructiva desde:
- `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main`
- `C:\Users\Usuario\OneDrive\Oficina\Polo`

Se ignoraron `.venv`, `.venv_local`, `__pycache__`, `.git`, `data_intermediate`, `data_clean` y `node_modules`. Los comprimidos se listaron sin extraer.

## Resumen

- Candidatos encontrados: 121
- Candidatos con alta probabilidad de dump SQL operativo real: 0
- Archivos llamados exactamente `dump_limpio.sql`: 0
- Archivos llamados `dump_original.sql` o `dump_actual.sql`: 0
- Candidatos donde se detectaron nombres de tablas esperadas: 12
- Comprimidos candidatos listados sin extraer: 1

## Candidatos mas probables

No se detectaron archivos con senales suficientes de dump SQL operativo real.

## Archivos que mencionan tablas esperadas

| Nombre | Extension | Tablas detectadas | Marcadores SQL | Interpretacion | Ruta |
|---|---|---|---|---|---|
| `02_create_unified_views.sql` | `.sql` | `ddjj_personas|productores|resoluciones|agricultura|tipoactividad|cultivos|cultivostipo` | `CREATE OR REPLACE VIEW` | SQL de vistas/repo, no dump | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\sql\02_create_unified_views.sql` |
| `01_create_historical_views.sql` | `.sql` | `ddjj_personas|productores|resoluciones|agricultura|tipoactividad|cultivos|cultivostipo` | `CREATE OR REPLACE VIEW` | SQL de vistas/repo, no dump | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\sql\01_create_historical_views.sql` |
| `DTO 2009-28.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\data_raw\DTO 2009-28.xlsx` |
| `DTO 2009-28.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\Bases-anteriores-emergencias\DTO 2009-28.xlsx` |
| `DTO 2015-55.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\data_raw\DTO 2015-55.xlsx` |
| `DTO 2015-55.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\Bases-anteriores-emergencias\DTO 2015-55.xlsx` |
| `DTO 2006-650.xlsx` | `.xlsx` | `adremas` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\data_raw\DTO 2006-650.xlsx` |
| `DTO 2006-650.xlsx` | `.xlsx` | `adremas` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\Bases-anteriores-emergencias\DTO 2006-650.xlsx` |
| `DTO 2016-01.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\data_raw\DTO 2016-01.xlsx` |
| `DTO 2016-01.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\Bases-anteriores-emergencias\DTO 2016-01.xlsx` |
| `DTO 2013-1479.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\BaseEmergencias-main\data_raw\DTO 2013-1479.xlsx` |
| `DTO 2013-1479.xlsx` | `.xlsx` | `agricultura` | `-` | archivo de datos/documentacion, no dump confirmado | `C:\Users\Usuario\OneDrive\Oficina\Polo\Bases-anteriores-emergencias\DTO 2013-1479.xlsx` |

## Comprimidos candidatos

| Nombre | Extension | MB | Nota | Ruta |
|---|---|---:|---|---|
| `streamlit.zip` | `.zip` | 0.002 | `zip_no_extraido_contenido:.streamlit/|__MACOSX/._.streamlit|.streamlit/secrets.toml.example|__MACOSX/.streamlit/._secret` | `C:\Users\Usuario\OneDrive\Oficina\Polo\streamlit.zip` |

## Todos los candidatos

El listado completo esta en `data_intermediate/dump_search_candidates.csv`.

## Conclusion

No se encontro `dump_limpio.sql` en las carpetas revisadas.
No se encontro `dump_original.sql` ni `dump_actual.sql` con esos nombres exactos.
No se detecto ningun dump SQL operativo real. Los `.sql` encontrados corresponden a vistas del pipeline, no a una exportacion de base operativa.
Algunos Excel historicos y SQL de vistas mencionan nombres de tablas, pero no equivalen a la base actual normalizada del dashboard.
