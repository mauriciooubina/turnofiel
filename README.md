# TurnoFiel - Sistema de predicción de ausentismo en comercios de servicios con agenda híbrida

Proyecto Final de Ingeniería (PFI) - Universidad Argentina de la Empresa (UADE), 2026.

---

## Stack Tecnológico

- **Frontend:** React 19, Vite, TypeScript, CSS propio (sin frameworks de estilos), linter `oxlint`.
- **Backend:** FastAPI, Uvicorn (ASGI), Pydantic v2. Python 3.13 en el entorno local (`.venv`); la imagen Docker del backend usa Python 3.11.
- **Base de Datos & Persistencia:** PostgreSQL 15, Docker Compose, `psycopg2-binary`.
- **Motor Analítico & ML:** Pandas, NumPy, Scikit-learn, XGBoost, Matplotlib y Seaborn (gráficos), `hashlib` (SHA-256 + Salt).
- **Modelado Matemático:** Teoría de Colas Estocástica ($M/M/s$).

---

## Estructura del Proyecto

```text
turnofiel/
├── .env                         # Variables de entorno locales (no se versiona)
├── .env.example                 # Plantilla de variables de entorno (sin secretos)
├── docker-compose.yml           # Orquestación de PostgreSQL y FastAPI Backend
├── requirements.txt             # Dependencias de Python backend y data pipeline
├── README.md                    # Documentación principal del repositorio
│
├── backend/                     # API Backend en FastAPI
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py              # Punto de entrada de FastAPI y middlewares (CORS)
│   │   ├── config.py            # Carga de variables de entorno y rutas de almacenamiento
│   │   ├── dependencies.py      # Inyección de dependencias (autenticación JWT y control de acceso)
│   │   ├── models/
│   │   │   └── gradient_boosting_model.joblib # Modelo predictivo serializado (Gradient Boosting)
│   │   ├── routers/
│   │   │   ├── actions.py       # Endpoints POST y GET /api/actions
│   │   │   ├── auth.py          # Endpoints POST /api/auth/login y GET /api/auth/me
│   │   │   ├── calendar.py      # Endpoints GET /api/calendar y POST /api/calendar/simulate (solo demo)
│   │   │   ├── export.py        # Endpoint GET /api/export (descarga CSV)
│   │   │   ├── privacy.py       # Endpoints POST /api/privacy/search y /api/privacy/requests
│   │   │   └── queues.py        # Endpoint GET /api/queues
│   │   ├── schemas/             # DTOs y validación con Pydantic v2
│   │   │   ├── actions.py       # Esquemas de solicitud y respuesta de acciones preventivas
│   │   │   ├── auth.py          # Esquemas de credenciales de login y usuario autenticado
│   │   │   ├── calendar.py
│   │   │   ├── privacy.py       # Esquemas de búsqueda, pedidos y estado de privacidad
│   │   │   └── queues.py
│   │   └── services/
│   │       ├── actions_service.py # Registro y consulta de acciones preventivas en base de datos
│   │       ├── auth_service.py  # Autenticación de usuarios, hash bcrypt y emisión de tokens JWT
│   │       ├── calendar_service.py # Servicio de agenda con detección predictiva de riesgo
│   │       ├── db_service.py    # Consultas SQL para PostgreSQL
│   │       ├── export_service.py # Generación y formateo de exportación CSV
│   │       ├── ml_service.py    # Carga del modelo e inferencia de riesgo (ALTO / MEDIO / BAJO)
│   │       ├── privacy_service.py # Búsqueda de clientes y registro de solicitudes de privacidad
│   │       └── queue_service.py # Servicio de serving para teoría de colas M/M/s
│   └── tests/                   # Tests de pytest (API, servicios, modelo ML, colas)
│
├── data/                        # Almacenamiento de Datasets
│   ├── raw/                     # CSVs originales con datos personales (no se versionan, Ley 25.326)
│   │   ├── hellfish/            # appointments.csv, barbers.csv, services.csv
│   │   └── hooligans/           # appointments.csv, barbers.csv, services.csv
│   ├── processed/               # Datos procesados y anonimizados (sí se versionan)
│   │   ├── processed_appointments_matrix.csv
│   │   ├── consolidated_blocks.csv
│   │   ├── hyperparam_search_results.json # Métricas de la búsqueda en grilla de hiperparámetros
│   │   ├── ml_metrics_summary.json
│   │   └── queue_metrics.json
│   └── seed/                    # Barberos y servicios para init_db.py (sí se versionan)
│       ├── barbers.csv
│       └── services.csv
│
├── data_pipeline/               # Pipeline de Ingeniería de Datos y Simulación
│   ├── etl_pipeline.py          # Proceso ETL: limpieza, aislamiento de bloqueos y hashing SHA-256
│   ├── init_db.py               # Script de creación del esquema relacional e ingesta en PostgreSQL
│   ├── create_users.py          # Creación de tabla users y carga de usuarios con contraseñas bcrypt
│   ├── db_roles.py              # Definición y asignación de permisos mínimos para el rol de app
│   ├── reset_demo.py            # Vaciado de acciones preventivas y solicitudes para reiniciar la demo
│   ├── setup_app_role.py        # Creación y configuración del rol restringido en PostgreSQL
│   ├── queuing_theory.py        # Cálculo estocástico de parámetros M/M/s (λ, μ, ρ, Lq, Wq)
│   ├── train_models.py          # Entrenamiento y comparación de modelos (validación cruzada estratificada)
│   ├── retrain_model.py         # Reentrenamiento periódico y calibración por sucursal
│   ├── tune_hyperparams.py      # Búsqueda en grilla de hiperparámetros (valida la configuración de train_models.py)
│   ├── plots/                   # Gráficos generados (matriz de confusión, curvas ROC)
│   └── utils.py                 # Auxiliares criptográficos y DateTime
│
└── frontend/                    # Dashboard Web en React 19 + TypeScript (ver frontend/README.md)
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx              # Componente principal con navegación por pestañas y modo Fallback
        ├── components/          # Agenda, alertas de ausentismo, métricas M/M/s, simulación y ExportModal.tsx
        ├── data/
        │   └── fallbackData.ts  # Datos estáticos de resiliencia local
        └── types/               # Tipos TypeScript de los contratos de la API
```

