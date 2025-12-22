"""
Arq Worker - Task Queue assíncrono.

Responsabilidades:
- Executar jobs agendados (cron)
- Verificar contas a vencer (diário às 8h)
- Enviar resumo semanal (segunda às 9h)
- Enviar resumo mensal (dia 1 às 10h)

Para rodar o worker:
    arq backend.worker.WorkerSettings

Para rodar com hot-reload (dev):
    arq backend.worker.WorkerSettings --watch backend
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from arq import cron
from arq.connections import RedisSettings

from backend.config import settings
from backend.core.database import SessionLocal

# Timezone São Paulo
SAO_PAULO_TZ = ZoneInfo("America/Sao_Paulo")

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS
# =============================================================================

def get_db():
    """Retorna sessão do banco de dados."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def parse_redis_url(url: str) -> RedisSettings:
    """Converte URL Redis para RedisSettings do arq."""
    from urllib.parse import urlparse

    parsed = urlparse(url)

    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=int(parsed.path.lstrip("/") or 0),
        password=parsed.password,
    )


# =============================================================================
# JOBS
# =============================================================================

async def job_verificacao_diaria(ctx: dict) -> dict:
    """
    Job executado diariamente às 8h.
    Verifica contas a vencer e detecta anomalias.
    """
    from backend.models import Usuario
    from backend.services.agents.proactive_agent import proactive_agent
    from backend.services.whatsapp import whatsapp_service

    logger.info(f"[Worker] Iniciando verificação diária - {datetime.now(SAO_PAULO_TZ)}")

    db = get_db()
    resultados = {"usuarios_processados": 0, "alertas_enviados": 0, "erros": 0}

    try:
        usuarios = db.query(Usuario).filter(Usuario.ativo == True).all()

        for usuario in usuarios:
            try:
                resultado = await proactive_agent.executar_verificacao_diaria(
                    db, usuario.id
                )

                if resultado["alertas"] and usuario.telefone:
                    for alerta in resultado["alertas"]:
                        await whatsapp_service.enviar_mensagem(
                            usuario.telefone,
                            alerta["mensagem"]
                        )
                        resultados["alertas_enviados"] += 1

                resultados["usuarios_processados"] += 1
                logger.info(
                    f"[Worker] Usuário {usuario.id}: "
                    f"{resultado['total']} alerta(s) gerado(s)"
                )

            except Exception as e:
                resultados["erros"] += 1
                logger.error(
                    f"[Worker] Erro ao processar usuário {usuario.id}: {e}"
                )
    finally:
        db.close()

    logger.info(f"[Worker] Verificação diária concluída: {resultados}")
    return resultados


async def job_verificacao_semanal(ctx: dict) -> dict:
    """
    Job executado toda segunda-feira às 9h.
    Envia resumo semanal.
    """
    from backend.models import Usuario
    from backend.services.agents.proactive_agent import proactive_agent
    from backend.services.whatsapp import whatsapp_service

    logger.info(f"[Worker] Iniciando verificação semanal - {datetime.now(SAO_PAULO_TZ)}")

    db = get_db()
    resultados = {"usuarios_processados": 0, "resumos_enviados": 0, "erros": 0}

    try:
        usuarios = db.query(Usuario).filter(Usuario.ativo == True).all()

        for usuario in usuarios:
            try:
                resultado = await proactive_agent.executar_verificacao_semanal(
                    db, usuario.id
                )

                if resultado and usuario.telefone:
                    await whatsapp_service.enviar_mensagem(
                        usuario.telefone,
                        resultado["mensagem"]
                    )
                    resultados["resumos_enviados"] += 1
                    logger.info(
                        f"[Worker] Resumo semanal enviado para usuário {usuario.id}"
                    )

                resultados["usuarios_processados"] += 1

            except Exception as e:
                resultados["erros"] += 1
                logger.error(
                    f"[Worker] Erro ao gerar resumo semanal usuário {usuario.id}: {e}"
                )
    finally:
        db.close()

    logger.info(f"[Worker] Verificação semanal concluída: {resultados}")
    return resultados


