import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings
from backend.routes import (
    agendamentos_router,
    alertas_router,
    auth_router,
    categorias_router,
    dashboard_router,
    familia_router,
    preferencias_router,
    recorrencias_router,
    transacoes_router,
    whatsapp_router,
)

logger = logging.getLogger(__name__)

# Rate limiter global
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para adicionar headers de segurança."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Headers de segurança
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS apenas em produção (HTTPS)
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
            # CSP mais restritivo em produção
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' https://api.openrouter.ai"
            )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gerencia ciclo de vida da aplicacao."""
    # Startup
    logger.info("Kairix Financeiro API iniciando...")
    logger.info(f"Ambiente: {settings.ENVIRONMENT}")
    logger.info(f"CORS permitido: {settings.cors_origins_list}")
    logger.info("Jobs agendados são executados pelo worker arq separado")
    logger.info("Para iniciar o worker: arq backend.worker.WorkerSettings")

    yield

    # Shutdown
    logger.info("Kairix Financeiro API encerrando...")


app = FastAPI(
    title="Kairix Financeiro API",
    description="API para gestão financeira com integração WhatsApp e IA",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Security Headers Middleware (primeiro para garantir que todos os responses tenham)
app.add_middleware(SecurityHeadersMiddleware)

# CORS - restritivo baseado em configuração
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    expose_headers=["X-Total-Count"],
    max_age=600,  # Cache preflight por 10 minutos
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
@limiter.exempt
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Kairix Financeiro API"}


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Iniciando Kairix Financeiro API em http://{settings.HOST}:{settings.PORT}")

    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
