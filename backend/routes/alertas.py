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
from datetime import datetime, timezone

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario
from backend.services.agents.proactive_agent import proactive_agent
from backend.services.queue_service import queue_service

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
# ENDPOINTS - QUEUE (Jobs)
# ============================================================================

@router.post("/queue/verificar-usuario")
async def enqueue_verificacao_usuario(
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Enfileira verificação de alertas para o usuário atual.
    O job será processado pelo worker arq.
    """
    resultado = await queue_service.enqueue_verificacao_usuario(usuario.id)
    return resultado


@router.post("/queue/executar/{job_id}")
async def enqueue_job_manual(
    job_id: str,
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Enfileira um job manualmente.

    Jobs disponiveis:
    - verificacao_diaria: Executa verificação para todos os usuários
    - verificacao_semanal: Envia resumo semanal
    - verificacao_mensal: Envia resumo mensal
    - verificacao_usuario: Executa apenas para o usuário atual
    """
    jobs_map = {
        "verificacao_diaria": queue_service.enqueue_verificacao_diaria,
        "verificacao_semanal": queue_service.enqueue_verificacao_semanal,
        "verificacao_mensal": queue_service.enqueue_verificacao_mensal,
        "verificacao_usuario": lambda: queue_service.enqueue_verificacao_usuario(usuario.id),
    }

    if job_id not in jobs_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' não encontrado. Jobs disponíveis: {list(jobs_map.keys())}"
        )

    resultado = await jobs_map[job_id]()
    return resultado


@router.get("/queue/job/{job_id}")
async def get_job_status(
    job_id: str,
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Consulta status de um job específico.
    """
    info = await queue_service.get_job_info(job_id)

    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job não encontrado ou já expirou"
        )

    return info


@router.get("/queue/status")
async def status_queue(
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """
    Retorna status da fila de jobs.
    """
    return await queue_service.get_queue_info()


# ============================================================================
# ENDPOINTS - EXECUÇÃO DIRETA (sem fila, para testes)
# ============================================================================

@router.post("/executar-agora")
async def executar_verificacao_agora(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Executa verificação de alertas IMEDIATAMENTE (sem passar pela fila).
    Útil para testes e debug.
    """
    from backend.services.whatsapp import whatsapp_service

    resultado = await proactive_agent.executar_verificacao_diaria(db, usuario.id)

    if resultado["alertas"] and usuario.telefone:
        for alerta in resultado["alertas"]:
            await whatsapp_service.enviar_mensagem(usuario.telefone, alerta["mensagem"])

    return {
        "sucesso": True,
        "alertas_enviados": len(resultado["alertas"]),
        "alertas": resultado["alertas"],
        "executado_em": datetime.now(timezone.utc).isoformat()
    }
