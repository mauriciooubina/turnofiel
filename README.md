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
pfi/
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
│   │   ├── models/
│   │   │   └── gradient_boosting_model.joblib # Modelo predictivo serializado (Gradient Boosting)
│   │   ├── routers/
│   │   │   ├── calendar.py      # Endpoints GET /api/calendar y POST /api/calendar/simulate
│   │   │   └── queues.py        # Endpoint GET /api/queues
│   │   ├── schemas/             # DTOs y validación con Pydantic v2
│   │   │   ├── calendar.py
│   │   │   └── queues.py
│   │   └── services/
│   │       ├── db_service.py    # Consultas SQL para PostgreSQL
│   │       ├── calendar_service.py # Servicio de agenda con detección predictiva de riesgo
│   │       ├── ml_service.py    # Carga del modelo e inferencia de riesgo (ALTO / MEDIO / BAJO)
│   │       └── queue_service.py # Servicio de serving para teoría de colas M/M/s
│   └── tests/                   # Tests de pytest (API, servicios, modelo ML, colas)
│
├── data/                        # Almacenamiento de Datasets
│   ├── raw/                     # CSVs originales con datos personales (no se versionan, Ley 25.326)
│   │   ├── hellfish/            # appointments.csv, barbers.csv, services.csv
│   │   └── hooligans/           # appointments.csv, barbers.csv, services.csv
│   └── processed/               # Datos procesados y anonimizados (sí se versionan)
│       ├── processed_appointments_matrix.csv
│       ├── consolidated_blocks.csv
│       ├── ml_metrics_summary.json
│       └── queue_metrics.json
│
├── data_pipeline/               # Pipeline de Ingeniería de Datos y Simulación
│   ├── etl_pipeline.py          # Proceso ETL: limpieza, aislamiento de bloqueos y hashing SHA-256
│   ├── init_db.py               # Script de creación del esquema relacional e ingesta en PostgreSQL
│   ├── queuing_theory.py        # Cálculo estocástico de parámetros M/M/s (λ, μ, ρ, Lq, Wq)
│   ├── train_models.py          # Entrenamiento y comparación de modelos (validación cruzada estratificada)
│   ├── tune_hyperparams.py      # Búsqueda en grilla de hiperparámetros (valida la configuración de train_models.py)
│   ├── plots/                   # Gráficos generados (matriz de confusión, curvas ROC)
│   └── utils.py                 # Auxiliares criptográficos y DateTime
│
└── frontend/                    # Dashboard Web en React 19 + TypeScript (ver frontend/README.md)
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── App.tsx              # Componente principal con navegación por pestañas y modo Fallback
        ├── components/          # Agenda, alertas de ausentismo, métricas M/M/s y simulación de turnos
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

El contenedor `pfi_backend` de Docker Compose corre siempre con `DATA_SOURCE=POSTGRES` (definido en `docker-compose.yml`). El valor del `.env` aplica cuando el backend se ejecuta fuera de Docker.

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

# Salts Criptográficos (Ley 25.326)
HELLFISH_SALT=<sal-secreta-hellfish>
HOOLIGANS_SALT=<sal-secreta-hooligans>
```

> Las sales son secretas: definilas solo en tu `.env` local (que no se versiona) y nunca las escribas en el código ni en la documentación. Docker Compose no levanta el backend si `HELLFISH_SALT` o `HOOLIGANS_SALT` no están definidas.

> La contraseña de PostgreSQL también va solo en el `.env`. Docker Compose no levanta los contenedores si `DB_PASS` no está definida. Postgres toma la contraseña únicamente al crear el volumen `pgdata` por primera vez: si ya tenés la base creada, usá en `DB_PASS` la misma contraseña con la que se creó.

### 3. Crear el Entorno Virtual de Python

```bash
# Desde la raíz del proyecto (pfi/)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 4. Encender la Infraestructura (PostgreSQL + FastAPI Backend)

```bash
# Desde la raíz del proyecto (pfi/)
docker compose up -d
```

### 5. Inicializar y Poblar la Base de Datos PostgreSQL