---

## Modos de Ejecución y Feature Flag (`DATA_SOURCE`)

El backend soporta un **Feature Flag de fuente de datos** mediante la variable de entorno `DATA_SOURCE`:

1. **`DATA_SOURCE=POSTGRES` (valor por defecto):**
   - Consume los datos directamente de la base de datos relacional PostgreSQL activa en Docker.
   - Cuenta con **Mecanismo de Resiliencia (Fallback)**: si la base de datos PostgreSQL no responde o cae, el backend conmuta automáticamente a leer los archivos CSV procesados sin interrupción del servicio.

2. **`DATA_SOURCE=CSV` (Modo Liviano / Local):**
   - Consume directamente los datasets procesados en `data/processed/` sin requerir conexión a base de datos.

El contenedor `turnofiel_backend` de Docker Compose corre siempre con `DATA_SOURCE=POSTGRES` (definido en `docker-compose.yml`). El valor del `.env` aplica cuando el backend se ejecuta fuera de Docker.

---

## Guía de Instalación y Puesta en Marcha

### 1. Requisitos Previos
- Docker Desktop instalado y corriendo.
- Node.js y `npm`.
- Python 3.13 (para el entorno local de scripts y tests).

### 2. Configurar Variables de Entorno
Copiá la plantilla y completá los valores:

```bash
cp .env.example .env
```

El archivo `.env` tiene que contener:

```env
# Backend & CORS
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Feature Flag & Base de Datos PostgreSQL
DATA_SOURCE=POSTGRES
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pfi_db
DB_USER=postgres
DB_PASS=<contraseña-de-postgres>
APP_DB_USER=pfi_app
APP_DB_PASS=<contraseña-de-la-app-mínimo-12-caracteres>

# Salts Criptográficos (Ley 25.326)
HELLFISH_SALT=<sal-secreta-hellfish>
HOOLIGANS_SALT=<sal-secreta-hooligans>

# Autenticación
JWT_SECRET=<cadena-aleatoria-de-32-o-más-caracteres>
JWT_EXPIRE_MINUTES=480
ADMIN_PASSWORD=<contraseña-admin>
HELLFISH_PASSWORD=<contraseña-hellfish>
HOOLIGANS_PASSWORD=<contraseña-hooligans>
```

