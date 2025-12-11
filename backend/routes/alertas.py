"""
Rotas de Alertas

Endpoints para gerenciar alertas proativos:
- Verificar alertas pendentes
- Executar verificacao manual
- Gerenciar configuracoes de alertas
- Visualizar jobs agendados
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario
from backend.services.agents.proactive_agent import proactive_agent
from backend.services.scheduler_service import scheduler_service

router = APIRouter(prefix="/api/alertas", tags=["Alertas"])


# ============================================================================
# SCHEMAS
# ============================================================================

class AlertaResponse(BaseModel):
    tipo: str
    mensagem: str
    urgente: bool


class VerificacaoResponse(BaseModel):
    usuario_id: int
    alertas: List[AlertaResponse]
    total: int


class JobResponse(BaseModel):
    id: str
    name: str
    next_run: Optional[str]
    trigger: str


class ContaVencerResponse(BaseModel):
    id: int
    descricao: str
    valor: float
    data_vencimento: str
    dias_restantes: int
    e_recorrente: bool
    urgente: bool


class AnomaliaResponse(BaseModel):
    categoria_id: int
    categoria: str
    icone: str
    media_historica: float
    gasto_atual: float
    percentual_acima: float
    diferenca: float


# ============================================================================
# ENDPOINTS - VERIFICACAO
# ============================================================================

@router.get("/verificar", response_model=VerificacaoResponse)
async def verificar_alertas(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Executa verificacao de alertas para o usuario atual.
    Retorna contas a vencer, anomalias detectadas, etc.
    """
    resultado = await proactive_agent.executar_verificacao_diaria(db, usuario.id)

    return VerificacaoResponse(
        usuario_id=resultado["usuario_id"],
        alertas=[AlertaResponse(**a) for a in resultado["alertas"]],
        total=resultado["total"]
    )


@router.get("/contas-vencer", response_model=List[ContaVencerResponse])
async def listar_contas_vencer(
    dias: int = 7,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Lista contas que vencem nos proximos N dias.
    """
    contas = await proactive_agent.verificar_contas_a_vencer(db, usuario.id, dias)
    return [ContaVencerResponse(**c) for c in contas]


@router.get("/contas-atrasadas", response_model=List[dict])
async def listar_contas_atrasadas(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Lista contas que ja venceram e nao foram pagas.
    """
    return await proactive_agent.verificar_contas_atrasadas(db, usuario.id)


@router.get("/anomalias", response_model=List[AnomaliaResponse])
async def listar_anomalias(
    percentual: float = 0.30,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Detecta gastos anomalos (acima da media historica).

    Args:
        percentual: Percentual acima da media para considerar anomalia (0.30 = 30%)
    """
    anomalias = await proactive_agent.detectar_gastos_anomalos(db, usuario.id, percentual)
    return [AnomaliaResponse(**a) for a in anomalias]


# ============================================================================
# ENDPOINTS - RESUMOS
# ============================================================================

@router.get("/resumo/diario")
async def obter_resumo_diario(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna resumo do dia anterior.
    """
    resumo = await proactive_agent.gerar_resumo_diario(db, usuario.id)
    return resumo


@router.get("/resumo/semanal")
async def obter_resumo_semanal(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna resumo da semana anterior.
    """
    resumo = await proactive_agent.gerar_resumo_semanal(db, usuario.id)
    return resumo


@router.get("/resumo/mensal")
async def obter_resumo_mensal(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna resumo do mes anterior.
    """
    resumo = await proactive_agent.gerar_resumo_mensal(db, usuario.id)
    return resumo


# ============================================================================
# ENDPOINTS - SCHEDULER (Admin)
# ============================================================================

@router.get("/scheduler/jobs", response_model=List[JobResponse])
async def listar_jobs(
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Lista todos os jobs agendados no scheduler.
    """
    jobs = scheduler_service.get_jobs()
    return [JobResponse(**j) for j in jobs]


@router.post("/scheduler/executar/{job_id}")
async def executar_job_manual(
    job_id: str,
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Executa um job manualmente (para testes).

    Jobs disponiveis:
    - verificacao_diaria
    - verificacao_semanal
    - verificacao_mensal
    """
    resultado = scheduler_service.executar_job_manual(job_id)

    if "erro" in resultado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=resultado["erro"]
        )

    return resultado


@router.get("/scheduler/status")
async def status_scheduler(
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Retorna status do scheduler.
    """
    is_running = (
        scheduler_service.scheduler is not None
        and scheduler_service.scheduler.running
    )

    return {
        "running": is_running,
        "initialized": scheduler_service._initialized,
        "jobs_count": len(scheduler_service.get_jobs()) if is_running else 0
    }
