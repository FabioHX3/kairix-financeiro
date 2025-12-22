from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional, List
from pathlib import Path

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario, Transacao, Categoria, TipoTransacao, StatusTransacao, gerar_codigo_unico
from backend.schemas import (
    TransacaoCriar, TransacaoResposta, TransacaoAtualizar, ResumoPeriodo
)

router = APIRouter(prefix="/api/transacoes", tags=["Transações"])

UPLOAD_DIR = Path("/app/uploads") if Path("/app").exists() else Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("", response_model=TransacaoResposta, status_code=status.HTTP_201_CREATED)
async def criar_transacao(
    transacao: TransacaoCriar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Cria uma nova transação"""

    if transacao.categoria_id:
        categoria = db.query(Categoria).filter(Categoria.id == transacao.categoria_id).first()
        if not categoria:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria não encontrada"
            )

        if categoria.usuario_id and categoria.usuario_id != usuario_atual.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Categoria não pertence ao usuário"
            )

    # Gera código único (com verificação no banco)
    codigo = gerar_codigo_unico(db)

    nova_transacao = Transacao(
        codigo=codigo,
        usuario_id=usuario_atual.id,
        **transacao.model_dump()
    )

    db.add(nova_transacao)
    db.commit()
    db.refresh(nova_transacao)

    return nova_transacao


@router.get("", response_model=List[TransacaoResposta])
async def listar_transacoes(
    tipo: Optional[TipoTransacao] = None,
    categoria_id: Optional[int] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=5000),
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Lista transações do usuário com filtros"""

    query = db.query(Transacao).filter(Transacao.usuario_id == usuario_atual.id)

    if tipo:
        query = query.filter(Transacao.tipo == tipo)
    if categoria_id:
        query = query.filter(Transacao.categoria_id == categoria_id)
    if data_inicio:
        query = query.filter(Transacao.data_transacao >= data_inicio)
    if data_fim:
        query = query.filter(Transacao.data_transacao <= data_fim)

    transacoes = query.order_by(Transacao.data_transacao.desc()).offset(skip).limit(limit).all()

    return transacoes


@router.get("/{transacao_id}", response_model=TransacaoResposta)
async def obter_transacao(
    transacao_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Obtém uma transação específica"""

    transacao = db.query(Transacao).filter(
        Transacao.id == transacao_id,
        Transacao.usuario_id == usuario_atual.id
    ).first()

    if not transacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transação não encontrada"
        )

    return transacao


@router.put("/{transacao_id}", response_model=TransacaoResposta)
async def atualizar_transacao(
    transacao_id: int,
    dados: TransacaoAtualizar,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Atualiza uma transação"""

    transacao = db.query(Transacao).filter(
        Transacao.id == transacao_id,
        Transacao.usuario_id == usuario_atual.id
    ).first()

    if not transacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transação não encontrada"
        )

    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(transacao, campo, valor)

    db.commit()
    db.refresh(transacao)

    return transacao


@router.delete("/{transacao_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_transacao(
    transacao_id: int,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Deleta uma transação"""

    transacao = db.query(Transacao).filter(
        Transacao.id == transacao_id,
        Transacao.usuario_id == usuario_atual.id
    ).first()

    if not transacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transação não encontrada"
        )

    db.delete(transacao)
    db.commit()

    return None


@router.get("/resumo/periodo", response_model=ResumoPeriodo)
async def obter_resumo_periodo(
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Obtém resumo financeiro de um período"""

    query = db.query(Transacao).filter(
        Transacao.usuario_id == usuario_atual.id,
        Transacao.status == StatusTransacao.CONFIRMADA
    )

    if data_inicio:
        query = query.filter(Transacao.data_transacao >= data_inicio)
    if data_fim:
        query = query.filter(Transacao.data_transacao <= data_fim)

    transacoes = query.all()

    total_receitas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.RECEITA)
    total_despesas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.DESPESA)
    quantidade_receitas = len([t for t in transacoes if t.tipo == TipoTransacao.RECEITA])
    quantidade_despesas = len([t for t in transacoes if t.tipo == TipoTransacao.DESPESA])

    return ResumoPeriodo(
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo=total_receitas - total_despesas,
        quantidade_receitas=quantidade_receitas,
        quantidade_despesas=quantidade_despesas
    )