> El backend no arranca sin `JWT_SECRET`; generala con `openssl rand -hex 32`; las contraseñas van solo en el `.env`.

> Las sales son secretas: definilas solo en tu `.env` local (que no se versiona) y nunca las escribas en el código ni en la documentación. Docker Compose no levanta el backend si `HELLFISH_SALT` o `HOOLIGANS_SALT` no están definidas.

> La contraseña de PostgreSQL también va solo en el `.env`. Docker Compose no levanta los contenedores si `DB_PASS` no está definida. Postgres toma la contraseña únicamente al crear el volumen `pgdata` por primera vez: si ya tenés la base creada, usá en `DB_PASS` la misma contraseña con la que se creó.

> Variables nuevas del `.env`: `APP_DB_USER` (opcional, default `pfi_app`) y `APP_DB_PASS` (obligatoria, ≥ 12 caracteres). `DB_USER` y `DB_PASS` son el admin y solo los usan `postgres` y `tools`.

### 3. Crear el Entorno Virtual de Python

```bash
# Desde la raíz del proyecto (turnofiel/)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. Puesta en Marcha de la Infraestructura

Puesta en marcha desde cero:

```bash
# Levantar la base de datos PostgreSQL
docker compose up -d postgres

# Crea las 6 tablas relacionales (la 6.ª es preventive_actions, vacía) e inserta los 5.320 turnos procesados
docker compose run --rm tools python data_pipeline/init_db.py

# Crea la tabla users y guarda los 3 usuarios con su contraseña hasheada con bcrypt (se puede volver a correr para cambiar contraseñas)
docker compose run --rm tools python data_pipeline/create_users.py

# Crea el rol de la app con permisos mínimos (se puede volver a correr para cambiar APP_DB_PASS; después, `docker compose up -d backend`)
docker compose run --rm tools python data_pipeline/setup_app_role.py

# Construir y levantar toda la plataforma (PostgreSQL, backend y Caddy)
docker compose up -d --build
```

La app queda en **`https://localhost`** y la documentación de la API en `https://localhost/docs`. Ni el 5432 ni el 8000 se publican.

> Para verificar que el backend está activo: abrir `https://localhost/api/health` en el navegador o correr `curl https://localhost/api/health` (responde `{"message": "Backend running successfully.", "status": "active"}`). `GET /` responde lo mismo, pero solo dentro de la red de Docker, porque el 8000 no se publica.

> Los turnos se cargan desde `data/processed/` y los barberos y servicios desde `data/seed/` (versionado, sin datos de contacto). No hace falta `data/raw/`. El esquema declara claves foráneas de `appointments` hacia `barbers` y `services`. Ojo: el script borra y recrea todas las tablas, incluidas las acciones preventivas registradas.

#### Certificado TLS / HTTPS

La primera vez el navegador avisa que la CA no es de confianza. Se puede aceptar la advertencia, o confiar en la CA local de Caddy:

```bash
docker compose cp caddy:/data/caddy/pki/authorities/local/root.crt ./caddy-root.crt
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain caddy-root.crt
```

La CA vive en el volumen `caddy_data`: no cambia entre rebuilds.

### 5. Desarrollo con Recarga en Caliente (Frontend)

Para desarrollar en el frontend con HMR:

```bash
cd frontend
npm install
npm run dev
```

Para desarrollar con `npm run dev`, poné `VITE_API_URL=https://localhost` en `frontend/.env` (CORS ya permite `http://localhost:5173`). El dashboard queda en **`http://localhost:5173`**.

### Recordatorios por WhatsApp y reset de la demo

El botón **Recordatorio por WhatsApp** en los turnos de riesgo de la agenda abre un enlace dinámico hacia `wa.me` con un mensaje personalizado y registra la acción en la tabla `preventive_actions`. Opcionalmente, se puede configurar en `frontend/.env` la variable `VITE_DEMO_WHATSAPP_NUMBER` con un número demo (solo dígitos, ej. `54911...`); si se deja vacía, WhatsApp solicita elegir el contacto.

