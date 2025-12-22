"""
Consultant Agent - Responde consultas do usuario.

Responsabilidades:
- Consultar saldo atual
- Gastos por categoria
- Comparativos (mes atual vs anterior)
- Ultimas transacoes
- Recorrencias e previsoes
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from backend.services.agents.base_agent import (
    BaseAgent,
    AgentContext,
    AgentResponse,
    IntentType
)
from backend.utils import fmt_valor


class ConsultantAgent(BaseAgent):
    """
    Agente consultor - responde perguntas sobre financas do usuario.

    Consultas suportadas:
    - Saldo (receitas - despesas)
    - Gastos por categoria
    - Gastos do mes
    - Ultimas transacoes
    - Comparativos
    - Recorrencias
    """

    name = "consultant"
    description = "Responde consultas financeiras"

    def can_handle(self, context: AgentContext) -> bool:
        """Pode processar consultas"""
        return context.intent == IntentType.CONSULTAR

    async def process(self, context: AgentContext) -> AgentResponse:
        """
        Processa consulta do usuario.
        Por enquanto retorna placeholder - sera expandido.
        """
        return AgentResponse(
            sucesso=True,
            mensagem="Consultas serao implementadas em breve!",
            dados={}
        )

    async def obter_saldo(
        self,
        db: Session,
        usuario_id: int,
        mes: int = None,
        ano: int = None
    ) -> Dict:
        """
        Calcula saldo do usuario (receitas - despesas).

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            mes: Mes especifico (None = mes atual)
            ano: Ano especifico (None = ano atual)

        Returns:
            Dict com total_receitas, total_despesas, saldo
        """
        from backend.models import Transacao, TipoTransacao

        if mes is None:
            mes = datetime.now(timezone.utc).month
        if ano is None:
            ano = datetime.now(timezone.utc).year

        # Query base
        query = db.query(
            Transacao.tipo,
            func.sum(Transacao.valor).label('total')
        ).filter(
            Transacao.usuario_id == usuario_id,
            extract('month', Transacao.data_transacao) == mes,
            extract('year', Transacao.data_transacao) == ano,
            Transacao.status != 'cancelada'
        ).group_by(Transacao.tipo)

        resultados = query.all()

        total_receitas = 0
        total_despesas = 0

        for tipo, total in resultados:
            if tipo == TipoTransacao.RECEITA:
                total_receitas = float(total or 0)
            else:
                total_despesas = float(total or 0)

        return {
            "mes": mes,
            "ano": ano,
            "total_receitas": round(total_receitas, 2),
            "total_despesas": round(total_despesas, 2),
            "saldo": round(total_receitas - total_despesas, 2)
        }

    async def obter_gastos_por_categoria(
        self,
        db: Session,
        usuario_id: int,
        mes: int = None,
        ano: int = None,
        tipo: str = "despesa"
    ) -> List[Dict]:
        """
        Retorna gastos agrupados por categoria.

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            mes: Mes (None = atual)
            ano: Ano (None = atual)
            tipo: 'despesa' ou 'receita'

        Returns:
            Lista de categorias com totais
        """
        from backend.models import Transacao, Categoria, TipoTransacao

        if mes is None:
            mes = datetime.now(timezone.utc).month
        if ano is None:
            ano = datetime.now(timezone.utc).year

        tipo_enum = TipoTransacao.DESPESA if tipo == "despesa" else TipoTransacao.RECEITA

        query = db.query(
            Categoria.nome,
            Categoria.icone,
            Categoria.cor,
            func.sum(Transacao.valor).label('total'),
            func.count(Transacao.id).label('quantidade')
        ).join(
            Transacao, Transacao.categoria_id == Categoria.id
        ).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.tipo == tipo_enum,
            extract('month', Transacao.data_transacao) == mes,
            extract('year', Transacao.data_transacao) == ano,
            Transacao.status != 'cancelada'
        ).group_by(
            Categoria.id, Categoria.nome, Categoria.icone, Categoria.cor
        ).order_by(func.sum(Transacao.valor).desc())

        resultados = query.all()

        total_geral = sum(r.total for r in resultados) if resultados else 0

        return [{
            "categoria": r.nome,
            "icone": r.icone,
            "cor": r.cor,
            "total": round(float(r.total), 2),
            "quantidade": r.quantidade,
            "percentual": round((float(r.total) / total_geral * 100) if total_geral > 0 else 0, 1)
        } for r in resultados]

    async def obter_ultimas_transacoes(
        self,
        db: Session,
        usuario_id: int,
        limite: int = 10
    ) -> List[Dict]:
        """
        Retorna ultimas transacoes do usuario.

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            limite: Quantidade maxima

        Returns:
            Lista de transacoes
        """
        from backend.models import Transacao, Categoria

        transacoes = db.query(Transacao).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.status != 'cancelada'
        ).order_by(Transacao.data_transacao.desc()).limit(limite).all()

        resultado = []
        for t in transacoes:
            categoria = db.query(Categoria).filter(Categoria.id == t.categoria_id).first()

            resultado.append({
                "codigo": t.codigo,
                "tipo": t.tipo.value,
                "valor": t.valor,
                "descricao": t.descricao,
                "categoria": categoria.nome if categoria else "Outros",
                "categoria_icone": categoria.icone if categoria else "📌",
                "data": t.data_transacao.strftime("%d/%m/%Y"),
                "origem": t.origem.value
            })

        return resultado

    async def obter_comparativo_mensal(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Compara mes atual com mes anterior.

        Returns:
            Dict com dados de ambos os meses e variacao
        """
        hoje = datetime.now(timezone.utc)
        mes_atual = hoje.month
        ano_atual = hoje.year

        # Calcula mes anterior
        if mes_atual == 1:
            mes_anterior = 12
            ano_anterior = ano_atual - 1
        else:
            mes_anterior = mes_atual - 1
            ano_anterior = ano_atual

        # Busca dados
        atual = await self.obter_saldo(db, usuario_id, mes_atual, ano_atual)
        anterior = await self.obter_saldo(db, usuario_id, mes_anterior, ano_anterior)

        # Calcula variacoes
        def calc_variacao(atual_val, anterior_val):
            if anterior_val == 0:
                return 100 if atual_val > 0 else 0
            return round((atual_val - anterior_val) / abs(anterior_val) * 100, 1)

        return {
            "mes_atual": {
                "mes": mes_atual,
                "ano": ano_atual,
                **atual
            },
            "mes_anterior": {
                "mes": mes_anterior,
                "ano": ano_anterior,
                **anterior
            },
            "variacao": {
                "receitas": calc_variacao(atual["total_receitas"], anterior["total_receitas"]),
                "despesas": calc_variacao(atual["total_despesas"], anterior["total_despesas"]),
                "saldo": calc_variacao(atual["saldo"], anterior["saldo"])
            }
        }

    async def obter_resumo_completo(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Retorna resumo completo das financas.

        Returns:
            Dict com saldo, categorias, ultimas transacoes, comparativo
        """
        saldo = await self.obter_saldo(db, usuario_id)
        categorias = await self.obter_gastos_por_categoria(db, usuario_id)
        ultimas = await self.obter_ultimas_transacoes(db, usuario_id, limite=5)
        comparativo = await self.obter_comparativo_mensal(db, usuario_id)

        return {
            "saldo_atual": saldo,
            "gastos_por_categoria": categorias[:5],  # Top 5
            "ultimas_transacoes": ultimas,
            "comparativo_mensal": comparativo
        }

    def formatar_resumo_texto(
        self,
        resumo: Dict,
        personalidade: str = "amigavel"
    ) -> str:
        """
        Formata resumo em texto para WhatsApp.

        Args:
            resumo: Dict com dados do resumo
            personalidade: Estilo de comunicacao

        Returns:
            Texto formatado
        """
        saldo = resumo["saldo_atual"]
        categorias = resumo["gastos_por_categoria"]
        comparativo = resumo["comparativo_mensal"]

        if personalidade == "formal":
            msg = f"Resumo Financeiro - {saldo['mes']:02d}/{saldo['ano']}\n\n"
            msg += f"Receitas: {fmt_valor(saldo['total_receitas'])}\n"
            msg += f"Despesas: {fmt_valor(saldo['total_despesas'])}\n"
            msg += f"Saldo: {fmt_valor(saldo['saldo'])}\n"

        elif personalidade == "divertido":
            emoji_saldo = "🤑" if saldo['saldo'] >= 0 else "😰"
            msg = f"Suas financas de {saldo['mes']:02d}/{saldo['ano']}! {emoji_saldo}\n\n"
            msg += f"💰 Entrou: {fmt_valor(saldo['total_receitas'])}\n"
            msg += f"💸 Saiu: {fmt_valor(saldo['total_despesas'])}\n"
            msg += f"📊 Sobrou: {fmt_valor(saldo['saldo'])}\n"

        else:  # amigavel
            msg = f"Resumo de {saldo['mes']:02d}/{saldo['ano']}\n\n"
            msg += f"Receitas: {fmt_valor(saldo['total_receitas'])}\n"
            msg += f"Despesas: {fmt_valor(saldo['total_despesas'])}\n"
            msg += f"Saldo: {fmt_valor(saldo['saldo'])}\n"

        # Adiciona top categorias
        if categorias:
            msg += "\nPrincipais gastos:\n"
            for cat in categorias[:3]:
                msg += f"{cat['icone']} {cat['categoria']}: {fmt_valor(cat['total'])} ({cat['percentual']}%)\n"

        # Adiciona comparativo
        var = comparativo["variacao"]
        if var["despesas"] != 0:
            emoji_var = "📈" if var["despesas"] > 0 else "📉"
            msg += f"\n{emoji_var} Despesas: {'+' if var['despesas'] > 0 else ''}{var['despesas']}% vs mes anterior"

        return msg

    async def buscar_transacao_por_codigo(
        self,
        db: Session,
        usuario_id: int,
        codigo: str
    ) -> Optional[Dict]:
        """
        Busca transacao pelo codigo.

        Returns:
            Dict com dados da transacao ou None
        """
        from backend.models import Transacao, Categoria

        transacao = db.query(Transacao).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.codigo == codigo.upper()
        ).first()

        if not transacao:
            return None

        categoria = db.query(Categoria).filter(
            Categoria.id == transacao.categoria_id
        ).first()

        return {
            "codigo": transacao.codigo,
            "tipo": transacao.tipo.value,
            "valor": transacao.valor,
            "descricao": transacao.descricao,
            "categoria": categoria.nome if categoria else "Outros",
            "data": transacao.data_transacao.strftime("%d/%m/%Y"),
            "origem": transacao.origem.value,
            "status": transacao.status.value,
            "criado_em": transacao.criado_em.strftime("%d/%m/%Y %H:%M")
        }


# Instancia global
consultant_agent = ConsultantAgent()
