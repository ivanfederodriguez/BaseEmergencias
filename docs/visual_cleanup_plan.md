# Limpieza visual del dashboard

## Contexto

Al activar `DATA_MODE=unificado`, la pagina `Analisis` empezo a combinar datos actuales e historicos. Esto aumento la cantidad de categorias y amplio mucho el rango de valores, especialmente en cultivos y ganaderia. La intervencion se limito a mejorar legibilidad sin cambiar navegacion, estructura general ni vistas SQL.

## Archivo modificado

- `dashboard/pages/5_Analisis.py`

No se modificaron:

- `dashboard/app.py`
- paginas `Productores`, `Detalle DDJJ`, `Adremas` o `Mapa`
- vistas SQL
- secrets de Streamlit

## Controles agregados

En la parte superior de `Analisis` se agregaron controles simples:

- `Resolucion`
- `Top N`: 10, 20, 30, 50
- `Anio`
- `Origen de datos`: solo visible en modo unificado
- `Ordenar cultivos por`: superficie afectada, superficie sembrada, porcentaje afectado

## Cultivos

Problema original:

- El grafico vertical tenia demasiadas categorias en el eje X.
- Las etiquetas largas se superponian.
- Valores extremos dificultaban comparar cultivos medianos y chicos.

Solucion aplicada:

- Se reemplazo por barras horizontales agrupadas.
- Se muestra por defecto Top 20.
- El usuario puede elegir Top 10, 20, 30 o 50.
- El orden puede definirse por superficie afectada, sembrada o porcentaje afectado.
- Cuando el orden es por superficie afectada o sembrada, el grafico muestra hectareas sembradas y afectadas.
- Cuando el orden es por porcentaje afectado, el grafico cambia a barras de porcentaje de superficie afectada.
- Para el ranking porcentual se agrega `Superficie sembrada minima`, con valor inicial de 10 ha, para evitar porcentajes extremos sobre superficies muy pequenas.
- Las etiquetas largas se truncan en el eje, pero el nombre completo queda disponible en tooltip.
- Se conserva la comparacion entre superficie sembrada y afectada.
- Las categorias sin clasificar no se muestran por defecto en el ranking principal.
- Se agrego el checkbox `Incluir cultivos sin clasificar` para mostrarlas manualmente.
- Se consideran sin clasificar: vacio, `(s/d)`, `s/d`, `sd`, `sin dato`, `sin datos`, `none` y `nan`.
- Debajo del grafico se informa la superficie sembrada, superficie afectada, registros, DDJJ y participacion de los cultivos sin clasificar sobre la superficie afectada agricola filtrada.

Decision metodologica:

- `(s/d)` no es un cultivo real.
- Debe tratarse como alerta de calidad/no clasificado.
- No debe competir en el Top N de cultivos salvo que el usuario active explicitamente su inclusion.

Variables usadas:

- `tipo_cultivo`
- `sembrada`
- `afectada`
- `pct_afectado`
- `registros`
- `ddjj`
- `superficie_minima_pct`

## Ganaderia

Problema original:

- Existencias y mortandad estaban en un mismo grafico, con magnitudes muy distintas.
- La variable grande aplastaba visualmente a la pequena.

Solucion aplicada:

- Se separaron existencias y mortandad en dos graficos horizontales.
- Se agrego tabla resumen con tasa de mortandad.
- Se aplica Top N para mantener lectura rapida.

Variables usadas:

- `categoria`
- `existencias`
- `mortandad`
- `tasa_mortandad`

## Mejoras

Problema original:

- El grafico podia crecer con categorias largas.

Solucion aplicada:

- Se mantiene grafico de barras horizontales.
- Se aplica Top N.
- Se truncan etiquetas largas y se conserva tooltip con nombre completo.
- Se mantiene tabla con valores principales.

Variables usadas:

- `mejora`
- `declaraciones`
- `valor_prom`
- `pct_perdida_prom`

## Tipo juridico y actividad

Problema original:

- El treemap quedaba dominado por una categoria grande.

Solucion aplicada:

- Se mantiene el treemap.
- Se agrego selector:
  - Top combinaciones
  - Todas las categorias
  - Excluir categoria dominante
- Se agrego tabla ordenada con las principales combinaciones.

Variables usadas:

- `tipo_juridico`
- `actividad`
- `n`

## Pendientes visuales

- Revisar si conviene replicar el filtro `origen_dato` en la Home con el mismo criterio visual de la pagina `Analisis`.
- Evaluar si los mapas deben mostrar una advertencia explicita cuando solo representan datos actuales.
- Evaluar una escala logaritmica opcional para superficies si los valores extremos siguen dificultando comparacion.
- Revisar nombres de cultivos historicos para homogeneizar sinonimos antes de una version final institucional.
