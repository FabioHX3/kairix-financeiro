"""
Rotas de Recorrencias

Endpoints para gerenciar transacoes recorrentes:
- Detectar recorrencias automaticamente
- Listar recorrencias
- Criar/editar recorrencias manualmente
- Previsao mensal
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import (
    Usuario, RecurringTransaction, ScheduledBill,
    FrequenciaRecorrencia, StatusRecorrencia, StatusConta
)
from backend.services.agents.recurrence_agent import recurrence_agent
from backend.services.agents.consultant_agent import consultant_agent

router = APIRouter(prefix="/api/recorrencias", tags=["Recorrencias"])


# ============================================================================
# SCHEMAS
# ============================================================================

class FrequenciaEnum(str, Enum):
    DIARIA = "diaria"
    SEMANAL = "semanal"
    QUINZENAL = "quinzenal"
    MENSAL = "mensal"
    BIMESTRAL = "bimestral"
    TRIMESTRAL = "trimestral"
    SEMESTRAL = "semestral"
    ANUAL = "anual"


class StatusRecorrenciaEnum(str, Enum):
    ATIVA = "ativa"
    PAUSADA = "pausada"
    CANCELADA = "cancelada"


class RecorrenciaResponse(BaseModel):
    id: int
    descricao: str
    tipo: str
    valor_medio: float
    frequencia: str
    dia_mes: Optional[int]
    categoria_nome: Optional[str]
    status: str
    ocorrencias: int
    ultima_ocorrencia: Optional[str]
    proxima_esperada: Optional[str]
    confianca: float
    auto_confirmar: bool

    class Config:
        from_attributes = True


class RecorrenciaCreate(BaseModel):
    descricao: str = Field(..., min_length=2, max_length=255)
    tipo: str = Field(..., pattern="^(receita|despesa)$")
    valor: float = Field(..., gt=0)
    frequencia: FrequenciaEnum
    dia_mes: Optional[int] = Field(None, ge=1, le=31)
    categoria_id: Optional[int] = None
    auto_confirmar: bool = False


class RecorrenciaUpdate(BaseModel):
    descricao: Optional[str] = Field(None, min_length=2, max_length=255)
    valor: Optional[float] = Field(None, gt=0)
    frequencia: Optional[FrequenciaEnum] = None
    dia_mes: Optional[int] = Field(None, ge=1, le=31)
    categoria_id: Optional[int] = None
    status: Optional[StatusRecorrenciaEnum] = None
    auto_confirmar: Optional[bool] = None


class DeteccaoResponse(BaseModel):
    descricao_padrao: str
    tipo: str
    valor_medio: float
    frequencia: str
    ocorrencias: int
    confianca: float
    proxima_esperada: Optional[str]


class PrevisaoResponse(BaseModel):
    mes: int
    ano: int
    total_despesas: float
    total_receitas: float
    saldo_previsto: float
    itens: List[dict]


# ============================================================================
# ENDPOINTS - RECORRENCIAS
# ============================================================================

@router.get("", response_model=List[RecorrenciaResponse])
async def listar_recorrencias(
    apenas_ativas: bool = True,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Lista todas as recorrencias do usuario.
    """
    recorrencias = await recurrence_agent.listar_recorrencias(
        db, usuario.id, apenas_ativas
    )
    return [RecorrenciaResponse(**r) for r in recorrencias]


