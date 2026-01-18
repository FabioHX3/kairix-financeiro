"""
Gateway Agent - Orquestrador principal do sistema multi-agente Kairix.

Responsabilidades:
- Classificar intenção do usuário
- Rotear para agente especializado
- Gerenciar fluxo de confirmação
- Gerar código único para transações
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config import settings
from backend.services.agents.base_agent import (
    BaseAgent,
    AgentContext,
    AgentResponse,
    IntentType,
    OrigemMensagem
)
from backend.services.memory_service import memory_service
from backend.services.agents.learning_agent import learning_agent
from backend.services.agents.personality_agent import personality_agent


class GatewayAgent(BaseAgent):
    """
    Agente Gateway - Ponto de entrada para todas as mensagens.

    Fluxo:
    1. Verifica se há ação pendente (confirmação)
    2. Classifica intenção da mensagem
    3. Roteia para agente especializado
    4. Retorna resposta formatada
    """

    name = "gateway"
    description = "Orquestrador principal do sistema"

    # Palavras-chave para classificação rápida (sem LLM)
    KEYWORDS_CONFIRMAR = {"sim", "s", "ok", "confirma", "confirmo", "isso", "correto", "certo"}
    KEYWORDS_CANCELAR = {"nao", "não", "n", "cancela", "cancelar", "errado", "refazer"}
    KEYWORDS_SAUDACAO = {"oi", "olá", "ola", "eai", "e ai", "bom dia", "boa tarde", "boa noite", "hey", "hi"}
    KEYWORDS_AJUDA = {"ajuda", "help", "como", "o que", "funciona"}

    def __init__(self, db_session=None, redis_client=None):
        super().__init__(db_session, redis_client)

        # LLM para classificação de intenção (modelo leve)
        self.llm = ChatOpenAI(
            model=settings.OPENROUTER_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.1,
            max_tokens=500,
        )

        # Agentes especializados (lazy loading)
        self._extractor_agent = None
        self._learning_agent = None

    @property
    def extractor_agent(self):
        """Lazy load do ExtractorAgent"""
        if self._extractor_agent is None:
            from backend.services.agents.extractor_agent import ExtractorAgent
            self._extractor_agent = ExtractorAgent(self.db, self.redis)
        return self._extractor_agent

    def can_handle(self, context: AgentContext) -> bool:
        """Gateway sempre pode processar"""
        return True

    async def process(self, context: AgentContext) -> AgentResponse:
        """
        Processa mensagem do usuário.

        1. Verifica ação pendente
        2. Classifica intenção
        3. Roteia para agente correto
        """
        self.log(f"Processando: {context.mensagem_original[:50]}...")

        # 1. Verifica se há ação pendente
        acao_pendente = await memory_service.obter_acao_pendente(context.whatsapp)

        if acao_pendente:
            return await self._processar_resposta_pendente(context, acao_pendente)

        # 2. Classifica intenção
        intent = await self._classificar_intencao(context)
        context.intent = intent

        self.log(f"Intenção detectada: {intent.value}")

        # 3. Roteia para agente apropriado
        return await self._rotear(context)

    async def _processar_resposta_pendente(
        self,
        context: AgentContext,
        acao_pendente: dict
    ) -> AgentResponse:
        """Processa resposta do usuário para ação pendente"""
        msg_lower = context.mensagem_original.lower().strip()

        tipo_pendente = acao_pendente.get("tipo", "")

        # Verifica se é confirmação
        if msg_lower in self.KEYWORDS_CONFIRMAR or msg_lower.startswith(("sim", "ok")):
            return await self._confirmar_acao(context, acao_pendente)

        # Verifica se é cancelamento
        if msg_lower in self.KEYWORDS_CANCELAR or msg_lower.startswith(("nao", "não", "cancel")):
            return await self._cancelar_acao(context, acao_pendente)

        # Se está aguardando código para edição/exclusão, tenta extrair
        if tipo_pendente in ("aguardando_codigo_edicao", "aguardando_codigo_exclusao"):
            # Procura código de 5 caracteres na mensagem
            codigo_match = re.search(r'\b([A-Za-z0-9]{5})\b', context.mensagem_original)
            if codigo_match:
                # Tem código, processa como confirmação de código
                return await self._confirmar_acao(context, acao_pendente)

        # Se não é nem sim nem não nem código, pode ser nova mensagem
        # Limpa pendente e processa como nova
        await memory_service.limpar_acao_pendente(context.whatsapp)
        return await self.process(context)

    async def _confirmar_acao(
        self,
        context: AgentContext,
        acao_pendente: dict
    ) -> AgentResponse:
        """Confirma e executa ação pendente"""
        tipo = acao_pendente.get("tipo")
        dados = acao_pendente.get("dados", {})

        if tipo == "registrar_transacao":
            # Salva transação no banco
            resultado = await self._salvar_transacao(context, dados)

            # Limpa ação pendente
            await memory_service.limpar_acao_pendente(context.whatsapp)

            # Salva padrão para aprendizado no banco
            if resultado.get("sucesso") and self.db:
                categoria_id = dados.get("categoria_id") or 1  # Default para categoria 1 se None
                await learning_agent.registrar_padrao(
                    db=self.db,
                    usuario_id=context.usuario_id,
                    descricao=dados.get("descricao", ""),
                    categoria_id=categoria_id,
                    tipo=dados.get("tipo", "despesa")
                )

            # Obtém personalidade do usuário
            personalidade = "amigavel"
            if self.db:
                from backend.models import UserPreferences
                prefs = self.db.query(UserPreferences).filter(
                    UserPreferences.usuario_id == context.usuario_id
                ).first()
                if prefs:
                    personalidade = prefs.personalidade.value

            # Formata mensagem usando personality_agent
            msg = personality_agent.formatar_mensagem_transacao(
                personalidade=personalidade,
                tipo=dados.get("tipo", "despesa"),
                valor=dados.get("valor", 0),
                descricao=dados.get("descricao", ""),
                categoria=dados.get("categoria", "Outros"),
                codigo=resultado.get("codigo", "N/A")
            )

            return AgentResponse(
                sucesso=True,
                mensagem=msg,
                dados=resultado,
                codigo_transacao=resultado.get("codigo")
            )

        if tipo == "registrar_multiplas":
            # Salva múltiplas transações
            itens = dados.get("itens", [])
            codigos = []
            total = 0

            for item in itens:
                resultado = await self._salvar_transacao(context, item)
                if resultado.get("sucesso"):
                    codigos.append(resultado.get("codigo"))
                    total += item.get("valor", 0)

                    # Salva padrão para cada item
                    if self.db:
                        categoria_id = item.get("categoria_id") or 1
                        await learning_agent.registrar_padrao(
                            db=self.db,
                            usuario_id=context.usuario_id,
                            descricao=item.get("descricao", ""),
                            categoria_id=categoria_id,
                            tipo=item.get("tipo", "despesa")
                        )

            # Limpa ação pendente
            await memory_service.limpar_acao_pendente(context.whatsapp)

            if codigos:
                msg = f"Registradas {len(codigos)} transacoes!\n\n"
                for i, item in enumerate(itens):
                    tipo_emoji = "💸" if item.get("tipo") == "despesa" else "💰"
                    msg += f"{tipo_emoji} R$ {item.get('valor', 0):,.2f} - {item.get('descricao', '')}\n"
                    msg += f"   Codigo: {codigos[i] if i < len(codigos) else 'erro'}\n\n"
                msg += f"Algo errado, me avisa que corrijo!"

                return AgentResponse(
                    sucesso=True,
                    mensagem=msg,
                    dados={"codigos": codigos, "total": total}
                )

        if tipo == "aguardando_codigo_edicao":
            from backend.models.models import Transacao

            # Extrai TODOS os códigos de 5 caracteres da mensagem
            codigos_encontrados = re.findall(r'\b([A-Za-z0-9]{5})\b', context.mensagem_original)
            if not codigos_encontrados:
                return AgentResponse(
                    sucesso=False,
                    mensagem="Nao entendi o codigo. Me diz só o codigo de 5 letras!"
                )

            # Verifica qual dos códigos encontrados está na lista de válidos
            codigos_validos = [c.upper() for c in dados.get("codigos_validos", [])]
            codigo = None
            for c in codigos_encontrados:
                if c.upper() in codigos_validos:
                    codigo = c.upper()
                    break

            # Se nenhum match na lista válida, tenta o último como fallback
            if not codigo:
                codigo = codigos_encontrados[-1].upper()
            novo_valor = dados.get("valor_novo")

            transacao = self.db.query(Transacao).filter(
                Transacao.usuario_id == context.usuario_id,
                Transacao.codigo == codigo
            ).first()

            if not transacao:
                return AgentResponse(
                    sucesso=False,
                    mensagem=f"Codigo {codigo} nao encontrado. Confere e tenta de novo!"
                )

            # Salva para confirmar
            await memory_service.salvar_acao_pendente(
                context.whatsapp,
                "editar_transacao",
                {
                    "transacao_id": transacao.id,
                    "codigo": transacao.codigo,
                    "descricao": transacao.descricao,
                    "valor_atual": float(transacao.valor),
                    "valor_novo": novo_valor
                }
            )

            data_fmt = transacao.data_transacao.strftime("%d/%m às %H:%M") if transacao.data_transacao else ""

            return AgentResponse(
                sucesso=True,
                mensagem=f"Alterar *{transacao.descricao}*?\n"
                        f"({data_fmt} - Cod: {transacao.codigo})\n\n"
                        f"De: R$ {transacao.valor:,.2f}\n"
                        f"Para: R$ {novo_valor:,.2f}\n\n"
                        f"Certo? Diga *sim* para confirmar!",
                requer_confirmacao=True
            )

        if tipo == "editar_transacao":
            from backend.models.models import Transacao

            transacao_id = dados.get("transacao_id")
            novo_valor = dados.get("valor_novo")

            transacao = self.db.query(Transacao).filter(
                Transacao.id == transacao_id,
                Transacao.usuario_id == context.usuario_id
            ).first()

            if transacao:
                valor_antigo = transacao.valor
                transacao.valor = novo_valor
                self.db.commit()

                await memory_service.limpar_acao_pendente(context.whatsapp)

                return AgentResponse(
                    sucesso=True,
                    mensagem=f"Alterado!\n\n"
                            f"*{transacao.descricao}*\n"
                            f"De: R$ {valor_antigo:,.2f}\n"
                            f"Para: R$ {novo_valor:,.2f}\n\n"
                            f"Algo errado, me avisa!"
                )

            await memory_service.limpar_acao_pendente(context.whatsapp)
            return AgentResponse(sucesso=False, mensagem="Transacao nao encontrada.")

        if tipo == "aguardando_codigo_exclusao":
            from backend.models.models import Transacao

            # Extrai TODOS os códigos de 5 caracteres da mensagem
            codigos_encontrados = re.findall(r'\b([A-Za-z0-9]{5})\b', context.mensagem_original)
            if not codigos_encontrados:
                return AgentResponse(
                    sucesso=False,
                    mensagem="Nao entendi o codigo. Me diz só o codigo de 5 letras!"
                )

            # Verifica qual dos códigos encontrados está na lista de válidos
            codigos_validos = [c.upper() for c in dados.get("codigos_validos", [])]
            codigo = None
            for c in codigos_encontrados:
                if c.upper() in codigos_validos:
                    codigo = c.upper()
                    break

            # Se nenhum match na lista válida, tenta o último como fallback
            if not codigo:
                codigo = codigos_encontrados[-1].upper()

            transacao = self.db.query(Transacao).filter(
                Transacao.usuario_id == context.usuario_id,
                Transacao.codigo == codigo
            ).first()

            if not transacao:
                return AgentResponse(
                    sucesso=False,
                    mensagem=f"Codigo {codigo} nao encontrado. Confere e tenta de novo!"
                )

            # Salva para confirmar exclusão
            await memory_service.salvar_acao_pendente(
                context.whatsapp,
                "deletar_transacao",
                {
                    "transacao_id": transacao.id,
                    "codigo": transacao.codigo,
                    "descricao": transacao.descricao,
                    "valor": float(transacao.valor)
                }
            )

            data_fmt = transacao.data_transacao.strftime("%d/%m às %H:%M") if transacao.data_transacao else ""
            tipo_emoji = "💸" if transacao.tipo.value == "despesa" else "💰"

            return AgentResponse(
                sucesso=True,
                mensagem=f"Apagar essa transacao?\n\n"
                        f"{tipo_emoji} *{transacao.descricao}*\n"
                        f"R$ {transacao.valor:,.2f}\n"
                        f"{data_fmt} - Cod: {transacao.codigo}\n\n"
                        f"Diga *sim* para confirmar!",
                requer_confirmacao=True
            )

        if tipo == "deletar_transacao":
            from backend.models.models import Transacao

            transacao_id = dados.get("transacao_id")

            transacao = self.db.query(Transacao).filter(
                Transacao.id == transacao_id,
                Transacao.usuario_id == context.usuario_id
            ).first()

            if transacao:
                descricao = transacao.descricao
                valor = transacao.valor
                self.db.delete(transacao)
                self.db.commit()

                await memory_service.limpar_acao_pendente(context.whatsapp)

                return AgentResponse(
                    sucesso=True,
                    mensagem=f"Apagado!\n\n"
                            f"*{descricao}* - R$ {valor:,.2f}\n\n"
                            f"Removido do sistema."
                )

            await memory_service.limpar_acao_pendente(context.whatsapp)
            return AgentResponse(sucesso=False, mensagem="Transacao nao encontrada.")

        # Ação desconhecida
        await memory_service.limpar_acao_pendente(context.whatsapp)
        return AgentResponse(
            sucesso=False,
            mensagem="Desculpe, não entendi. Pode repetir?"
        )

    async def _cancelar_acao(
        self,
        context: AgentContext,
        acao_pendente: dict
    ) -> AgentResponse:
        """Cancela ação pendente"""
        await memory_service.limpar_acao_pendente(context.whatsapp)

        return AgentResponse(
            sucesso=True,
            mensagem="Ok, cancelado! O que deseja fazer?",
            dados={"acao_cancelada": acao_pendente.get("tipo")}
        )

    async def _classificar_intencao(self, context: AgentContext) -> IntentType:
        """
        Classifica a intenção do usuário.

        Prioridade:
        1. Consulta (perguntas como "quanto gastei")
        2. Transação (tem valor/verbo financeiro)
        3. Saudação (só se for APENAS saudação)
        4. Ajuda
        5. LLM para casos ambíguos
        """
        msg_lower = context.mensagem_original.lower().strip()

        # 1. PRIORIDADE: Consulta (perguntas sobre gastos/saldo)
        if self._parece_consulta(msg_lower):
            return IntentType.CONSULTAR

        # 2. Edição de transação
        if self._parece_edicao(msg_lower):
            return IntentType.EDITAR

        # 3. Exclusão de transação
        if self._parece_exclusao(msg_lower):
            return IntentType.DELETAR

        # 4. Padrões de transação
        if self._parece_transacao(msg_lower):
            return IntentType.REGISTRAR

        # 5. Saudação (só se não for transação nem consulta)
        # Verifica se é APENAS saudação (mensagem curta)
        palavras = msg_lower.split()
        if len(palavras) <= 3 and any(kw in msg_lower for kw in self.KEYWORDS_SAUDACAO):
            return IntentType.SAUDACAO

        # 4. Ajuda
        if any(kw in msg_lower for kw in self.KEYWORDS_AJUDA):
            return IntentType.AJUDA

        # 5. Usa LLM para casos ambíguos
        return await self._classificar_com_llm(context)

    def _parece_transacao(self, msg: str) -> bool:
        """Verifica se mensagem parece ser uma transação"""
        # Padrões comuns
        patterns = [
            r'\d+[,.]?\d*\s*(reais?|r\$|conto)',  # "50 reais", "100,50 R$"
            r'r\$\s*\d+',                          # "R$ 50"
            r'gast(ei|ou|amos)',                   # "gastei", "gastou"
            r'pagu(ei|ou)',                        # "paguei", "pagou"
            r'compre?i',                           # "comprei"
            r'receb(i|eu|emos)',                   # "recebi", "recebeu"
            r'entr(ou|aram?)',                     # "entrou", "entraram"
        ]
        return any(re.search(p, msg) for p in patterns)

    def _parece_consulta(self, msg: str) -> bool:
        """Verifica se mensagem parece ser uma consulta"""
        patterns = [
            r'quanto\s+gast',                     # "quanto gastei"
            r'qual\s+(meu\s+)?saldo',             # "qual meu saldo"
            r'minhas?\s+despesas?',               # "minhas despesas"
            r'minhas?\s+receitas?',               # "minhas receitas"
            r'resumo',                            # "resumo"
            r'relatorio',                         # "relatório"
            r'ultim[ao]s?\s+transac',             # "últimas transações"
        ]
        return any(re.search(p, msg) for p in patterns)

    def _parece_edicao(self, msg: str) -> bool:
        """Verifica se mensagem parece ser uma edição"""
        patterns = [
            r'corrig[eai]',                       # "corrige", "corrija", "corrigir"
            r'alter[ae]',                         # "altera", "altere"
            r'mud[ae]',                           # "muda", "mude"
            r'edit[ae]',                          # "edita", "edite"
            r'atualiz[ae]',                       # "atualiza", "atualize"
            r'troc[ae].*valor',                   # "troca o valor"
            r'era\s+\d+.*na verdade',             # "era 30, na verdade é 35"
        ]
        return any(re.search(p, msg) for p in patterns)

    def _parece_exclusao(self, msg: str) -> bool:
        """Verifica se mensagem parece ser uma exclusão"""
        patterns = [
            r'apag[ae]',                          # "apaga", "apague"
            r'delet[ae]',                         # "deleta", "delete"
            r'remov[ae]',                         # "remove", "remova"
            r'exclu[ia]',                         # "exclui", "exclua"
            r'cancel[ae].*transac',               # "cancela a transação"
            r'tir[ae]',                           # "tira", "tire"
        ]
        return any(re.search(p, msg) for p in patterns)

    async def _classificar_com_llm(self, context: AgentContext) -> IntentType:
        """Usa LLM para classificar intenção ambígua"""
        prompt = f"""Classifique a intenção do usuário em uma dessas categorias:
