from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario

router = APIRouter(prefix="/api/agendamentos", tags=["Agendamentos"])


class AgendamentoRelatorio(BaseModel):
    tipo: str  # 'diario', 'semanal', 'mensal'
    hora: str  # HH:MM
    dia_semana: Optional[int] = None
    dia_mes: Optional[int] = None
    ativo: bool = True


class AgendamentoResposta(AgendamentoRelatorio):
    id: int
    usuario_id: int
    criado_em: datetime

    class Config:
        from_attributes = True


# TODO: Mover para banco de dados
agendamentos_memoria = {}


@router.post("", status_code=status.HTTP_201_CREATED)
async def criar_agendamento(
    agendamento: AgendamentoRelatorio,
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

    if usuario_atual.id in agendamentos_memoria:
        del agendamentos_memoria[usuario_atual.id]

    novo_agendamento = {
        "id": usuario_atual.id,
        "usuario_id": usuario_atual.id,
        "tipo": agendamento.tipo,
        "hora": agendamento.hora,
        "dia_semana": agendamento.dia_semana,
        "dia_mes": agendamento.dia_mes,
        "ativo": agendamento.ativo,
        "criado_em": datetime.utcnow()
    }

    agendamentos_memoria[usuario_atual.id] = novo_agendamento

    return novo_agendamento


@router.get("", response_model=Optional[AgendamentoResposta])
async def obter_agendamento(
    usuario_atual: Usuario = Depends(obter_usuario_atual)
):
    """Obtém o agendamento do usuário"""

    if usuario_atual.id in agendamentos_memoria:
        return agendamentos_memoria[usuario_atual.id]

    return None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_agendamento(
    usuario_atual: Usuario = Depends(obter_usuario_atual)
):
    """Remove o agendamento do usuário"""

    if usuario_atual.id in agendamentos_memoria:
        del agendamentos_memoria[usuario_atual.id]

    return None


@router.put("/ativar")
async def ativar_agendamento(
    ativo: bool,
    usuario_atual: Usuario = Depends(obter_usuario_atual)
):
    """Ativa ou desativa o agendamento"""

    if usuario_atual.id not in agendamentos_memoria:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhum agendamento encontrado"
        )

    agendamentos_memoria[usuario_atual.id]["ativo"] = ativo

    return agendamentos_memoria[usuario_atual.id]