Para volver al día uno de la demo sin tocar los turnos históricos (`appointments`), se ejecuta el script de reset:

```bash
docker compose run --rm tools python data_pipeline/reset_demo.py
```

### Usuarios y roles

El sistema cuenta con autenticación y control de acceso por roles:
- El usuario `admin` ve ambos comercios.
- Los usuarios `hellfish` y `hooligans` solo ven su propio comercio (el backend responde 403 Forbidden si se solicita el otro).
- Las sesiones utilizan un token JWT con vencimiento de 8 h (`JWT_EXPIRE_MINUTES=480`), guardado en `sessionStorage`.
- En caso de no tener backend disponible, la pantalla de login ofrece entrar **sin conexión**, con datos de respaldo.
- El login siempre consulta PostgreSQL para validar contraseñas con bcrypt; sin embargo, una sesión ya abierta sigue funcionando con el fallback CSV en caso de caída de la base de datos.
- Los scripts `init_db.py` y `reset_demo.py` no borran los usuarios de la tabla `users`.

### Privacidad (Ley 25.326)

La interfaz incluye la pestaña **Privacidad** para gestionar las solicitudes de derechos ARCO realizadas por los clientes al comercio:
- **Búsqueda**: acepta el identificador seudonimizado (`client_hashed` de 16 caracteres) o el número de teléfono del cliente. El teléfono se hashea en el servidor con la sal del comercio y nunca se guarda, imprime ni devuelve.
- **Acciones y botones**:
  - `No contactar` / `Permitir contacto` (derecho de oposición): bloquea las alertas automáticas de WhatsApp para los turnos del cliente sin cancelar la posibilidad de confirmar turnos manualmente.
  - `Suprimir datos` (derecho de cancelación / supresión, Art. 16): desvincula la cita de referencias identificables; los turnos históricos se preservan de forma agregada para estadísticas y colas pero el modelo predictivo los evalúa sin historial (como cliente nuevo). La supresión se aplica dinámicamente al leer (los turnos históricos en `appointments` no se modifican).
- **Endpoints REST**:
  - `POST /api/privacy/search`: busca los registros y turnos de un cliente por hash o por teléfono.
  - `POST /api/privacy/requests`: registra una solicitud de privacidad (`do_not_contact`, `allow_contact` o `erasure`) en `client_privacy_requests`.
- **Reset de la demo**: el script `reset_demo.py` ahora vacía tanto `preventive_actions` como `client_privacy_requests`, restaurando el estado original de la demo sin alterar los turnos históricos (`appointments`).

### Reentrenamiento y calibración periódica

El script `data_pipeline/retrain_model.py` implementa el ciclo de reentrenamiento y calibración periódica del clasificador de ausentismo (Gradient Boosting) declarado en el PFI:

- **Qué hace**: evalúa un modelo candidato mediante validación cruzada estratificada de 5 pliegues (5-Fold Stratified CV), calcula métricas académicas (F1-score, Recall, Precisión, ROC-AUC, Brier score), evalúa la calibración global y segmentada por sucursal (`by_shop`) en las tres bandas de riesgo (`BAJO`, `MEDIO`, `ALTO`), compara probabilísticamente el candidato con el modelo productivo actual y genera un candidato serializado junto con un informe detallado en JSON.
- **Fuentes de datos (`--source`)**:
  - `--source postgres` (por defecto): consulta directamente la base de datos PostgreSQL mediante un join entre `appointments` y `services`. Excluye automáticamente a los clientes que hayan presentado una solicitud de supresión de datos (`erasure` en `client_privacy_requests`). Dado que la columna `appointments.lead_time_hours` se almacena como `NUMERIC(10,2)` (redondeo a 2 decimales), la antelación presenta variaciones marginales frente al valor continuo de la matriz procesada, lo cual puede generar leves diferencias en las probabilidades predichas, lo que puede cambiar el nivel de riesgo de algunas decenas de turnos sobre 5.320; el número exacto queda en `comparison_with_production` del reporte.
  - `--source csv`: entrena leyendo directamente `data/processed/processed_appointments_matrix.csv`. Reproduce con exacta precisión de punto flotante las métricas documentadas en la tesis y el modelo productivo actual (modo de reproducibilidad y auditoría).
