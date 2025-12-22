import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.routes import (
    auth_router,
    transacoes_router,
    categorias_router,
    dashboard_router,
    whatsapp_router,
    familia_router,
    agendamentos_router,
    preferencias_router,
    recorrencias_router,
    alertas_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicacao."""
    # Startup
    logger.info("Kairix Financeiro API iniciando...")
    logger.info("Jobs agendados são executados pelo worker arq separado")
    logger.info("Para iniciar o worker: arq backend.worker.WorkerSettings")

    yield

    # Shutdown
    logger.info("Kairix Financeiro API encerrando...")

app = FastAPI(
    title="Kairix Financeiro API",
    description="API para gestão financeira com integração WhatsApp e IA",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(transacoes_router)
app.include_router(categorias_router)
app.include_router(dashboard_router)
app.include_router(whatsapp_router)
app.include_router(familia_router)
app.include_router(agendamentos_router)
app.include_router(preferencias_router)
app.include_router(recorrencias_router)
app.include_router(alertas_router)

# Uploads directory (for attachments)
UPLOADS_DIR = Path("/app/uploads") if Path("/app").exists() else Path("uploads")
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "Kairix Financeiro API"}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Iniciando Kairix Financeiro API em http://{settings.HOST}:{settings.PORT}")

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