async def job_verificacao_mensal(ctx: dict) -> dict:
    """
    Job executado todo dia 1 às 10h.
    Envia resumo mensal completo.
    """
    from backend.models import Usuario
    from backend.services.agents.proactive_agent import proactive_agent
    from backend.services.whatsapp import whatsapp_service

    logger.info(f"[Worker] Iniciando verificação mensal - {datetime.now(SAO_PAULO_TZ)}")

    db = get_db()
    resultados = {"usuarios_processados": 0, "resumos_enviados": 0, "erros": 0}

    try:
        usuarios = db.query(Usuario).filter(Usuario.ativo == True).all()

        for usuario in usuarios:
            try:
                resultado = await proactive_agent.executar_verificacao_mensal(
                    db, usuario.id
                )

                if resultado and usuario.telefone:
                    await whatsapp_service.enviar_mensagem(
                        usuario.telefone,
                        resultado["mensagem"]
                    )
                    resultados["resumos_enviados"] += 1
                    logger.info(
                        f"[Worker] Resumo mensal enviado para usuário {usuario.id}"
                    )

                resultados["usuarios_processados"] += 1

            except Exception as e:
                resultados["erros"] += 1
                logger.error(
                    f"[Worker] Erro ao gerar resumo mensal usuário {usuario.id}: {e}"
                )
    finally:
        db.close()

    logger.info(f"[Worker] Verificação mensal concluída: {resultados}")
    return resultados


async def job_verificacao_usuario(ctx: dict, usuario_id: int) -> dict:
    """
    Job para verificação sob demanda de um usuário específico.
    Pode ser enfileirado via API.
    """
    from backend.services.agents.proactive_agent import proactive_agent
    from backend.services.whatsapp import whatsapp_service
    from backend.models import Usuario

    logger.info(f"[Worker] Verificação sob demanda para usuário {usuario_id}")

    db = get_db()

    try:
        usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()

        if not usuario:
            return {"erro": "Usuário não encontrado"}

        resultado = await proactive_agent.executar_verificacao_diaria(
            db, usuario_id
        )

        if resultado["alertas"] and usuario.telefone:
            for alerta in resultado["alertas"]:
                await whatsapp_service.enviar_mensagem(
                    usuario.telefone,
                    alerta["mensagem"]
                )

        return {
            "usuario_id": usuario_id,
            "alertas_enviados": len(resultado["alertas"]),
            "sucesso": True
        }

    finally:
        db.close()


# =============================================================================
# STARTUP/SHUTDOWN
# =============================================================================

async def startup(ctx: dict):
    """Executado quando o worker inicia."""
    logger.info("[Worker] Iniciando worker arq...")
    logger.info(f"[Worker] Timezone: America/Sao_Paulo")
    logger.info("[Worker] Jobs agendados:")
    logger.info("  - verificacao_diaria: diariamente às 8h")
    logger.info("  - verificacao_semanal: segunda-feira às 9h")
    logger.info("  - verificacao_mensal: dia 1 às 10h")


async def shutdown(ctx: dict):
    """Executado quando o worker para."""
    logger.info("[Worker] Encerrando worker arq...")


# =============================================================================
# CONFIGURAÇÃO DO WORKER
# =============================================================================

class WorkerSettings:
    """Configurações do worker arq."""

    # Conexão Redis
    redis_settings = parse_redis_url(settings.REDIS_URL)

    # Funções de lifecycle
    on_startup = startup
    on_shutdown = shutdown

    # Jobs disponíveis para enfileiramento manual
    functions = [
        job_verificacao_diaria,
        job_verificacao_semanal,
        job_verificacao_mensal,
        job_verificacao_usuario,
    ]

    # Jobs agendados (cron)
    cron_jobs = [
        # Diário às 8h (horário de São Paulo)
        cron(
            job_verificacao_diaria,
            hour=8,
            minute=0,
            timeout=300,  # 5 min timeout
        ),
        # Segunda-feira às 9h
        cron(
            job_verificacao_semanal,
            weekday=0,  # 0 = segunda
            hour=9,
            minute=0,
            timeout=600,  # 10 min timeout
        ),
        # Dia 1 às 10h
        cron(
            job_verificacao_mensal,
            day=1,
            hour=10,
            minute=0,
            timeout=600,  # 10 min timeout
        ),
    ]

    # Timezone
    timezone = SAO_PAULO_TZ

    # Retry policy
    max_tries = 3
    retry_delay = 60  # 1 minuto entre retries

    # Health check
    health_check_interval = 60