@router.post("/detectar", response_model=List[DeteccaoResponse])
async def detectar_recorrencias(
    dias: int = 180,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Analisa historico e detecta possiveis recorrencias.
    Nao salva automaticamente - retorna sugestoes.
    """
    deteccoes = await recurrence_agent.analisar_historico(
        db, usuario.id, dias
    )

    return [DeteccaoResponse(
        descricao_padrao=d["descricao_padrao"],
        tipo=d["tipo"],
        valor_medio=d["valor_medio"],
        frequencia=d["frequencia"],
        ocorrencias=d["ocorrencias"],
        confianca=d["confianca"],
        proxima_esperada=d["proxima_esperada"].isoformat() if d.get("proxima_esperada") else None
    ) for d in deteccoes]


@router.post("/detectar/salvar")
async def detectar_e_salvar(
    dias: int = 180,
    confianca_minima: float = 0.6,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Detecta recorrencias e salva automaticamente as com confianca >= minima.
    """
    deteccoes = await recurrence_agent.analisar_historico(
        db, usuario.id, dias
    )

    salvos = []
    for d in deteccoes:
        if d["confianca"] >= confianca_minima:
            resultado = await recurrence_agent.registrar_recorrencia(
                db, usuario.id, d
            )
            salvos.append(resultado)

    return {
        "detectadas": len(deteccoes),
        "salvas": len(salvos),
        "itens": salvos
    }


@router.post("", response_model=RecorrenciaResponse)
async def criar_recorrencia(
    dados: RecorrenciaCreate,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Cria recorrencia manualmente.
    """
    from backend.models import TipoTransacao

    tipo_enum = TipoTransacao.DESPESA if dados.tipo == "despesa" else TipoTransacao.RECEITA
    freq_enum = FrequenciaRecorrencia(dados.frequencia.value)

    recorrencia = RecurringTransaction(
        usuario_id=usuario.id,
        categoria_id=dados.categoria_id,
        descricao_padrao=dados.descricao,
        tipo=tipo_enum,
        valor_medio=dados.valor,
        frequencia=freq_enum,
        dia_mes=dados.dia_mes,
        auto_confirmar=dados.auto_confirmar,
        detectada_automaticamente=False,
        confianca_deteccao=1.0  # Manual = confianca total
    )

    db.add(recorrencia)
    db.commit()
    db.refresh(recorrencia)

    # Busca para retornar formatado
    recorrencias = await recurrence_agent.listar_recorrencias(db, usuario.id)
    for r in recorrencias:
        if r["id"] == recorrencia.id:
            return RecorrenciaResponse(**r)

    raise HTTPException(status_code=500, detail="Erro ao criar recorrencia")


@router.put("/{recorrencia_id}", response_model=RecorrenciaResponse)
async def atualizar_recorrencia(
    recorrencia_id: int,
    dados: RecorrenciaUpdate,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Atualiza recorrencia existente.
    """
    recorrencia = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recorrencia_id,
        RecurringTransaction.usuario_id == usuario.id
    ).first()

    if not recorrencia:
        raise HTTPException(status_code=404, detail="Recorrencia nao encontrada")

    # Atualiza campos
    if dados.descricao is not None:
        recorrencia.descricao_padrao = dados.descricao
    if dados.valor is not None:
        recorrencia.valor_medio = dados.valor
    if dados.frequencia is not None:
        recorrencia.frequencia = FrequenciaRecorrencia(dados.frequencia.value)
    if dados.dia_mes is not None:
        recorrencia.dia_mes = dados.dia_mes
    if dados.categoria_id is not None:
        recorrencia.categoria_id = dados.categoria_id
    if dados.status is not None:
        recorrencia.status = StatusRecorrencia(dados.status.value)
    if dados.auto_confirmar is not None:
        recorrencia.auto_confirmar = dados.auto_confirmar

    recorrencia.atualizado_em = datetime.utcnow()
    db.commit()

    # Busca para retornar formatado
    recorrencias = await recurrence_agent.listar_recorrencias(db, usuario.id, apenas_ativas=False)
    for r in recorrencias:
        if r["id"] == recorrencia.id:
            return RecorrenciaResponse(**r)

    raise HTTPException(status_code=500, detail="Erro ao atualizar")


@router.delete("/{recorrencia_id}")
async def deletar_recorrencia(
    recorrencia_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Deleta recorrencia.
    """
    recorrencia = db.query(RecurringTransaction).filter(
        RecurringTransaction.id == recorrencia_id,
        RecurringTransaction.usuario_id == usuario.id
    ).first()

    if not recorrencia:
        raise HTTPException(status_code=404, detail="Recorrencia nao encontrada")

    db.delete(recorrencia)
    db.commit()

    return {"message": "Recorrencia deletada"}


# ============================================================================
# ENDPOINTS - PREVISAO
# ============================================================================

@router.get("/previsao", response_model=PrevisaoResponse)
async def obter_previsao(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Obtem previsao de gastos/receitas para o mes baseado em recorrencias.
    """
    previsao = await recurrence_agent.obter_previsao_mes(
        db, usuario.id, mes, ano
    )
    return PrevisaoResponse(**previsao)


# ============================================================================
# ENDPOINTS - CONSULTAS (via Consultant Agent)
# ============================================================================

@router.get("/resumo")
async def obter_resumo(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna resumo financeiro completo.
    """
    return await consultant_agent.obter_resumo_completo(db, usuario.id)


@router.get("/saldo")
async def obter_saldo(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna saldo do mes (receitas - despesas).
    """
    return await consultant_agent.obter_saldo(db, usuario.id, mes, ano)


@router.get("/categorias")
async def obter_gastos_categorias(
    mes: Optional[int] = None,
    ano: Optional[int] = None,
    tipo: str = "despesa",
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna gastos agrupados por categoria.
    """
    return await consultant_agent.obter_gastos_por_categoria(
        db, usuario.id, mes, ano, tipo
    )


@router.get("/comparativo")
async def obter_comparativo(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Compara mes atual com mes anterior.
    """
    return await consultant_agent.obter_comparativo_mensal(db, usuario.id)