- **Integridad y seguridad**: por defecto, el reentrenamiento **no reemplaza** el modelo productivo y nunca reescribe ni modifica `data/processed/ml_metrics_summary.json`.
- **Artefactos generados**:
  - Candidato: `backend/app/models/candidates/gradient_boosting_candidate_<timestamp>.joblib`
  - Reporte: `data/processed/retraining/retrain_report_<timestamp>.json`
- **Promoción a producción (`--promote`)**: al incluir el modificador `--promote`, el script resguarda primero una copia del modelo productivo vigente en `backend/app/models/backups/gradient_boosting_model_<timestamp>.joblib` y luego reemplaza de forma atómica `backend/app/models/gradient_boosting_model.joblib`. Para que el backend cargue en memoria el nuevo clasificador serializado, es necesario reiniciar el servicio:
  ```bash
  docker compose restart backend
  ```
- **Automatización mensual sugerida (Cron)**:
  La calibración periódica puede programarse mensualmente mediante cron ejecutando el script dentro del contenedor `tools`:
  ```bash
  0 3 1 * * cd /ruta/a/pfi && docker compose run --rm tools python data_pipeline/retrain_model.py >> logs/retrain.log 2>&1
  ```
  *(Nota: la carpeta `logs/` debe ser creada previamente en caso de no existir; los archivos `*.log` ya están excluidos en `.gitignore`)*.

### Exportación de datos operativos

El sistema permite exportar el historial de turnos y evaluaciones de riesgo operativo para su análisis externo o auditoría comercial:

- **Endpoint REST**: `GET /api/export`
- **Parámetros de consulta**: `shop_id` (`hellfish` o `hooligans`), `date_from` (`YYYY-MM-DD`) y `date_to` (`YYYY-MM-DD`).
- **Límite temporal y validaciones**: el rango máximo permitido entre `date_from` y `date_to` es de 31 días (inclusive). Se valida que `date_to >= date_from`. Si se solicita un rango mayor a 31 días, la API responde con código `422 Unprocessable Entity`.
- **Control de acceso por roles**:
  - El usuario `admin` tiene autorización para descargar datos operativos de cualquiera de los dos comercios.
  - Los usuarios de comercio (`hellfish`, `hooligans`) solo pueden acceder y exportar los datos correspondientes a su propia sucursal; si intentan consultar otro comercio se rechaza con código `403 Forbidden`.
- **Formato y compatibilidad del CSV**:
  - Delimitador: punto y coma (`;`).
  - Codificación: UTF-8 con BOM (`\ufeff`), garantizando apertura directa en Microsoft Excel sin problemas de tildes o caracteres especiales.
  - Separador decimal: coma (ej. `0,9685`, `18000,00`).
  - Fin de línea: CRLF (`\r\n`).
  - Protección contra CSV Injection: celdas que comiencen con `=`, `+`, `-`, `@`, tabulador o retorno de carro se sanitizan automáticamente anteponiendo un apóstrofe (`'`).
- **Estructura de columnas (17 campos)**:
  `fecha`, `hora_inicio`, `hora_fin`, `turno_id`, `profesional`, `servicio`, `precio_servicio`, `duracion_min`, `cliente_hash`, `canal`, `riesgo`, `probabilidad_ausencia`, `accion_sugerida`, `contacto_bloqueado`, `datos_suprimidos`, `acciones_registradas`, `asistencia_real`.
- **Protección de datos (Ley 25.326)**: los clientes que hayan ejercido su derecho de supresión de datos se exportan con el identificador `cliente_hash` en blanco (`""`) y con el campo `datos_suprimidos` marcado en `"sí"`.

### Regenerar datos y modelo (opcional)

Los datos procesados de `data/processed/` y el modelo `gradient_boosting_model.joblib` ya están versionados, así que este paso no es necesario para correr el sistema. Para regenerarlos hacen falta los CSVs originales de `data/raw/`, que no se incluyen en el repositorio por contener datos personales:

```bash
.venv/bin/python data_pipeline/etl_pipeline.py     # limpieza, anonimización y matriz procesada
.venv/bin/python data_pipeline/queuing_theory.py   # parámetros M/M/s (queue_metrics.json)
.venv/bin/python data_pipeline/train_models.py     # entrenamiento, métricas y modelo serializado
```

