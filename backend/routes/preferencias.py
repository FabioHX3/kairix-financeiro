"""
Rotas de Preferências do Usuário

Endpoints para gerenciar preferências do assistente IA:
- Personalidade (formal, amigável, divertido)
- Alertas (vencimentos, gastos anômalos)
- Resumos automáticos
- Auto-confirmação
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario, UserPreferences, PersonalidadeIA
from backend.services.agents.learning_agent import learning_agent

router = APIRouter(prefix="/api/preferencias", tags=["Preferencias"])


# ============================================================================
# SCHEMAS
# ============================================================================

class PersonalidadeEnum(str, Enum):
    FORMAL = "formal"
    AMIGAVEL = "amigavel"
    DIVERTIDO = "divertido"


class PreferenciasResponse(BaseModel):
    personalidade: str
    alertar_vencimentos: bool
    dias_antes_vencimento: int
    alertar_gastos_anomalos: bool
    limite_anomalia_percentual: int
    resumo_diario: bool
    resumo_semanal: bool
    resumo_mensal: bool
    horario_resumo: str
    auto_confirmar_confianca: float

    class Config:
        from_attributes = True


class PreferenciasUpdate(BaseModel):
    personalidade: Optional[PersonalidadeEnum] = None
    alertar_vencimentos: Optional[bool] = None
    dias_antes_vencimento: Optional[int] = Field(None, ge=1, le=30)
    alertar_gastos_anomalos: Optional[bool] = None
    limite_anomalia_percentual: Optional[int] = Field(None, ge=10, le=100)
    resumo_diario: Optional[bool] = None
    resumo_semanal: Optional[bool] = None
    resumo_mensal: Optional[bool] = None
    horario_resumo: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")
    auto_confirmar_confianca: Optional[float] = Field(None, ge=0.5, le=1.0)


class PadraoResponse(BaseModel):
    id: int
    palavras_chave: str
    tipo: str
    categoria_id: int
    categoria_nome: str
    ocorrencias: int
    confianca: float
    criado_em: str
    atualizado_em: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=PreferenciasResponse)
async def obter_preferencias(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Retorna preferências do usuário atual.
    Cria preferências padrão se não existirem.
    """
    prefs = await learning_agent.obter_preferencias(db, usuario.id)
    return PreferenciasResponse(**prefs)


@router.put("", response_model=PreferenciasResponse)
async def atualizar_preferencias(
    dados: PreferenciasUpdate,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Atualiza preferências do usuário.
    Apenas campos enviados são atualizados.
    """
    # Filtra apenas campos com valor
    dados_dict = {k: v for k, v in dados.model_dump().items() if v is not None}

    if not dados_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum campo para atualizar"
        )

    prefs = await learning_agent.atualizar_preferencias(db, usuario.id, dados_dict)
    return PreferenciasResponse(**prefs)


@router.post("/reset", response_model=PreferenciasResponse)
async def resetar_preferencias(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Reseta preferências para valores padrão.
    """
    # Deleta preferências existentes
    prefs_existente = db.query(UserPreferences).filter(
        UserPreferences.usuario_id == usuario.id
    ).first()

    if prefs_existente:
        db.delete(prefs_existente)
        db.commit()

    # Cria novas com valores padrão
    prefs = await learning_agent.criar_preferencias_padrao(db, usuario.id)
    return PreferenciasResponse(**prefs)


@router.get("/padroes", response_model=list[PadraoResponse])
async def listar_padroes(
    limite: int = 20,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Lista padrões aprendidos do usuário.
    Mostra palavras-chave mapeadas para categorias.
    """
    padroes = await learning_agent.listar_padroes_usuario(db, usuario.id, limite)
    return [PadraoResponse(**p) for p in padroes]


@router.delete("/padroes/{padrao_id}")
async def deletar_padrao(
    padrao_id: int,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Deleta um padrão específico.
    Útil quando o usuário quer "desaprender" algo.
    """
    from backend.models import UserPattern

    padrao = db.query(UserPattern).filter(
        UserPattern.id == padrao_id,
        UserPattern.usuario_id == usuario.id
    ).first()

    if not padrao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Padrão não encontrado"
        )

    db.delete(padrao)
    db.commit()

    return {"message": "Padrão deletado com sucesso"}


@router.delete("/padroes")
async def limpar_padroes(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """
    Limpa todos os padrões aprendidos.
    O assistente "esquece" tudo que aprendeu.
    """
    from backend.models import UserPattern

    deletados = db.query(UserPattern).filter(
        UserPattern.usuario_id == usuario.id
    ).delete()

    db.commit()

    return {"message": f"{deletados} padrões deletados"}
