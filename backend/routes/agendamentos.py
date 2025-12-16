from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario, Agendamento, TipoAgendamento

router = APIRouter(prefix="/api/agendamentos", tags=["Agendamentos"])


class AgendamentoCreate(BaseModel):
    tipo: str  # 'diario', 'semanal', 'mensal'
    hora: str  # HH:MM
    dia_semana: Optional[int] = None
    dia_mes: Optional[int] = None
    ativo: bool = True


class AgendamentoResposta(BaseModel):
    id: int
    usuario_id: int
    tipo: str
    hora: str
    dia_semana: Optional[int] = None
    dia_mes: Optional[int] = None
    ativo: bool
    criado_em: datetime

    class Config:
        from_attributes = True


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgendamentoResposta)
async def criar_agendamento(
    agendamento: AgendamentoCreate,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Cria um agendamento de relatório por WhatsApp"""

    if agendamento.tipo not in ['diario', 'semanal', 'mensal']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo inválido. Use: diario, semanal ou mensal"
        )

    try:
        datetime.strptime(agendamento.hora, "%H:%M")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hora inválida. Use formato HH:MM"
        )

    if agendamento.tipo == 'semanal' and agendamento.dia_semana is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dia da semana é obrigatório para agendamento semanal"
        )

    if agendamento.tipo == 'mensal' and agendamento.dia_mes is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dia do mês é obrigatório para agendamento mensal"
        )

    # Remove agendamento existente (usuário só pode ter 1)
    agendamento_existente = db.query(Agendamento).filter(
        Agendamento.usuario_id == usuario_atual.id
    ).first()

    if agendamento_existente:
        db.delete(agendamento_existente)

    # Cria novo agendamento
    tipo_enum = TipoAgendamento(agendamento.tipo)
    novo_agendamento = Agendamento(
        usuario_id=usuario_atual.id,
        tipo=tipo_enum,
        hora=agendamento.hora,
        dia_semana=agendamento.dia_semana,
        dia_mes=agendamento.dia_mes,
        ativo=agendamento.ativo
    )

    db.add(novo_agendamento)
    db.commit()
    db.refresh(novo_agendamento)

    return AgendamentoResposta(
        id=novo_agendamento.id,
        usuario_id=novo_agendamento.usuario_id,
        tipo=novo_agendamento.tipo.value,
        hora=novo_agendamento.hora,
        dia_semana=novo_agendamento.dia_semana,
        dia_mes=novo_agendamento.dia_mes,
        ativo=novo_agendamento.ativo,
        criado_em=novo_agendamento.criado_em
    )


@router.get("", response_model=Optional[AgendamentoResposta])
async def obter_agendamento(
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Obtém o agendamento do usuário"""

    agendamento = db.query(Agendamento).filter(
        Agendamento.usuario_id == usuario_atual.id
    ).first()

    if not agendamento:
        return None

    return AgendamentoResposta(
        id=agendamento.id,
        usuario_id=agendamento.usuario_id,
        tipo=agendamento.tipo.value,
        hora=agendamento.hora,
        dia_semana=agendamento.dia_semana,
        dia_mes=agendamento.dia_mes,
        ativo=agendamento.ativo,
        criado_em=agendamento.criado_em
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_agendamento(
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Remove o agendamento do usuário"""

    agendamento = db.query(Agendamento).filter(
        Agendamento.usuario_id == usuario_atual.id
    ).first()

    if agendamento:
        db.delete(agendamento)
        db.commit()

    return None


@router.put("/ativar", response_model=AgendamentoResposta)
async def ativar_agendamento(
    ativo: bool,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Ativa ou desativa o agendamento"""

    agendamento = db.query(Agendamento).filter(
        Agendamento.usuario_id == usuario_atual.id
    ).first()

    if not agendamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum agendamento encontrado"
        )

    agendamento.ativo = ativo
    db.commit()
    db.refresh(agendamento)

    return AgendamentoResposta(
        id=agendamento.id,
        usuario_id=agendamento.usuario_id,
        tipo=agendamento.tipo.value,
        hora=agendamento.hora,
        dia_semana=agendamento.dia_semana,
        dia_mes=agendamento.dia_mes,
        ativo=agendamento.ativo,
        criado_em=agendamento.criado_em
    )
