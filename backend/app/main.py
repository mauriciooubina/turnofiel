import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.config import CORS_ALLOWED_ORIGINS, BACKEND_HOST, BACKEND_PORT, JWT_SECRET

if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("Definir JWT_SECRET en .env (mínimo 32 caracteres)")

from app.routers import actions, auth, calendar, export, privacy, queues

app = FastAPI(
    title="Sistema de Predicción de Ausentismo",
    description="Backend en FastAPI con inferencia de ausentismo en tiempo real y dimensionamiento estocástico M/M/s.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(calendar.router)
app.include_router(queues.router)
app.include_router(actions.router)
app.include_router(privacy.router)
app.include_router(export.router)

HEALTH_RESPONSE = {"message": "Backend running successfully.", "status": "active"}

@app.get("/")
def read_root():
    return HEALTH_RESPONSE

@app.get("/api/health", tags=["health"])
def health_check():
    """Verificación de estado del servicio (público, sin autenticación). Accesible por HTTPS a través de Caddy."""
    return HEALTH_RESPONSE

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=True)
