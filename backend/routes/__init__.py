from backend.routes.agendamentos import router as agendamentos_router
from backend.routes.alertas import router as alertas_router
from backend.routes.auth import router as auth_router
from backend.routes.categorias import router as categorias_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.familia import router as familia_router
from backend.routes.preferencias import router as preferencias_router
from backend.routes.recorrencias import router as recorrencias_router
from backend.routes.transacoes import router as transacoes_router
from backend.routes.whatsapp import router as whatsapp_router

__all__ = [
    "agendamentos_router",
    "alertas_router",
    "auth_router",
    "categorias_router",
    "dashboard_router",
    "familia_router",
    "preferencias_router",
    "recorrencias_router",
    "transacoes_router",
    "whatsapp_router",
]