```bash
# Crea las 6 tablas relacionales (la 6.ª es preventive_actions, vacía) e inserta los 5.320 turnos procesados
.venv/bin/python data_pipeline/init_db.py
```

> Los turnos se cargan desde `data/processed/`. Los datos de barberos y servicios se leen de `data/raw/<comercio>/barbers.csv` y `services.csv`; si esos archivos no están disponibles, esas tablas quedan vacías.

### 6. Iniciar el Dashboard Frontend (React + Vite)

```bash
# En una nueva terminal, acceder a la carpeta frontend
cd frontend
npm install
npm run dev
```

El dashboard estará disponible en: **`http://localhost:5173`**

### Recordatorios por WhatsApp y reset de la demo

El botón **Recordatorio por WhatsApp** en los turnos de riesgo de la agenda abre un enlace dinámico hacia `wa.me` con un mensaje personalizado y registra la acción en la tabla `preventive_actions`. Opcionalmente, se puede configurar en `frontend/.env` la variable `VITE_DEMO_WHATSAPP_NUMBER` con un número demo (solo dígitos, ej. `54911...`); si se deja vacía, WhatsApp solicita elegir el contacto.

Para volver al día uno de la demo sin tocar los turnos históricos (`appointments`), se ejecuta el script de reset:

```bash
.venv/bin/python data_pipeline/reset_demo.py
```

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
**`http://localhost:8000/docs`**

| Método | Endpoint | Descripción |
| :--- | :--- | :--- |
| `GET` | `/` | Verifica que el backend esté activo. |
| `GET` | `/api/calendar?shop_id={hellfish\|hooligans}&date={YYYY-MM-DD}` | Devuelve la agenda del día con categorización predictiva de riesgo de ausentismo (`ALTO`, `MEDIO`, `BAJO`). |
| `POST` | `/api/calendar/simulate` | Simula la incorporación de un turno nuevo y devuelve su nivel de riesgo de ausentismo y su color de semaforización. |
| `GET` | `/api/queues` | Devuelve los parámetros del modelo $M/M/s$ en tres modos: sin parámetros (métricas históricas por comercio), `?lambda_rate=&mu_rate=&servers=` (cálculo directo, CP5) y `?shop_id=&date=&walk_ins=12:2,18:1` (franjas horarias del día con λ = Σ(1−p) + walk-ins, sin guardar nada). |
| `POST` | `/api/actions` | Registra una acción preventiva (`whatsapp` o `confirm`) sobre un turno en `preventive_actions`. |
| `GET` | `/api/actions?shop_id={hellfish\|hooligans}` | Devuelve el historial de acciones preventivas registradas para un comercio. |

---

## Tests automatizados

El backend tiene una suite de pytest que no requiere la base de datos levantada:

```bash
# Desde la raíz del proyecto (pfi/)
.venv/bin/python -m pytest backend/tests -q
```

| Archivo | Qué cubre |
| :--- | :--- |
| `test_ml_service.py` | Carga del modelo, umbrales de riesgo (0,20 / 0,50), regla de barbero inactivo y fallback heurístico. `test_predict_documented_high_risk_case` reproduce el **Caso de Prueba 2** de la tesis (turno documentado → `ALTO`, probabilidad ≈ 0,68, inferencia < 5 ms). |
| `test_calendar.py` | Endpoint de agenda y simulación de turnos. `test_calendar_fallback_http_when_postgres_down` reproduce el **Caso de Prueba 4** de la tesis (PostgreSQL caído → fallback a CSV con HTTP 200 en < 200 ms). |
| `test_queues.py` | Endpoint y servicio de teoría de colas $M/M/s$, incluido el fallback a archivo si PostgreSQL no responde, franjas con walk-ins y parámetros directos (CP5). |
| `test_db_service.py` | Consultas a PostgreSQL: usa la base real si está levantada y, si no, una conexión simulada. |
| `test_main.py` | Endpoint raíz y esquema OpenAPI. |

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
Desde la raíz del proyecto (`pfi/`), ejecutá:
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
