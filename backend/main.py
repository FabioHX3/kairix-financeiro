import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

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

# Static files
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


# Pages
@app.get("/")
async def home():
    return FileResponse("frontend/templates/login.html")


@app.get("/login")
async def login_page():
    return FileResponse("frontend/templates/login.html")


@app.get("/cadastro")
async def cadastro_page():
    return FileResponse("frontend/templates/cadastro.html")


@app.get("/dashboard")
async def dashboard_page():
    return FileResponse("frontend/templates/dashboard.html")


@app.get("/receitas")
async def receitas_page():
    return FileResponse("frontend/templates/receitas.html")


@app.get("/despesas")
async def despesas_page():
    return FileResponse("frontend/templates/despesas.html")


@app.get("/meus-dados")
async def meus_dados_page():
    return FileResponse("frontend/templates/meus-dados.html")


@app.get("/relatorios")
async def relatorios_page():
    return FileResponse("frontend/templates/relatorios.html")


@app.get("/familia")
async def familia_page():
    return FileResponse("frontend/templates/familia.html")


@app.get("/alterar-senha")
async def alterar_senha_page():
    return FileResponse("frontend/templates/alterar-senha.html")


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
