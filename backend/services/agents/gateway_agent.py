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
from datetime import datetime
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
        acao_pendente = await memory_service.obter_acao_pendente(context.telefone)

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

        # Verifica se é confirmação
        if msg_lower in self.KEYWORDS_CONFIRMAR or msg_lower.startswith(("sim", "ok")):
            return await self._confirmar_acao(context, acao_pendente)

        # Verifica se é cancelamento
        if msg_lower in self.KEYWORDS_CANCELAR or msg_lower.startswith(("nao", "não")):
            return await self._cancelar_acao(context, acao_pendente)

        # Se não é nem sim nem não, pode ser correção ou nova mensagem
        # Limpa pendente e processa como nova
        await memory_service.limpar_acao_pendente(context.telefone)
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
            await memory_service.limpar_acao_pendente(context.telefone)

            # Salva padrão para aprendizado
            if resultado.get("sucesso"):
                await memory_service.salvar_padrao_usuario(
                    usuario_id=context.usuario_id,
                    descricao=dados.get("descricao", ""),
                    categoria_id=dados.get("categoria_id", 0),
                    tipo=dados.get("tipo", "despesa")
                )

            return AgentResponse(
                sucesso=True,
                mensagem=f"Registrado! Codigo: {resultado.get('codigo', 'N/A')}\n\n"
                        f"{dados.get('tipo', '').upper()} de R$ {dados.get('valor', 0):.2f}\n"
                        f"{dados.get('descricao', '')}\n"
                        f"Categoria: {dados.get('categoria', 'Outros')}\n\n"
                        f"Algo errado? Me avisa que corrijo!",
                dados=resultado,
                codigo_transacao=resultado.get("codigo")
            )

        # Ação desconhecida
        await memory_service.limpar_acao_pendente(context.telefone)
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
        await memory_service.limpar_acao_pendente(context.telefone)

        return AgentResponse(
            sucesso=True,
            mensagem="Ok, cancelado! O que deseja fazer?",
            dados={"acao_cancelada": acao_pendente.get("tipo")}
        )

    async def _classificar_intencao(self, context: AgentContext) -> IntentType:
        """
        Classifica a intenção do usuário.

        Primeiro tenta classificação por keywords (rápido),
        depois usa LLM se necessário.
        """
        msg_lower = context.mensagem_original.lower().strip()

        # Classificação rápida por keywords
        if any(kw in msg_lower for kw in self.KEYWORDS_SAUDACAO):
            return IntentType.SAUDACAO

        if any(kw in msg_lower for kw in self.KEYWORDS_AJUDA):
            return IntentType.AJUDA

        # Padrões comuns de transação
        if self._parece_transacao(msg_lower):
            return IntentType.REGISTRAR

        # Padrões de consulta
        if self._parece_consulta(msg_lower):
            return IntentType.CONSULTAR

        # Usa LLM para casos ambíguos
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

        # Intenção não mapeada
        return AgentResponse(
            sucesso=True,
            mensagem="Hmm, não entendi muito bem. Pode reformular?\n\n"
                    "Dica: Me conta seus gastos ou receitas que eu organizo tudo!",
            dados={"intent_detectada": intent.value}
        )

    async def _responder_consulta(self, context: AgentContext) -> AgentResponse:
        """Responde consultas básicas (placeholder para ConsultantAgent)"""
        # TODO: Mover para ConsultantAgent

        return AgentResponse(
            sucesso=True,
            mensagem="Consultas ainda estao sendo implementadas.\n\n"
                    "Em breve voce podera perguntar:\n"
                    "- Quanto gastei esse mes?\n"
                    "- Qual meu saldo?\n"
                    "- Minhas ultimas transacoes"
        )

    def _responder_saudacao(self, context: AgentContext) -> AgentResponse:
        """Responde saudações"""
        hora = datetime.now().hour

        if hora < 12:
            saudacao = "Bom dia"
        elif hora < 18:
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
                data_transacao=datetime.strptime(dados.get("data", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"),
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