- REGISTRAR: quer registrar gasto ou receita
- CONSULTAR: quer ver gastos, saldo, relatório
- LISTAR: quer ver lista de transações
- EDITAR: quer corrigir transação existente
- DELETAR: quer apagar transação
- CONFIGURAR: quer mudar configurações
- AJUDA: quer ajuda ou instruções
- SAUDACAO: cumprimento, conversa casual
- DESCONHECIDO: não se encaixa em nenhuma

Mensagem: "{context.mensagem_original}"

Responda APENAS com a categoria (ex: REGISTRAR)"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="Você é um classificador de intenções. Responda apenas com a categoria."),
                HumanMessage(content=prompt)
            ])

            intent_str = response.content.strip().upper()

            # Mapeia para enum
            mapping = {
                "REGISTRAR": IntentType.REGISTRAR,
                "CONSULTAR": IntentType.CONSULTAR,
                "LISTAR": IntentType.LISTAR,
                "EDITAR": IntentType.EDITAR,
                "DELETAR": IntentType.DELETAR,
                "CONFIGURAR": IntentType.CONFIGURAR,
                "AJUDA": IntentType.AJUDA,
                "SAUDACAO": IntentType.SAUDACAO,
            }

            return mapping.get(intent_str, IntentType.DESCONHECIDO)

        except Exception as e:
            self.log(f"Erro na classificação LLM: {e}")
            return IntentType.DESCONHECIDO

    async def _rotear(self, context: AgentContext) -> AgentResponse:
        """Roteia para o agente apropriado baseado na intenção"""

        intent = context.intent

        if intent == IntentType.REGISTRAR:
            return await self.extractor_agent.process(context)

        if intent == IntentType.CONSULTAR:
            # TODO: Implementar ConsultantAgent
            return await self._responder_consulta(context)

        if intent == IntentType.SAUDACAO:
            return self._responder_saudacao(context)

        if intent == IntentType.AJUDA:
            return self._responder_ajuda()

        if intent == IntentType.EDITAR:
            return await self._responder_edicao(context)

        if intent == IntentType.DELETAR:
            return await self._responder_exclusao(context)

        # Intenção não mapeada
        return AgentResponse(
            sucesso=True,
            mensagem="Hmm, não entendi muito bem. Pode reformular?\n\n"
                    "Dica: Me conta seus gastos ou receitas que eu organizo tudo!",
            dados={"intent_detectada": intent.value}
        )

    async def _responder_consulta(self, context: AgentContext) -> AgentResponse:
        """Responde consultas básicas"""
        from backend.models.models import Transacao, TipoTransacao
        from sqlalchemy import func
        from zoneinfo import ZoneInfo

        if not self.db:
            return AgentResponse(
                sucesso=False,
                mensagem="Erro ao consultar. Tente novamente."
            )

        msg_lower = context.mensagem_original.lower()
        agora = datetime.now(ZoneInfo(context.timezone))
        inicio_mes = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Meses em português
        meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        mes_ano = f"{meses_pt[agora.month]}/{agora.year}"

        try:
            # Consulta gastos do mês
            if "gast" in msg_lower or "despes" in msg_lower:
                total = self.db.query(func.sum(Transacao.valor)).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.tipo == TipoTransacao.DESPESA,
                    Transacao.data_transacao >= inicio_mes
                ).scalar() or 0

                # Busca últimas 5 despesas
                ultimas = self.db.query(Transacao).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.tipo == TipoTransacao.DESPESA,
                    Transacao.data_transacao >= inicio_mes
                ).order_by(Transacao.data_transacao.desc()).limit(5).all()

                msg = f"💸 *Gastos de {mes_ano}*\n\n"
                msg += f"Total: R$ {total:,.2f}\n\n"

                if ultimas:
                    msg += "Ultimas despesas:\n"
                    for t in ultimas:
                        msg += f"• R$ {t.valor:,.2f} - {t.descricao}\n"

                return AgentResponse(sucesso=True, mensagem=msg)

            # Consulta saldo (receitas - despesas)
            if "saldo" in msg_lower:
                receitas = self.db.query(func.sum(Transacao.valor)).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.tipo == TipoTransacao.RECEITA,
                    Transacao.data_transacao >= inicio_mes
                ).scalar() or 0

                despesas = self.db.query(func.sum(Transacao.valor)).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.tipo == TipoTransacao.DESPESA,
                    Transacao.data_transacao >= inicio_mes
                ).scalar() or 0

                saldo = receitas - despesas
                emoji = "📈" if saldo >= 0 else "📉"

                msg = f"{emoji} *Saldo de {mes_ano}*\n\n"
                msg += f"💰 Receitas: R$ {receitas:,.2f}\n"
                msg += f"💸 Despesas: R$ {despesas:,.2f}\n"
                msg += f"━━━━━━━━━━━━━\n"
                msg += f"*Saldo: R$ {saldo:,.2f}*"

                return AgentResponse(sucesso=True, mensagem=msg)

            # Consulta receitas
            if "receb" in msg_lower or "receit" in msg_lower or "entr" in msg_lower:
                total = self.db.query(func.sum(Transacao.valor)).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.tipo == TipoTransacao.RECEITA,
                    Transacao.data_transacao >= inicio_mes
                ).scalar() or 0

                msg = f"💰 *Receitas de {mes_ano}*\n\n"
                msg += f"Total: R$ {total:,.2f}"

                return AgentResponse(sucesso=True, mensagem=msg)

            # Consulta genérica - mostra resumo
            receitas = self.db.query(func.sum(Transacao.valor)).filter(
                Transacao.usuario_id == context.usuario_id,
                Transacao.tipo == TipoTransacao.RECEITA,
                Transacao.data_transacao >= inicio_mes
            ).scalar() or 0

            despesas = self.db.query(func.sum(Transacao.valor)).filter(
                Transacao.usuario_id == context.usuario_id,
                Transacao.tipo == TipoTransacao.DESPESA,
                Transacao.data_transacao >= inicio_mes
            ).scalar() or 0

            saldo = receitas - despesas

            msg = f"📊 *Resumo de {mes_ano}*\n\n"
            msg += f"💰 Receitas: R$ {receitas:,.2f}\n"
            msg += f"💸 Despesas: R$ {despesas:,.2f}\n"
            msg += f"━━━━━━━━━━━━━\n"
            msg += f"*Saldo: R$ {saldo:,.2f}*"

            return AgentResponse(sucesso=True, mensagem=msg)

        except Exception as e:
            self.log(f"Erro na consulta: {e}")
            return AgentResponse(
                sucesso=False,
                mensagem="Erro ao consultar. Tente novamente."
            )

    def _responder_saudacao(self, context: AgentContext) -> AgentResponse:
        """Responde saudações com horário contextual"""
        from zoneinfo import ZoneInfo

        # Usa timezone do usuário
        hora = datetime.now(ZoneInfo(context.timezone)).hour

        if 6 <= hora < 12:
            saudacao = "Bom dia"
        elif 12 <= hora < 18:
            saudacao = "Boa tarde"
        else:
            saudacao = "Boa noite"

        return AgentResponse(
            sucesso=True,
            mensagem=f"{saudacao}! Sou o Kairix, seu assistente financeiro.\n\n"
                    f"Me conta seus gastos e receitas que eu organizo tudo pra voce!\n\n"
                    f"Exemplo: \"Gastei 50 no almoco\""
        )

    def _responder_ajuda(self) -> AgentResponse:
        """Responde pedidos de ajuda"""
        return AgentResponse(
            sucesso=True,
            mensagem="Posso te ajudar a organizar suas financas!\n\n"
                    "O que eu faco:\n"
                    "- Registro gastos e receitas\n"
                    "- Entendo fotos de notas e comprovantes\n"
                    "- Transcrevo audios com gastos\n"
                    "- Organizo por categorias\n\n"
                    "Exemplos:\n"
                    "- \"Gastei 150 no mercado\"\n"
                    "- \"Recebi 3000 de salario\"\n"
                    "- Envie foto de uma nota fiscal\n"
                    "- Envie audio falando um gasto"
        )

    async def _responder_edicao(self, context: AgentContext) -> AgentResponse:
        """Processa edição de transação"""
        from backend.models.models import Transacao

        if not self.db:
            return AgentResponse(sucesso=False, mensagem="Erro interno. Tente novamente.")

        msg = context.mensagem_original.lower()

        # Tenta extrair código da transação (5 caracteres alfanuméricos)
        codigo_match = re.search(r'\b([A-Za-z0-9]{5})\b', context.mensagem_original)

        # Tenta extrair novo valor
        valor_match = re.search(r'(\d+[,.]?\d*)', msg)
        novo_valor = None
        if valor_match:
            novo_valor = float(valor_match.group(1).replace(',', '.'))

        # Busca transação pelo código ou descrição
        transacao = None

        if codigo_match:
            codigo = codigo_match.group(1).upper()
            transacao = self.db.query(Transacao).filter(
                Transacao.usuario_id == context.usuario_id,
                Transacao.codigo == codigo
            ).first()

        # Se não achou por código, busca por descrição
        if not transacao:
            # Palavras-chave para buscar
            keywords = ["uber", "ifood", "mercado", "luz", "agua", "salario", "aluguel", "aliexpress", "99", "taxi"]
            keyword_encontrada = None
            for kw in keywords:
                if kw in msg:
                    keyword_encontrada = kw
                    break

            if keyword_encontrada:
                # Busca TODAS as transações com esse nome
                transacoes = self.db.query(Transacao).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.descricao.ilike(f"%{keyword_encontrada}%")
                ).order_by(Transacao.data_transacao.desc()).limit(5).all()

                if len(transacoes) > 1:
                    # Múltiplas transações - salva contexto e pede para escolher
                    # Salva lista de códigos válidos para validação posterior
                    codigos_validos = [t.codigo for t in transacoes]
                    await memory_service.salvar_acao_pendente(
                        context.whatsapp,
                        "aguardando_codigo_edicao",
                        {"valor_novo": novo_valor, "keyword": keyword_encontrada, "codigos_validos": codigos_validos}
                    )

                    msg = f"Encontrei {len(transacoes)} transacoes de *{keyword_encontrada.title()}*:\n\n"
                    for i, t in enumerate(transacoes, 1):
                        data_fmt = t.data_transacao.strftime("%d/%m %H:%M") if t.data_transacao else "?"
                        msg += f"{i}. R$ {t.valor:,.2f} - {data_fmt}\n"
                        msg += f"   Codigo: {t.codigo}\n\n"
                    msg += f"Qual delas? Me diz o codigo!"

                    return AgentResponse(
                        sucesso=True,
                        mensagem=msg,
                        requer_confirmacao=True
                    )
                elif len(transacoes) == 1:
                    transacao = transacoes[0]

        if not transacao:
            return AgentResponse(
                sucesso=False,
                mensagem="Nao encontrei essa transacao.\n\n"
                        "Dica: Use o codigo (ex: \"corrige NF41Z para 35\")\n"
                        "ou o nome (ex: \"corrige o uber para 35\")"
            )

        # Formata data/hora para exibição
        data_fmt = transacao.data_transacao.strftime("%d/%m às %H:%M") if transacao.data_transacao else ""

        # Se tem novo valor, salva ação pendente para confirmar
        if novo_valor:
            await memory_service.salvar_acao_pendente(
                context.whatsapp,
                "editar_transacao",
                {
                    "transacao_id": transacao.id,
                    "codigo": transacao.codigo,
                    "descricao": transacao.descricao,
                    "valor_atual": float(transacao.valor),
                    "valor_novo": novo_valor
                }
            )

            return AgentResponse(
                sucesso=True,
                mensagem=f"Alterar *{transacao.descricao}*?\n"
                        f"({data_fmt} - Cod: {transacao.codigo})\n\n"
                        f"De: R$ {transacao.valor:,.2f}\n"
                        f"Para: R$ {novo_valor:,.2f}\n\n"
                        f"Certo? Diga *sim* para confirmar!",
                requer_confirmacao=True
            )

        # Se não tem novo valor, pede
        return AgentResponse(
            sucesso=True,
            mensagem=f"Encontrei: *{transacao.descricao}* - R$ {transacao.valor:,.2f}\n"
                    f"({data_fmt} - Cod: {transacao.codigo})\n\n"
                    f"Qual o valor correto?"
        )

    async def _responder_exclusao(self, context: AgentContext) -> AgentResponse:
        """Processa exclusão de transação"""
        from backend.models.models import Transacao

        if not self.db:
            return AgentResponse(sucesso=False, mensagem="Erro interno. Tente novamente.")

        msg = context.mensagem_original.lower()

        # Tenta extrair código da transação
        codigo_match = re.search(r'\b([A-Za-z0-9]{5})\b', context.mensagem_original)

        # Busca transação
        transacao = None

        if codigo_match:
            codigo = codigo_match.group(1).upper()
            transacao = self.db.query(Transacao).filter(
                Transacao.usuario_id == context.usuario_id,
                Transacao.codigo == codigo
            ).first()

        # Se não achou por código, busca por descrição
        if not transacao:
            keywords = ["uber", "ifood", "mercado", "luz", "agua", "salario", "aluguel", "aliexpress", "99", "taxi"]
            keyword_encontrada = None
            for kw in keywords:
                if kw in msg:
                    keyword_encontrada = kw
                    break

            if keyword_encontrada:
                # Busca TODAS as transações com esse nome
                transacoes = self.db.query(Transacao).filter(
                    Transacao.usuario_id == context.usuario_id,
                    Transacao.descricao.ilike(f"%{keyword_encontrada}%")
                ).order_by(Transacao.data_transacao.desc()).limit(5).all()

                if len(transacoes) > 1:
                    # Múltiplas transações - salva contexto e pede para escolher
                    # Salva lista de códigos válidos para validação posterior
                    codigos_validos = [t.codigo for t in transacoes]
                    await memory_service.salvar_acao_pendente(
                        context.whatsapp,
                        "aguardando_codigo_exclusao",
                        {"keyword": keyword_encontrada, "codigos_validos": codigos_validos}
                    )

                    msg = f"Encontrei {len(transacoes)} transacoes de *{keyword_encontrada.title()}*:\n\n"
                    for i, t in enumerate(transacoes, 1):
                        data_fmt = t.data_transacao.strftime("%d/%m %H:%M") if t.data_transacao else "?"
                        msg += f"{i}. R$ {t.valor:,.2f} - {data_fmt}\n"
                        msg += f"   Codigo: {t.codigo}\n\n"
                    msg += f"Qual delas? Me diz o codigo!"

                    return AgentResponse(
                        sucesso=True,
                        mensagem=msg,
                        requer_confirmacao=True
                    )
                elif len(transacoes) == 1:
                    transacao = transacoes[0]

        if not transacao:
            return AgentResponse(
                sucesso=False,
                mensagem="Nao encontrei essa transacao.\n\n"
                        "Dica: Use o codigo (ex: \"apaga NF41Z\")\n"
                        "ou o nome (ex: \"apaga o uber\")"
            )

        # Formata data/hora para exibição
        data_fmt = transacao.data_transacao.strftime("%d/%m às %H:%M") if transacao.data_transacao else ""

        # Salva ação pendente para confirmar exclusão
        await memory_service.salvar_acao_pendente(
            context.whatsapp,
            "deletar_transacao",
            {
                "transacao_id": transacao.id,
                "codigo": transacao.codigo,
                "descricao": transacao.descricao,
                "valor": float(transacao.valor)
            }
        )

        tipo_emoji = "💸" if transacao.tipo.value == "despesa" else "💰"

        return AgentResponse(
            sucesso=True,
            mensagem=f"Apagar essa transacao?\n\n"
                    f"{tipo_emoji} *{transacao.descricao}*\n"
                    f"R$ {transacao.valor:,.2f}\n"
                    f"{data_fmt} - Cod: {transacao.codigo}\n\n"
                    f"Diga *sim* para confirmar!",
            requer_confirmacao=True
        )

    async def _salvar_transacao(self, context: AgentContext, dados: dict) -> dict:
        """Salva transação no banco de dados"""
        from backend.models.models import Transacao, TipoTransacao, OrigemRegistro, gerar_codigo_unico

        if not self.db:
            return {"sucesso": False, "erro": "Banco de dados não disponível"}

        try:
            # Gera código único
            codigo = gerar_codigo_unico(self.db)

            # Mapeia origem
            origem_map = {
                "whatsapp_texto": OrigemRegistro.WHATSAPP_TEXTO,
                "whatsapp_audio": OrigemRegistro.WHATSAPP_AUDIO,
                "whatsapp_imagem": OrigemRegistro.WHATSAPP_IMAGEM,
                "web": OrigemRegistro.WEB,
                "api": OrigemRegistro.API,
            }
            origem = origem_map.get(context.origem.value, OrigemRegistro.WHATSAPP_TEXTO)

            # Mapeia tipo
            tipo = TipoTransacao.DESPESA if dados.get("tipo") == "despesa" else TipoTransacao.RECEITA

            # Cria transação
            transacao = Transacao(
                codigo=codigo,
                usuario_id=context.usuario_id,
                categoria_id=dados.get("categoria_id"),
                tipo=tipo,
                valor=dados.get("valor", 0),
                descricao=dados.get("descricao", ""),
                data_transacao=datetime.strptime(dados.get("data", datetime.now(timezone.utc).strftime("%Y-%m-%d")), "%Y-%m-%d").replace(tzinfo=timezone.utc),
                origem=origem,
                mensagem_original=context.mensagem_original,
                confianca_ia=dados.get("confianca", 0.0)
            )

            self.db.add(transacao)
            self.db.commit()
            self.db.refresh(transacao)

            self.log(f"Transacao salva: {codigo} - R$ {transacao.valor}")

            return {
                "sucesso": True,
                "codigo": codigo,
                "id": transacao.id,
                "valor": transacao.valor
            }

        except Exception as e:
            self.db.rollback()
            self.log(f"Erro ao salvar transacao: {e}")
            return {"sucesso": False, "erro": str(e)}


# Instância global
gateway_agent = GatewayAgent()