> Reentrenar reemplaza el modelo serializado y puede cambiar las métricas reportadas en el documento del PFI.

La búsqueda de hiperparámetros solo usa `data/processed/`, así que se puede correr sin los datos crudos. No reentrena ni reemplaza el modelo: compara la configuración en uso de cada clasificador con la mejor de su grilla y guarda el resultado en `data/processed/hyperparam_search_results.json` (tarda unos 5 minutos).

```bash
.venv/bin/python data_pipeline/tune_hyperparams.py
```

---

## Endpoints de la REST API (FastAPI)

Una vez iniciado el backend, se puede acceder a la documentación interactiva OpenAPI (Swagger UI) en:
**`https://localhost/docs`**

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Verifica que el backend esté activo. |
| `GET` | `/api/health` | Verificación de estado pública (sin login), accesible por HTTPS. |
| `POST` | `/api/auth/login` | Valida usuario y contraseña (bcrypt) y devuelve un token JWT. |
| `GET` | `/api/auth/me` | Devuelve el usuario autenticado y su comercio. |
| `GET` | `/api/calendar?shop_id={hellfish\|hooligans}&date={YYYY-MM-DD}` | Devuelve la agenda del día con categorización predictiva de riesgo de ausentismo (`ALTO`, `MEDIO`, `BAJO`). |
| `POST` | `/api/calendar/simulate` | **Solo para la demo de la defensa.** Simula la incorporación de un turno nuevo y devuelve su nivel de riesgo de ausentismo y su color de semaforización. |
| `GET` | `/api/queues` | Devuelve los parámetros del modelo $M/M/s$ en tres modos: sin parámetros (métricas históricas por comercio), `?lambda_rate=&mu_rate=&servers=` (cálculo directo, CP5) y `?shop_id=&date=&walk_ins=12:2,18:1` (franjas horarias del día con λ = Σ(1−p) + walk-ins, sin guardar nada). |
| `POST` | `/api/actions` | Registra una acción preventiva (`whatsapp` o `confirm`) sobre un turno en `preventive_actions`. |
| `GET` | `/api/actions?shop_id={hellfish\|hooligans}` | Devuelve el historial de acciones preventivas registradas para un comercio. |
| `GET` | `/api/export?shop_id={hellfish\|hooligans}&date_from={YYYY-MM-DD}&date_to={YYYY-MM-DD}` | Descarga en archivo CSV los turnos del rango (hasta 31 días) con nivel de riesgo, probabilidad y acción sugerida. |
| `POST` | `/api/privacy/search` | Busca los turnos de un cliente por identificador seudonimizado o por teléfono (se hashea en el servidor). |
| `POST` | `/api/privacy/requests` | Registra una solicitud de privacidad (`do_not_contact`, `allow_contact` o `erasure`). |

> El endpoint `POST /api/calendar/simulate` y el botón **Simular turno entrante** de la agenda existen solo para la demo de la defensa del PFI y no forman parte del MVP: en el producto, los turnos nuevos se incorporan cuando un cliente reserva en el sistema de turnos del comercio.

---

## Tests automatizados

El backend tiene una suite de pytest que puede ejecutarse dentro del contenedor `tools` o en el entorno local:

```bash
# Con el contenedor tools (incluye tests con conexión a base de datos)
docker compose run --rm tools pytest backend/tests -q

# O en el entorno local (fuera de Docker, los tests que leen la base se saltean)
.venv/bin/python -m pytest backend/tests -q
```

