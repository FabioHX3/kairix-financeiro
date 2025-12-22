from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, date, timedelta, timezone
from typing import List, Optional

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Usuario, Transacao, Categoria, TipoTransacao, StatusTransacao
from backend.schemas import DashboardResposta, ResumoPeriodo, ResumoCategoria

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResposta)
async def obter_dashboard(
    mes: Optional[int] = Query(None, ge=1, le=12),
    ano: Optional[int] = Query(None, ge=2000),
    usuario_atual: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db)
):
    """Obtém dados completos do dashboard"""

    if not mes or not ano:
        hoje = datetime.now(timezone.utc)
        mes = mes or hoje.month
        ano = ano or hoje.year

    data_inicio = date(ano, mes, 1)

    if mes == 12:
        data_fim = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        data_fim = date(ano, mes + 1, 1) - timedelta(days=1)

    periodo = f"{ano}-{mes:02d}"

    query = db.query(Transacao).filter(
        Transacao.usuario_id == usuario_atual.id,
        Transacao.status == StatusTransacao.CONFIRMADA,
        Transacao.data_transacao >= data_inicio,
        Transacao.data_transacao <= data_fim
    )

    transacoes = query.all()

    # Resumo Geral
    total_receitas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.RECEITA)
    total_despesas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.DESPESA)
    quantidade_receitas = len([t for t in transacoes if t.tipo == TipoTransacao.RECEITA])
    quantidade_despesas = len([t for t in transacoes if t.tipo == TipoTransacao.DESPESA])

    resumo_geral = ResumoPeriodo(
        total_receitas=total_receitas,
        total_despesas=total_despesas,
        saldo=total_receitas - total_despesas,
        quantidade_receitas=quantidade_receitas,
        quantidade_despesas=quantidade_despesas
    )

    # Por Categoria
    receitas_por_categoria = _calcular_por_categoria(
        db, usuario_atual.id, TipoTransacao.RECEITA, data_inicio, data_fim, total_receitas
    )

    despesas_por_categoria = _calcular_por_categoria(
        db, usuario_atual.id, TipoTransacao.DESPESA, data_inicio, data_fim, total_despesas
    )

    # Últimas Transações
    ultimas_transacoes = db.query(Transacao).filter(
        Transacao.usuario_id == usuario_atual.id,
        Transacao.status == StatusTransacao.CONFIRMADA
    ).order_by(Transacao.data_transacao.desc()).limit(10).all()

    # Evolução Mensal
    evolucao_mensal = _calcular_evolucao_mensal(db, usuario_atual.id, mes, ano)

    return DashboardResposta(
        periodo=periodo,
        resumo_geral=resumo_geral,
        receitas_por_categoria=receitas_por_categoria,
        despesas_por_categoria=despesas_por_categoria,
        ultimas_transacoes=ultimas_transacoes,
        evolucao_mensal=evolucao_mensal
    )


def _calcular_por_categoria(
    db: Session,
    usuario_id: int,
    tipo: TipoTransacao,
    data_inicio: date,
    data_fim: date,
    total: float
) -> List[ResumoCategoria]:
    """Calcula resumo por categoria"""

    resultado = db.query(
        Categoria.id,
        Categoria.nome,
        Categoria.icone,
        Categoria.cor,
        func.sum(Transacao.valor).label("total"),
        func.count(Transacao.id).label("quantidade")
    ).join(
        Transacao, Transacao.categoria_id == Categoria.id
    ).filter(
        Transacao.usuario_id == usuario_id,
        Transacao.tipo == tipo,
        Transacao.status == StatusTransacao.CONFIRMADA,
        Transacao.data_transacao >= data_inicio,
        Transacao.data_transacao <= data_fim
    ).group_by(
        Categoria.id, Categoria.nome, Categoria.icone, Categoria.cor
    ).all()

    resumos = []
    for row in resultado:
        percentual = (row.total / total * 100) if total > 0 else 0
        resumos.append(ResumoCategoria(
            categoria_id=row.id,
            categoria_nome=row.nome,
            categoria_icone=row.icone,
            categoria_cor=row.cor,
            total=row.total,
            quantidade=row.quantidade,
            percentual=round(percentual, 2)
        ))

    resumos.sort(key=lambda x: x.total, reverse=True)

    return resumos


def _calcular_evolucao_mensal(db: Session, usuario_id: int, mes_atual: int, ano_atual: int) -> List[dict]:
    """Calcula evolução dos últimos 6 meses"""

    evolucao = []

    for i in range(5, -1, -1):
        mes = mes_atual - i
        ano = ano_atual

        while mes <= 0:
            mes += 12
            ano -= 1

        data_inicio = date(ano, mes, 1)

        if mes == 12:
            data_fim = date(ano + 1, 1, 1) - timedelta(days=1)
        else:
            data_fim = date(ano, mes + 1, 1) - timedelta(days=1)

        transacoes = db.query(Transacao).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.status == StatusTransacao.CONFIRMADA,
            Transacao.data_transacao >= data_inicio,
            Transacao.data_transacao <= data_fim
        ).all()

        total_receitas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.RECEITA)
        total_despesas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.DESPESA)

        evolucao.append({
            "mes": f"{ano}-{mes:02d}",
            "receitas": total_receitas,
            "despesas": total_despesas,
            "saldo": total_receitas - total_despesas
        })

    return evolucao
