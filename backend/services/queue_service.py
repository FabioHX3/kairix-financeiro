"""
Queue Service - Interface para enfileirar jobs no arq.

Responsabilidades:
- Enfileirar jobs sob demanda
- Consultar status dos jobs
- Interface para a API interagir com o worker
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from arq import create_pool
from arq.connections import RedisSettings

from backend.config import settings

logger = logging.getLogger(__name__)


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


class QueueService:
    """Serviço para interagir com a fila arq."""

    def __init__(self):
        self._pool = None
        self._redis_settings = parse_redis_url(settings.REDIS_URL)

    async def get_pool(self):
        """Retorna pool de conexões Redis."""
        if self._pool is None:
            self._pool = await create_pool(self._redis_settings)
        return self._pool

    async def close(self):
        """Fecha pool de conexões."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def enqueue_verificacao_usuario(self, usuario_id: int) -> Dict[str, Any]:
        """
        Enfileira verificação para um usuário específico.

        Args:
            usuario_id: ID do usuário

        Returns:
            Dict com job_id e status
        """
        try:
            pool = await self.get_pool()
            job = await pool.enqueue_job(
                "job_verificacao_usuario",
                usuario_id,
            )

            logger.info(f"[Queue] Job verificação enfileirado para usuário {usuario_id}")

            return {
                "job_id": job.job_id,
                "usuario_id": usuario_id,
                "status": "enqueued",
                "enqueued_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Queue] Erro ao enfileirar job: {e}")
            return {
                "erro": str(e),
                "usuario_id": usuario_id,
                "status": "error"
            }

    async def enqueue_verificacao_diaria(self) -> Dict[str, Any]:
        """Enfileira job de verificação diária manualmente."""
        try:
            pool = await self.get_pool()
            job = await pool.enqueue_job("job_verificacao_diaria")

            logger.info("[Queue] Job verificação diária enfileirado")

            return {
                "job_id": job.job_id,
                "tipo": "verificacao_diaria",
                "status": "enqueued",
                "enqueued_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Queue] Erro ao enfileirar job: {e}")
            return {"erro": str(e), "status": "error"}

    async def enqueue_verificacao_semanal(self) -> Dict[str, Any]:
        """Enfileira job de verificação semanal manualmente."""
        try:
            pool = await self.get_pool()
            job = await pool.enqueue_job("job_verificacao_semanal")

            logger.info("[Queue] Job verificação semanal enfileirado")

            return {
                "job_id": job.job_id,
                "tipo": "verificacao_semanal",
                "status": "enqueued",
                "enqueued_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Queue] Erro ao enfileirar job: {e}")
            return {"erro": str(e), "status": "error"}

    async def enqueue_verificacao_mensal(self) -> Dict[str, Any]:
        """Enfileira job de verificação mensal manualmente."""
        try:
            pool = await self.get_pool()
            job = await pool.enqueue_job("job_verificacao_mensal")

            logger.info("[Queue] Job verificação mensal enfileirado")

            return {
                "job_id": job.job_id,
                "tipo": "verificacao_mensal",
                "status": "enqueued",
                "enqueued_at": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Queue] Erro ao enfileirar job: {e}")
            return {"erro": str(e), "status": "error"}

    async def get_job_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca informações de um job.

        Args:
            job_id: ID do job

        Returns:
            Dict com informações do job ou None
        """
        try:
            from arq.jobs import Job

            pool = await self.get_pool()
            job = Job(job_id, pool)
            info = await job.info()

            if info is None:
                return None

            return {
                "job_id": job_id,
                "function": info.function,
                "args": info.args,
                "kwargs": info.kwargs,
                "enqueue_time": info.enqueue_time.isoformat() if info.enqueue_time else None,
                "start_time": info.start_time.isoformat() if info.start_time else None,
                "finish_time": info.finish_time.isoformat() if info.finish_time else None,
                "success": info.success,
                "result": info.result,
            }

        except Exception as e:
            logger.error(f"[Queue] Erro ao buscar job {job_id}: {e}")
            return None

    async def get_queue_info(self) -> Dict[str, Any]:
        """
        Retorna informações sobre a fila.

        Returns:
            Dict com estatísticas da fila
        """
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(settings.REDIS_URL)

            # Busca chaves da fila arq (fila padrão)
            queue_key = "arq:queue"

            queue_len = await r.llen(queue_key)

            await r.close()

            return {
                "queue_name": "default",
                "pending_jobs": queue_len,
                "redis_connected": True,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"[Queue] Erro ao consultar fila: {e}")
            return {
                "redis_connected": False,
                "erro": str(e)
            }


# Instância global
queue_service = QueueService()