| Archivo | Qué cubre |
| :--- | :--- |
| `test_ml_service.py` | Carga del modelo, umbrales de riesgo (0,20 / 0,50), regla de barbero inactivo y fallback heurístico. `test_predict_documented_high_risk_case` reproduce el **Caso de Prueba 2** de la tesis (turno documentado → `ALTO`, probabilidad ≈ 0,68, inferencia < 5 ms). |
| `test_calendar.py` | Endpoint de agenda y simulación de turnos. `test_calendar_fallback_http_when_postgres_down` reproduce el **Caso de Prueba 4** de la tesis (PostgreSQL caído → fallback a CSV con HTTP 200 en < 200 ms). |
| `test_queues.py` | Endpoint y servicio de teoría de colas $M/M/s$, incluido el fallback a archivo si PostgreSQL no responde, franjas con walk-ins y parámetros directos (CP5). |
| `test_db_service.py` | Consultas a PostgreSQL: usa la base real si está levantada y, si no, una conexión simulada. |
| `test_main.py` | Endpoint raíz y esquema OpenAPI. |
| `test_actions.py` | Registro y consulta histórica de acciones preventivas (POST y GET `/api/actions`), validación de tipos y manejo de errores ante caídas de la base de datos. |
| `test_auth.py` | Autenticación con contraseñas bcrypt, ciclo de vida de tokens JWT, control de acceso por rol o comercio y endpoints de login y sesión actual (`/api/auth/login`, `/api/auth/me`). |
| `test_calendar_service_unit.py` | Lógica unitaria del servicio de agenda, perfiles del simulador de turnos, antelación, cálculo de diagnósticos e integración con la base o CSV. |
| `test_data_pipeline.py` | Funciones auxiliares del pipeline (hashing SHA-256 con salt, parseo de fechas, zonas horarias, extracción de nombres de imagen) y preprocesamiento de datos para entrenamiento. |
| `test_db_roles.py` | Validación de nombres de roles de PostgreSQL, aprovisionamiento y asignación idempotente de privilegios mínimos para el rol de aplicación. |
| `test_deploy_config.py` | Configuración de despliegue en `docker-compose.yml` (puertos expuestos, perfiles, nombres de contenedores e imagen) y reglas de proxy inverso en `Caddyfile`. |
| `test_export.py` | Generación y exportación de turnos a CSV (GET `/api/export`), validación de rangos de fechas, formateo de celdas y acciones sugeridas. |
| `test_init_db.py` | Esquema relacional de la base de datos, claves foráneas, datos semilla de barberos y servicios sin columnas de datos personales e ingesta de datos. |
| `test_privacy.py` | Búsqueda por teléfono o hash, registro de solicitudes de no contacto y derecho al olvido/supresión (Ley 25.326), enmascarado de los clientes suprimidos y consistencia en agenda y colas. |
| `test_retrain_model.py` | Reentrenamiento: carga del dataset desde CSV o PostgreSQL, exclusión de clientes con solicitud de supresión, validación del dataset, bandas de riesgo y resumen de calibración por sucursal, y que sin `--promote` el modelo productivo no se reemplace (con `--promote`, respaldo y reemplazo). |
| `test_schemas.py` | Validación y serialización de contratos DTO con Pydantic v2 (esquemas de agenda, colas, acciones preventivas y privacidad). |

---

## Cumplimiento Normativo (Ley N° 25.326)

Toda la información personal e identificable (nombres y teléfonos de clientes, y los usuarios que crearon o eliminaron cada turno) es sometida a un proceso irreversible de **anonimización criptográfica mediante algoritmos Hash SHA-256 combinados con sales por comercio (*Salted Hashing*)** durante la fase ETL, garantizando el cumplimiento normativo de la Ley Argentina de Protección de Datos Personales. Los datos originales (`data/raw/`) no se versionan.

---

## 🛑 Apagado del Sistema y Liberación de Recursos

### 1. Detener el Frontend (React)
En la terminal donde ejecutaste `npm run dev`, presioná:
```bash
Ctrl + C
```

### 2. Apagar los Contenedores Docker (PostgreSQL + Backend FastAPI)
Desde la raíz del proyecto (`turnofiel/`), ejecutá:
```bash
docker compose stop    # pausa los contenedores sin perder nada
docker compose down    # elimina los contenedores; la base de datos se conserva en el volumen pgdata
```

> ⚠️ **No uses `docker compose down -v`**: elimina el volumen `pgdata` con toda la base de datos y habría que volver a correr `init_db.py`.

---

## 📄 Autores

- **Proyecto:** TurnoFiel - Proyecto Final de Ingeniería (PFI)
- **Carrera:** Ingeniería en Informática
- **Institución:** Universidad Argentina de la Empresa (UADE) - 2026
- **Autor:** Mauricio Nicolás Oubiña
- **Tutor:** Pablo Eduardo Hernandez
