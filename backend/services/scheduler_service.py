"""
Scheduler Service - Agendamento de tarefas automaticas.

Responsabilidades:
- Executar jobs em horarios programados
- Verificar contas a vencer (diario)
- Detectar anomalias (diario)
- Enviar resumos periodicos

Usa APScheduler com BackgroundScheduler para execucao async.
"""

import logging
from datetime import datetime
from typing import Optional, Callable
from contextlib import contextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from sqlalchemy.orm import Session

from backend.core.database import SessionLocal

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Servico de agendamento de tarefas.

    Jobs configurados:
    - verificacao_diaria: Todo dia as 8h
    - verificacao_semanal: Segunda-feira as 9h
    - verificacao_mensal: Dia 1 as 10h
    """

    def __init__(self):
        self.scheduler: Optional[BackgroundScheduler] = None
        self._initialized = False
        self._send_message_callback: Optional[Callable] = None

    def set_message_callback(self, callback: Callable):
        """
        Define callback para enviar mensagens via WhatsApp.

        Args:
            callback: Funcao async que recebe (telefone, mensagem)
        """
        self._send_message_callback = callback

    @contextmanager
    def get_db(self):
        """Context manager para sessao do banco."""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def initialize(self):
        """Inicializa o scheduler com os jobs configurados."""
        if self._initialized:
            logger.info("Scheduler ja inicializado")
            return

        jobstores = {
            'default': MemoryJobStore()
        }

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            timezone='America/Sao_Paulo'
        )

        # Job diario - 8h da manha
        self.scheduler.add_job(
            self._job_verificacao_diaria,
            CronTrigger(hour=8, minute=0),
            id='verificacao_diaria',
            name='Verificacao diaria de contas e anomalias',
            replace_existing=True
        )

        # Job semanal - Segunda-feira 9h
        self.scheduler.add_job(
            self._job_verificacao_semanal,
            CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='verificacao_semanal',
            name='Resumo semanal',
            replace_existing=True
        )

        # Job mensal - Dia 1 as 10h
        self.scheduler.add_job(
            self._job_verificacao_mensal,
            CronTrigger(day=1, hour=10, minute=0),
            id='verificacao_mensal',
            name='Resumo mensal',
            replace_existing=True
        )

        self._initialized = True
        logger.info("Scheduler inicializado com sucesso")

    def start(self):
        """Inicia o scheduler."""
        if not self._initialized:
            self.initialize()

        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler iniciado")

    def stop(self):
        """Para o scheduler."""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler parado")

    def get_jobs(self):
        """Retorna lista de jobs agendados."""
        if not self.scheduler:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
        return jobs

    # =========================================================================
    # JOBS
    # =========================================================================

    def _job_verificacao_diaria(self):
        """
        Job executado diariamente.
        Verifica contas a vencer e detecta anomalias.
        """
        import asyncio
        from backend.services.agents.proactive_agent import proactive_agent
        from backend.models import Usuario

        logger.info(f"[Scheduler] Iniciando verificacao diaria - {datetime.now()}")

        with self.get_db() as db:
            # Busca todos os usuarios ativos
            usuarios = db.query(Usuario).filter(Usuario.ativo == True).all()

            for usuario in usuarios:
                try:
                    # Executa verificacao (usando asyncio.run que é thread-safe)
                    resultado = asyncio.run(
                        proactive_agent.executar_verificacao_diaria(db, usuario.id)
                    )

                    # Envia alertas via WhatsApp
                    if resultado["alertas"] and usuario.telefone:
                        self._enviar_alertas_sync(usuario.telefone, resultado["alertas"])

                    logger.info(
                        f"[Scheduler] Usuario {usuario.id}: "
                        f"{resultado['total']} alerta(s) gerado(s)"
                    )

                except Exception as e:
                    logger.error(
                        f"[Scheduler] Erro ao processar usuario {usuario.id}: {e}"
                    )

        logger.info(f"[Scheduler] Verificacao diaria concluida")

    def _job_verificacao_semanal(self):
        """
        Job executado toda segunda-feira.
        Envia resumo semanal.
        """
        import asyncio
        from backend.services.agents.proactive_agent import proactive_agent
        from backend.models import Usuario

        logger.info(f"[Scheduler] Iniciando verificacao semanal - {datetime.now()}")

        with self.get_db() as db:
            usuarios = db.query(Usuario).filter(Usuario.ativo == True).all()

            for usuario in usuarios:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    resultado = loop.run_until_complete(
                        proactive_agent.executar_verificacao_semanal(db, usuario.id)
                    )

                    loop.close()

                    if resultado and usuario.telefone:
                        self._enviar_mensagem(usuario.telefone, resultado["mensagem"])
                        logger.info(f"[Scheduler] Resumo semanal enviado para usuario {usuario.id}")

                except Exception as e:
                    logger.error(
                        f"[Scheduler] Erro ao gerar resumo semanal usuario {usuario.id}: {e}"
                    )

        logger.info(f"[Scheduler] Verificacao semanal concluida")

    def _job_verificacao_mensal(self):
        """
        Job executado todo dia 1.
        Envia resumo mensal completo.
        """
        import asyncio
        from backend.services.agents.proactive_agent import proactive_agent
        from backend.models import Usuario

        logger.info(f"[Scheduler] Iniciando verificacao mensal - {datetime.now()}")

        with self.get_db() as db:
            usuarios = db.query(Usuario).filter(Usuario.ativo == True).all()

            for usuario in usuarios:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    resultado = loop.run_until_complete(
                        proactive_agent.executar_verificacao_mensal(db, usuario.id)
                    )

                    loop.close()

                    if resultado and usuario.telefone:
                        self._enviar_mensagem(usuario.telefone, resultado["mensagem"])
                        logger.info(f"[Scheduler] Resumo mensal enviado para usuario {usuario.id}")

                except Exception as e:
                    logger.error(
                        f"[Scheduler] Erro ao gerar resumo mensal usuario {usuario.id}: {e}"
                    )

        logger.info(f"[Scheduler] Verificacao mensal concluida")

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _enviar_alertas(self, telefone: str, alertas: list):
        """
        Envia lista de alertas via WhatsApp (async version).
        """
        self._enviar_alertas_sync(telefone, alertas)

    def _enviar_alertas_sync(self, telefone: str, alertas: list):
        """
        Envia lista de alertas via WhatsApp (sync version).
        Alertas urgentes sao enviados primeiro.
        """
        # Ordena por urgencia
        alertas_ordenados = sorted(alertas, key=lambda x: x.get("urgente", False), reverse=True)

        for alerta in alertas_ordenados:
            self._enviar_mensagem_sync(telefone, alerta["mensagem"])

    def _enviar_mensagem_sync(self, telefone: str, mensagem: str):
        """
        Envia mensagem via WhatsApp usando o callback configurado (sync).
        """
        if not self._send_message_callback:
            logger.warning(
                f"[Scheduler] Callback de envio nao configurado. "
                f"Mensagem para {telefone}: {mensagem[:50]}..."
            )
            return

        try:
            # Callback já é sync (configurado em main.py)
            self._send_message_callback(telefone, mensagem)
            logger.info(f"[Scheduler] Alerta enviado para {telefone}")
        except Exception as e:
            logger.error(f"[Scheduler] Erro ao enviar mensagem: {e}")

    # =========================================================================
    # METODOS PARA EXECUCAO MANUAL (testes)
    # =========================================================================

    def executar_job_manual(self, job_id: str) -> dict:
        """
        Executa um job manualmente (para testes).

        Args:
            job_id: ID do job ('verificacao_diaria', 'verificacao_semanal', 'verificacao_mensal')

        Returns:
            Dict com resultado da execucao
        """
        jobs_map = {
            'verificacao_diaria': self._job_verificacao_diaria,
            'verificacao_semanal': self._job_verificacao_semanal,
            'verificacao_mensal': self._job_verificacao_mensal
        }

        if job_id not in jobs_map:
            return {"erro": f"Job '{job_id}' nao encontrado"}

        try:
            jobs_map[job_id]()
            return {"sucesso": True, "job": job_id, "executado_em": datetime.now().isoformat()}
        except Exception as e:
            return {"erro": str(e), "job": job_id}

    async def executar_verificacao_usuario(self, db: Session, usuario_id: int) -> dict:
        """
        Executa verificacao para um usuario especifico (testes via API).

        Returns:
            Dict com alertas gerados
        """
        from backend.services.agents.proactive_agent import proactive_agent

        return await proactive_agent.executar_verificacao_diaria(db, usuario_id)


# Instancia global
scheduler_service = SchedulerService()
