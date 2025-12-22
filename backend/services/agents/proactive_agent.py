"""
Proactive Agent - Alertas automaticos e proativos.

Responsabilidades:
- Alertar sobre contas a vencer (3 dias antes, no dia)
- Detectar gastos anomalos (30% acima da media)
- Gerar resumos periodicos (diario, semanal, mensal)
- Enviar notificacoes via WhatsApp
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_

from backend.services.agents.base_agent import (
    BaseAgent,
    AgentContext,
    AgentResponse,
    IntentType
)
from backend.utils import fmt_valor


class ProactiveAgent(BaseAgent):
    """
    Agente proativo - envia alertas automaticos.

    Alertas suportados:
    - Contas a vencer (3 dias antes, no dia)
    - Gastos anomalos (30% acima da media)
    - Resumos periodicos
    """

    name = "proactive"
    description = "Envia alertas automaticos e proativos"

    # Configuracoes padrao
    DIAS_ANTECEDENCIA_ALERTA = 3
    PERCENTUAL_ANOMALIA = 0.30  # 30%

    def can_handle(self, context: AgentContext) -> bool:
        """Proactive agent nao processa mensagens diretamente"""
        return False

    async def process(self, context: AgentContext) -> AgentResponse:
        """Nao processa mensagens - apenas executa jobs"""
        return AgentResponse(
            sucesso=False,
            mensagem="Proactive agent nao processa mensagens diretamente",
            dados={}
        )

    # =========================================================================
    # ALERTAS DE CONTAS A VENCER
    # =========================================================================

    async def verificar_contas_a_vencer(
        self,
        db: Session,
        usuario_id: int,
        dias_antecedencia: int = 3
    ) -> List[Dict]:
        """
        Busca contas que vencem nos proximos N dias.

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            dias_antecedencia: Dias para alertar antes

        Returns:
            Lista de contas a vencer
        """
        from backend.models import ScheduledBill, StatusConta

        hoje = datetime.now(timezone.utc).date()
        data_limite = hoje + timedelta(days=dias_antecedencia)

        contas = db.query(ScheduledBill).filter(
            ScheduledBill.usuario_id == usuario_id,
            ScheduledBill.status == StatusConta.PENDENTE,
            ScheduledBill.data_vencimento >= hoje,
            ScheduledBill.data_vencimento <= data_limite
        ).order_by(ScheduledBill.data_vencimento).all()

        resultado = []
        for conta in contas:
            # Converte datetime para date se necessário
            data_venc = conta.data_vencimento.date() if hasattr(conta.data_vencimento, 'date') else conta.data_vencimento
            dias_restantes = (data_venc - hoje).days

            resultado.append({
                "id": conta.id,
                "descricao": conta.descricao,
                "valor": float(conta.valor),
                "data_vencimento": conta.data_vencimento.strftime("%d/%m/%Y"),
                "dias_restantes": dias_restantes,
                "e_recorrente": conta.recorrencia_id is not None,
                "urgente": dias_restantes == 0
            })

        return resultado

    async def verificar_contas_atrasadas(
        self,
        db: Session,
        usuario_id: int
    ) -> List[Dict]:
        """
        Busca contas que ja venceram e nao foram pagas.

        Returns:
            Lista de contas atrasadas
        """
        from backend.models import ScheduledBill, StatusConta

        hoje = datetime.now(timezone.utc).date()

        contas = db.query(ScheduledBill).filter(
            ScheduledBill.usuario_id == usuario_id,
            ScheduledBill.status == StatusConta.PENDENTE,
            ScheduledBill.data_vencimento < hoje
        ).order_by(ScheduledBill.data_vencimento).all()

        resultado = []
        for conta in contas:
            dias_atraso = (hoje - conta.data_vencimento).days

            # Atualiza status para atrasada
            conta.status = StatusConta.ATRASADA
            db.commit()

            resultado.append({
                "id": conta.id,
                "descricao": conta.descricao,
                "valor": float(conta.valor),
                "data_vencimento": conta.data_vencimento.strftime("%d/%m/%Y"),
                "dias_atraso": dias_atraso
            })

        return resultado

    def formatar_alerta_contas(
        self,
        contas_vencer: List[Dict],
        contas_atrasadas: List[Dict],
        personalidade: str = "amigavel"
    ) -> Optional[str]:
        """
        Formata mensagem de alerta de contas.

        Returns:
            Mensagem formatada ou None se nao houver alertas
        """
        if not contas_vencer and not contas_atrasadas:
            return None

        msg_parts = []

        # Contas atrasadas (prioridade)
        if contas_atrasadas:
            if personalidade == "formal":
                msg_parts.append("ATENÇÃO - Contas em atraso:")
            elif personalidade == "divertido":
                msg_parts.append("🚨 Eita! Tem conta atrasada:")
            else:
                msg_parts.append("⚠️ Contas atrasadas:")

            for conta in contas_atrasadas:
                msg_parts.append(
                    f"  • {conta['descricao']}: {fmt_valor(conta['valor'])} "
                    f"(venceu há {conta['dias_atraso']} dia(s))"
                )

        # Contas a vencer
        if contas_vencer:
            if msg_parts:
                msg_parts.append("")

            # Separa urgentes (hoje) das proximas
            urgentes = [c for c in contas_vencer if c["urgente"]]
            proximas = [c for c in contas_vencer if not c["urgente"]]

            if urgentes:
                if personalidade == "formal":
                    msg_parts.append("Contas com vencimento HOJE:")
                elif personalidade == "divertido":
                    msg_parts.append("🔥 Vence HOJE:")
                else:
                    msg_parts.append("📅 Vence hoje:")

                for conta in urgentes:
                    msg_parts.append(f"  • {conta['descricao']}: {fmt_valor(conta['valor'])}")

            if proximas:
                if msg_parts and urgentes:
                    msg_parts.append("")

                if personalidade == "formal":
                    msg_parts.append("Próximos vencimentos:")
                elif personalidade == "divertido":
                    msg_parts.append("📆 Vem aí:")
                else:
                    msg_parts.append("📆 Próximos dias:")

                for conta in proximas:
                    msg_parts.append(
                        f"  • {conta['descricao']}: {fmt_valor(conta['valor'])} "
                        f"(em {conta['dias_restantes']} dia(s))"
                    )

        return "\n".join(msg_parts)

    # =========================================================================
    # DETECCAO DE ANOMALIAS
    # =========================================================================

    async def detectar_gastos_anomalos(
        self,
        db: Session,
        usuario_id: int,
        percentual_limite: float = 0.30
    ) -> List[Dict]:
        """
        Detecta gastos que estao muito acima da media.

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            percentual_limite: Percentual acima da media (0.30 = 30%)

        Returns:
            Lista de categorias com gastos anomalos
        """
        from backend.models import Transacao, Categoria, TipoTransacao

        hoje = datetime.now(timezone.utc)
        mes_atual = hoje.month
        ano_atual = hoje.year

        # Calcula media dos ultimos 3 meses por categoria
        tres_meses_atras = hoje - timedelta(days=90)

        # Gastos dos ultimos 3 meses por categoria
        historico = db.query(
            Transacao.categoria_id,
            func.avg(Transacao.valor).label('media'),
            func.count(Transacao.id).label('quantidade')
        ).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.tipo == TipoTransacao.DESPESA,
            Transacao.data_transacao >= tres_meses_atras,
            Transacao.data_transacao < hoje.replace(day=1),  # Exclui mes atual
            Transacao.status != 'cancelada'
        ).group_by(Transacao.categoria_id).all()

        if not historico:
            return []

        # Gastos do mes atual por categoria
        gastos_atuais = db.query(
            Transacao.categoria_id,
            func.sum(Transacao.valor).label('total')
        ).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.tipo == TipoTransacao.DESPESA,
            extract('month', Transacao.data_transacao) == mes_atual,
            extract('year', Transacao.data_transacao) == ano_atual,
            Transacao.status != 'cancelada'
        ).group_by(Transacao.categoria_id).all()

        # Monta dicionario de gastos atuais
        gastos_dict = {g.categoria_id: float(g.total) for g in gastos_atuais}

        anomalias = []
        for h in historico:
            if h.categoria_id not in gastos_dict:
                continue

            media = float(h.media)
            atual = gastos_dict[h.categoria_id]
            limite = media * (1 + percentual_limite)

            if atual > limite and h.quantidade >= 2:  # Precisa de historico minimo
                # Busca nome da categoria
                categoria = db.query(Categoria).filter(
                    Categoria.id == h.categoria_id
                ).first()

                percentual_acima = ((atual - media) / media) * 100

                anomalias.append({
                    "categoria_id": h.categoria_id,
                    "categoria": categoria.nome if categoria else "Outros",
                    "icone": categoria.icone if categoria else "📌",
                    "media_historica": round(media, 2),
                    "gasto_atual": round(atual, 2),
                    "percentual_acima": round(percentual_acima, 1),
                    "diferenca": round(atual - media, 2)
                })

        # Ordena por maior percentual acima
        anomalias.sort(key=lambda x: x["percentual_acima"], reverse=True)

        return anomalias

    def formatar_alerta_anomalias(
        self,
        anomalias: List[Dict],
        personalidade: str = "amigavel"
    ) -> Optional[str]:
        """
        Formata mensagem de alerta de gastos anomalos.

        Returns:
            Mensagem formatada ou None se nao houver anomalias
        """
        if not anomalias:
            return None

        if personalidade == "formal":
            msg = "Alerta de gastos acima da média:\n\n"
        elif personalidade == "divertido":
            msg = "📊 Opa! Detectei uns gastos acima do normal:\n\n"
        else:
            msg = "📊 Gastos acima da média este mês:\n\n"

        for a in anomalias[:5]:  # Limita a 5
            msg += f"{a['icone']} {a['categoria']}\n"
            msg += f"   Média: {fmt_valor(a['media_historica'])}\n"
            msg += f"   Atual: {fmt_valor(a['gasto_atual'])} (+{a['percentual_acima']:.0f}%)\n\n"

        if personalidade == "divertido":
            msg += "Tá tudo bem? Só avisando! 😉"
        elif personalidade == "formal":
            msg += "Recomenda-se revisar estes gastos."
        else:
            msg += "Quer analisar alguma categoria?"

        return msg

    # =========================================================================
    # RESUMOS PERIODICOS
    # =========================================================================

    async def gerar_resumo_diario(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Gera resumo do dia anterior.

        Returns:
            Dict com transacoes e totais do dia
        """
        from backend.models import Transacao, Categoria, TipoTransacao

        ontem = datetime.now(timezone.utc).date() - timedelta(days=1)

        transacoes = db.query(Transacao).filter(
            Transacao.usuario_id == usuario_id,
            func.date(Transacao.data_transacao) == ontem,
            Transacao.status != 'cancelada'
        ).all()

        total_receitas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.RECEITA)
        total_despesas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.DESPESA)

        itens = []
        for t in transacoes:
            categoria = db.query(Categoria).filter(Categoria.id == t.categoria_id).first()
            itens.append({
                "tipo": t.tipo.value,
                "valor": float(t.valor),
                "descricao": t.descricao,
                "categoria": categoria.nome if categoria else "Outros"
            })

        return {
            "data": ontem.strftime("%d/%m/%Y"),
            "total_receitas": float(total_receitas),
            "total_despesas": float(total_despesas),
            "saldo_dia": float(total_receitas - total_despesas),
            "quantidade": len(transacoes),
            "itens": itens
        }

    async def gerar_resumo_semanal(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Gera resumo da semana anterior.

        Returns:
            Dict com totais e principais categorias da semana
        """
        from backend.models import Transacao, Categoria, TipoTransacao

        hoje = datetime.now(timezone.utc).date()
        # Semana anterior (segunda a domingo)
        dias_desde_segunda = hoje.weekday()
        fim_semana = hoje - timedelta(days=dias_desde_segunda + 1)  # Domingo passado
        inicio_semana = fim_semana - timedelta(days=6)  # Segunda passada

        transacoes = db.query(Transacao).filter(
            Transacao.usuario_id == usuario_id,
            func.date(Transacao.data_transacao) >= inicio_semana,
            func.date(Transacao.data_transacao) <= fim_semana,
            Transacao.status != 'cancelada'
        ).all()

        total_receitas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.RECEITA)
        total_despesas = sum(t.valor for t in transacoes if t.tipo == TipoTransacao.DESPESA)

        # Agrupa por categoria (despesas)
        categorias = {}
        for t in transacoes:
            if t.tipo == TipoTransacao.DESPESA:
                cat_id = t.categoria_id or 0
                if cat_id not in categorias:
                    categoria = db.query(Categoria).filter(Categoria.id == cat_id).first()
                    categorias[cat_id] = {
                        "nome": categoria.nome if categoria else "Outros",
                        "icone": categoria.icone if categoria else "📌",
                        "total": 0
                    }
                categorias[cat_id]["total"] += float(t.valor)

        # Ordena por maior gasto
        top_categorias = sorted(
            categorias.values(),
            key=lambda x: x["total"],
            reverse=True
        )[:5]

        return {
            "periodo": f"{inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m/%Y')}",
            "total_receitas": float(total_receitas),
            "total_despesas": float(total_despesas),
            "saldo_semana": float(total_receitas - total_despesas),
            "quantidade": len(transacoes),
            "top_categorias": top_categorias
        }

    async def gerar_resumo_mensal(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Gera resumo do mes anterior completo.

        Returns:
            Dict com analise completa do mes
        """
        from backend.models import Transacao, Categoria, TipoTransacao
        from backend.services.agents.consultant_agent import consultant_agent

        hoje = datetime.now(timezone.utc)

        # Mes anterior
        if hoje.month == 1:
            mes = 12
            ano = hoje.year - 1
        else:
            mes = hoje.month - 1
            ano = hoje.year

        # Usa consultant agent para pegar dados
        saldo = await consultant_agent.obter_saldo(db, usuario_id, mes, ano)
        categorias = await consultant_agent.obter_gastos_por_categoria(
            db, usuario_id, mes, ano, "despesa"
        )
        comparativo = await consultant_agent.obter_comparativo_mensal(db, usuario_id)

        return {
            "mes": mes,
            "ano": ano,
            "periodo": f"{mes:02d}/{ano}",
            "total_receitas": saldo["total_receitas"],
            "total_despesas": saldo["total_despesas"],
            "saldo": saldo["saldo"],
            "top_categorias": categorias[:5],
            "variacao_despesas": comparativo["variacao"]["despesas"],
            "variacao_receitas": comparativo["variacao"]["receitas"]
        }

    def formatar_resumo(
        self,
        resumo: Dict,
        tipo: str,  # "diario", "semanal", "mensal"
        personalidade: str = "amigavel"
    ) -> str:
        """
        Formata resumo para envio via WhatsApp.
        """
        if tipo == "diario":
            if personalidade == "formal":
                msg = f"Resumo do dia {resumo['data']}:\n\n"
            elif personalidade == "divertido":
                msg = f"📅 E aí! Ontem ({resumo['data']}) foi assim:\n\n"
            else:
                msg = f"📅 Resumo de ontem ({resumo['data']}):\n\n"

            if resumo["quantidade"] == 0:
                msg += "Nenhuma movimentação registrada."
            else:
                msg += f"💰 Receitas: {fmt_valor(resumo['total_receitas'])}\n"
                msg += f"💸 Despesas: {fmt_valor(resumo['total_despesas'])}\n"
                msg += f"📊 Saldo: {fmt_valor(resumo['saldo_dia'])}\n"
                msg += f"\n{resumo['quantidade']} transação(ões)"

        elif tipo == "semanal":
            if personalidade == "formal":
                msg = f"Resumo semanal ({resumo['periodo']}):\n\n"
            elif personalidade == "divertido":
                msg = f"📊 Resumão da semana ({resumo['periodo']}):\n\n"
            else:
                msg = f"📊 Semana passada ({resumo['periodo']}):\n\n"

            msg += f"💰 Receitas: {fmt_valor(resumo['total_receitas'])}\n"
            msg += f"💸 Despesas: {fmt_valor(resumo['total_despesas'])}\n"
            msg += f"📈 Saldo: {fmt_valor(resumo['saldo_semana'])}\n"

            if resumo["top_categorias"]:
                msg += "\n🏷️ Principais gastos:\n"
                for cat in resumo["top_categorias"][:3]:
                    msg += f"  {cat['icone']} {cat['nome']}: {fmt_valor(cat['total'])}\n"

        elif tipo == "mensal":
            if personalidade == "formal":
                msg = f"Relatório mensal ({resumo['periodo']}):\n\n"
            elif personalidade == "divertido":
                msg = f"📊 Fechamento do mês {resumo['periodo']}! 🎉\n\n"
            else:
                msg = f"📊 Resumo de {resumo['periodo']}:\n\n"

            msg += f"💰 Receitas: {fmt_valor(resumo['total_receitas'])}\n"
            msg += f"💸 Despesas: {fmt_valor(resumo['total_despesas'])}\n"

            emoji_saldo = "✅" if resumo["saldo"] >= 0 else "⚠️"
            msg += f"{emoji_saldo} Saldo: {fmt_valor(resumo['saldo'])}\n"

            # Variacao
            var_desp = resumo.get("variacao_despesas", 0)
            if var_desp != 0:
                emoji_var = "📈" if var_desp > 0 else "📉"
                msg += f"\n{emoji_var} Despesas: {'+' if var_desp > 0 else ''}{var_desp}% vs mês anterior"

            if resumo["top_categorias"]:
                msg += "\n\n🏷️ Onde foi o dinheiro:\n"
                for cat in resumo["top_categorias"][:5]:
                    msg += f"  {cat['icone']} {cat['categoria']}: {fmt_valor(cat['total'])} ({cat['percentual']}%)\n"

        return msg

    # =========================================================================
    # METODOS DE EXECUCAO
    # =========================================================================

    async def executar_verificacao_diaria(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Executa todas as verificacoes diarias para um usuario.

        Returns:
            Dict com alertas a enviar
        """
        from backend.services.agents.learning_agent import learning_agent

        # Busca preferencias do usuario
        prefs = await learning_agent.obter_preferencias(db, usuario_id)
        personalidade = prefs.get("personalidade", "amigavel")

        alertas = []

        # 1. Verifica contas a vencer (se habilitado)
        if prefs.get("alertar_contas_vencer", True):
            contas_vencer = await self.verificar_contas_a_vencer(db, usuario_id)
            contas_atrasadas = await self.verificar_contas_atrasadas(db, usuario_id)

            alerta_contas = self.formatar_alerta_contas(
                contas_vencer, contas_atrasadas, personalidade
            )
            if alerta_contas:
                alertas.append({
                    "tipo": "contas",
                    "mensagem": alerta_contas,
                    "urgente": bool(contas_atrasadas) or any(c["urgente"] for c in contas_vencer)
                })

        # 2. Detecta anomalias (se habilitado)
        if prefs.get("alertar_gastos_anomalos", True):
            anomalias = await self.detectar_gastos_anomalos(db, usuario_id)
            alerta_anomalias = self.formatar_alerta_anomalias(anomalias, personalidade)
            if alerta_anomalias:
                alertas.append({
                    "tipo": "anomalia",
                    "mensagem": alerta_anomalias,
                    "urgente": False
                })

        # 3. Resumo diario (se habilitado)
        if prefs.get("resumo_diario", False):
            resumo = await self.gerar_resumo_diario(db, usuario_id)
            if resumo["quantidade"] > 0:
                alertas.append({
                    "tipo": "resumo_diario",
                    "mensagem": self.formatar_resumo(resumo, "diario", personalidade),
                    "urgente": False
                })

        return {
            "usuario_id": usuario_id,
            "alertas": alertas,
            "total": len(alertas)
        }

    async def executar_verificacao_semanal(
        self,
        db: Session,
        usuario_id: int
    ) -> Optional[Dict]:
        """
        Executa verificacao semanal (toda segunda-feira).

        Returns:
            Dict com resumo ou None se desabilitado
        """
        from backend.services.agents.learning_agent import learning_agent

        prefs = await learning_agent.obter_preferencias(db, usuario_id)

        if not prefs.get("resumo_semanal", True):
            return None

        personalidade = prefs.get("personalidade", "amigavel")
        resumo = await self.gerar_resumo_semanal(db, usuario_id)

        return {
            "usuario_id": usuario_id,
            "tipo": "resumo_semanal",
            "mensagem": self.formatar_resumo(resumo, "semanal", personalidade),
            "dados": resumo
        }

    async def executar_verificacao_mensal(
        self,
        db: Session,
        usuario_id: int
    ) -> Optional[Dict]:
        """
        Executa verificacao mensal (todo dia 1).

        Returns:
            Dict com resumo ou None se desabilitado
        """
        from backend.services.agents.learning_agent import learning_agent

        prefs = await learning_agent.obter_preferencias(db, usuario_id)

        if not prefs.get("resumo_mensal", True):
            return None

        personalidade = prefs.get("personalidade", "amigavel")
        resumo = await self.gerar_resumo_mensal(db, usuario_id)

        return {
            "usuario_id": usuario_id,
            "tipo": "resumo_mensal",
            "mensagem": self.formatar_resumo(resumo, "mensal", personalidade),
            "dados": resumo
        }


# Instancia global
proactive_agent = ProactiveAgent()
