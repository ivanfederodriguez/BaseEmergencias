# Emergencias Agropecuarias — Pipeline + Dashboard

Procesa los dumps `.sql` que envía la institución, los normaliza, los
sube a TiDB Cloud (o MySQL local) y los presenta en un dashboard
interactivo en Streamlit.

```
.sql original ─► transformar.py ─► dump_limpio.sql ─┬─► MySQL local
                                                    └─► TiDB Cloud Serverless
                                                              │
                                                              ▼
                                                       Streamlit dashboard
```

## Estructura

```
.
├── transformar.py            # Limpia el dump (quita tablas innecesarias, InnoDB, utf8mb4)
├── importar_local.sh         # Importa el dump limpio en MySQL local
├── subir_a_tidb.sh           # Sube el dump limpio a TiDB Cloud
├── .env.example              # Plantilla de credenciales
├── requirements.txt          # Dependencias Python del dashboard
├── ANALISIS_BASE_DATOS.md    # Documentación del modelo de datos
└── dashboard/
    ├── app.py                # Home (KPIs + filtros globales)
    ├── utils.py              # Conexión + helpers + queries
    ├── .streamlit/config.toml
    └── pages/
        ├── 1_Productores.py
        ├── 2_Detalle_DDJJ.py
        ├── 3_Adremas.py
        ├── 4_Mapa.py
        └── 5_Analisis.py
```

## Setup inicial (una sola vez)

```bash
# 1. Configurar credenciales
cp .env.example .env
# editar .env con tus datos (al menos los de MYSQL_* locales)

# 2. Entorno Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 1) Procesar un dump nuevo

Cada vez que la institución te manda un `.sql`:

```bash
python3 transformar.py dump_2026_06.sql -o dump_limpio.sql
```

Resultado:

- Quita las 8 tablas innecesarias (`ddjj_personas_temp`, `productos_bkp`,
  `usuarios_notix`, `menu_admin`, `submenu_admin`, `permisos_admin`,
  `permisos_submenu_admin`, `AnalisisOvinos`).
- Convierte `ENGINE=MyISAM` → `InnoDB`.
- Fuerza `DEFAULT CHARSET=utf8mb4`.
- Imprime estadísticas (líneas, tamaño, tablas).

Opciones útiles:

```bash
# Eliminar tablas adicionales además de las del default
python3 transformar.py in.sql --drop fotos op

# Mantener una de las "por defecto" (ej. usuarios_notix)
python3 transformar.py in.sql --keep usuarios_notix

# No tocar engine o charset
python3 transformar.py in.sql --no-innodb --no-utf8mb4
```

## 2) Cargarlo en MySQL local

```bash
./importar_local.sh dump_limpio.sql
```

Crea (o recrea) la base `emergencias` y muestra el conteo de filas por tabla al final.

## 3) Cargarlo en TiDB Cloud Serverless

**Crear el cluster** (una sola vez):

1. Crear cuenta gratuita en <https://tidbcloud.com> (Google/GitHub).
2. *Create Cluster* → **Serverless** → región (recomendado `us-west-2` o `eu-central-1`).
3. En *Connect* generar un usuario/password — la consola muestra algo así:
   ```
   Host: gateway01.us-west-2.prod.aws.tidbcloud.com
   Port: 4000
   User: <prefix>.root
   Pass: <generado>
   ```
4. Copiar esos valores al `.env`:
   ```
   TIDB_HOST=gateway01.us-west-2.prod.aws.tidbcloud.com
   TIDB_PORT=4000
   TIDB_USER=xxxxxxxx.root
   TIDB_PASS=...
   TIDB_DB=emergencias
   ```
5. Subir:
   ```bash
   ./subir_a_tidb.sh dump_limpio.sql
   ```

> El script ya usa TLS (`--ssl-mode=VERIFY_IDENTITY`) y detecta el CA del sistema.

## 4) Correr el dashboard

```bash
# Origen de los datos: editar .env
DATA_SOURCE=local   # o "tidb"

cd dashboard
streamlit run app.py
```

Se abre en <http://localhost:8501>.

### Páginas

| Página | Qué hace |
| --- | --- |
| **Home** | KPIs (productores, DDJJ, % daño), DDJJ por resolución y departamento, evolución mensual. Filtros globales (resolución, departamento, % daño, fechas). |
| **Productores** | Búsqueda por nombre/CUIT/documento, filtro por actividad. Click en un productor para ver sus DDJJ. |
| **Detalle DDJJ** | Una DDJJ completa: cabecera, ponderaciones por rubro, tabs con Agricultura / Ganadería / Forestal / Mejoras / Adremas-Adjuntos. |
| **Adremas** | Listado catastral filtrable por departamento y superficie. Exporta CSV. |
| **Mapa** | Establecimientos georreferenciados (con auto-corrección de coordenadas mal grabadas como varchar). Color por % daño o actividad. |
| **Análisis** | Hectáreas afectadas vs sembradas, mortandad por categoría bovina, top mejoras, treemap por tipo jurídico/actividad. |

## 5) Publicar el dashboard (opcional)

**Streamlit Community Cloud** (gratis):

1. Subir este repo a GitHub (sin el `.env` — ya está en `.gitignore`).
2. Entrar a <https://share.streamlit.io> y conectar el repo.
3. *Main file*: `dashboard/app.py`.
4. *Advanced settings → Secrets*: pegar en formato **TOML** (no `.env`).
   Ver plantilla: `dashboard/.streamlit/secrets.toml.example`
5. Deploy.

**Secrets en TOML** (ejemplo — reemplazá con tus valores reales):

```toml
DATA_SOURCE = "tidb"
TIDB_HOST = "gateway01.us-west-2.prod.aws.tidbcloud.com"
TIDB_PORT = 4000
TIDB_USER = "299G1v2diSRStgb.root"
TIDB_PASS = "tu_password"
TIDB_DB = "emergencias"
TIDB_SSL_CA = "/etc/ssl/certs/ca-certificates.crt"
```

Errores comunes: `KEY=value` (formato .env), comillas mal cerradas, o líneas vacías raras.

> La app conecta a TiDB (porque está en internet); por eso `DATA_SOURCE=tidb` en Secrets.

## Automatizar el refresco periódico

Cuando recibís un nuevo `.sql` cada X semanas:

```bash
# 1. Limpiarlo
python3 transformar.py dumps/dump_$(date +%Y%m%d).sql -o dumps/limpio.sql

# 2. Subir a TiDB (reemplaza el contenido)
./subir_a_tidb.sh dumps/limpio.sql
```

Esto lo podés meter en un cronjob, en una GitHub Action programada, o en un
script `actualizar.sh` que vos disparas a mano.

## Troubleshooting

| Síntoma | Causa / fix |
| --- | --- |
| `Access denied for user 'root'@'localhost'` | tu MySQL local requiere password — completar `MYSQL_PASSWORD` en `.env`. |
| `SSL connection error: certificate verify failed` (TiDB) | el archivo de CA no existe en `TIDB_SSL_CA`; usar `/etc/ssl/cert.pem` en mac o `/etc/ssl/certs/ca-certificates.crt` en linux. |
| Streamlit: `No module named 'pymysql'` | activar el venv: `source .venv/bin/activate`. |
| El mapa no muestra puntos | los `latitud/longitud` están mal grabados; ver `fix_coord` en `utils.py` (ya intenta repararlos). |
| `Lost connection during query` al importar a TiDB | el dump es muy grande — pasarle `--max-allowed-packet=512M`, o partir el `.sql` por tabla. |
