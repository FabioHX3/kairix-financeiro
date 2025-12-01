"""
Agente Financeiro com LangChain
- Memória de conversa por usuário
- Tools para registrar transações
- Processamento inteligente de mensagens
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain.memory import ConversationBufferWindowMemory
from pydantic import BaseModel, Field

from backend.config import settings


# ============================================================================
# SCHEMAS DE RESPOSTA
# ============================================================================

class TransacaoExtraida(BaseModel):
    """Schema para transação extraída pelo agente"""
    tipo: str = Field(description="'receita' ou 'despesa'")
    valor: float = Field(description="Valor da transação")
    descricao: str = Field(description="Descrição da transação")
    categoria: str = Field(description="Categoria sugerida")
    data: str = Field(description="Data no formato YYYY-MM-DD")
    confianca: float = Field(description="Confiança de 0 a 1")


class RespostaAgente(BaseModel):
    """Schema para resposta do agente"""
    acao: str = Field(description="'registrar', 'perguntar', 'confirmar', 'consultar', 'conversar'")
    mensagem: str = Field(description="Mensagem para enviar ao usuário")
    transacao: Optional[TransacaoExtraida] = Field(default=None, description="Dados da transação se acao='registrar'")
    aguardando: Optional[str] = Field(default=None, description="O que está aguardando se acao='perguntar'")


# ============================================================================
# MEMÓRIA DE CONVERSA
# ============================================================================

class MemoriaUsuarios:
    """Gerencia memória de conversa por usuário (in-memory para MVP)"""

    def __init__(self, max_messages: int = 20):
        self._memorias: Dict[str, List[Dict]] = {}
        self._contextos: Dict[str, Dict] = {}  # Contexto pendente (ex: aguardando valor)
        self.max_messages = max_messages

    def get_historico(self, user_id: str) -> List[Dict]:
        """Retorna histórico de mensagens do usuário"""
        return self._memorias.get(user_id, [])

    def add_mensagem(self, user_id: str, role: str, content: str):
        """Adiciona mensagem ao histórico"""
        if user_id not in self._memorias:
            self._memorias[user_id] = []

        self._memorias[user_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        # Mantém apenas as últimas N mensagens
        if len(self._memorias[user_id]) > self.max_messages:
            self._memorias[user_id] = self._memorias[user_id][-self.max_messages:]

    def get_contexto(self, user_id: str) -> Dict:
        """Retorna contexto pendente do usuário"""
        return self._contextos.get(user_id, {})

    def set_contexto(self, user_id: str, contexto: Dict):
        """Define contexto pendente"""
        self._contextos[user_id] = contexto

    def limpar_contexto(self, user_id: str):
        """Limpa contexto pendente"""
        if user_id in self._contextos:
            del self._contextos[user_id]

    def limpar_historico(self, user_id: str):
        """Limpa histórico do usuário"""
        if user_id in self._memorias:
            del self._memorias[user_id]
        self.limpar_contexto(user_id)


# Instância global de memória
memoria = MemoriaUsuarios()


# ============================================================================
# AGENTE FINANCEIRO
# ============================================================================

class AgenteFinanceiro:
    """Agente de IA para gestão financeira via WhatsApp"""

    def __init__(self):
        # Configura LLM via OpenRouter
        self.llm = ChatOpenAI(
            model=settings.OPENROUTER_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.3,
            max_tokens=1000,
        )

        self.system_prompt = self._criar_system_prompt()

    def _criar_system_prompt(self) -> str:
        """Cria o prompt do sistema para o agente"""
        return """Você é o Kairix, um assistente financeiro pessoal inteligente e amigável no WhatsApp.

SUA PERSONALIDADE:
- Simpático e prestativo
- Direto e objetivo nas respostas
- Usa emojis com moderação
- Fala português brasileiro informal mas profissional

SUAS CAPACIDADES:
1. Registrar despesas e receitas a partir de mensagens de texto
2. Entender fotos de notas fiscais e comprovantes
3. Transcrever áudios com informações financeiras
4. Lembrar do contexto da conversa anterior
5. Perguntar quando algo não está claro

CATEGORIAS DISPONÍVEIS:
DESPESAS: Alimentação, Transporte, Saúde, Educação, Lazer, Casa, Vestuário, Outros
RECEITAS: Salário, Freelance, Investimentos, Vendas, Aluguel, Outros

REGRAS DE RESPOSTA:
Você DEVE responder SEMPRE com um JSON válido neste formato:
{
  "acao": "registrar" | "perguntar" | "confirmar" | "consultar" | "conversar",
  "mensagem": "mensagem para o usuário",
  "transacao": {
    "tipo": "receita" ou "despesa",
    "valor": numero,
    "descricao": "descrição",
    "categoria": "categoria",
    "data": "YYYY-MM-DD",
    "confianca": 0.0 a 1.0
  } ou null,
  "aguardando": "valor" | "tipo" | "categoria" | "confirmacao" | null
}

QUANDO USAR CADA AÇÃO:
- "registrar": Quando tem CERTEZA de tipo, valor e descrição
- "perguntar": Quando falta informação essencial (valor, se é gasto ou receita)
- "confirmar": Quando registrou e quer confirmar com usuário
- "consultar": Quando usuário pergunta sobre gastos/saldo
- "conversar": Para saudações, dúvidas gerais, ajuda

EXEMPLOS:

Usuário: "gastei 50 no almoço"
{
  "acao": "registrar",
  "mensagem": "💸 Registrei sua despesa!\n\n💵 R$ 50,00\n📝 Almoço\n🏷️ Alimentação\n\n✅ Tudo certo?",
  "transacao": {"tipo": "despesa", "valor": 50, "descricao": "Almoço", "categoria": "Alimentação", "data": "HOJE", "confianca": 0.95},
  "aguardando": null
}

Usuário: "150 reais"
{
  "acao": "perguntar",
  "mensagem": "🤔 R$ 150,00 - isso foi um *gasto* ou um *recebimento*?",
  "transacao": null,
  "aguardando": "tipo"
}

Usuário: "oi"
{
  "acao": "conversar",
  "mensagem": "Olá! 👋 Sou o Kairix, seu assistente financeiro!\n\nMe conta seus gastos e ganhos que eu organizo tudo pra você.\n\n💡 Exemplo: \"Gastei 50 no almoço\"",
  "transacao": null,
  "aguardando": null
}

DATA DE HOJE: {data_hoje}
"""

    def _formatar_historico(self, historico: List[Dict]) -> List:
        """Converte histórico para formato LangChain"""
        messages = []
        for msg in historico[-10:]:  # Últimas 10 mensagens
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))
        return messages

    async def processar_mensagem(
        self,
        user_id: str,
        mensagem: str,
        categorias: List[Dict] = None,
        contexto_extra: Dict = None
    ) -> RespostaAgente:
        """
        Processa uma mensagem do usuário e retorna a resposta do agente

        Args:
            user_id: ID único do usuário (telefone)
            mensagem: Texto da mensagem
            categorias: Lista de categorias disponíveis
            contexto_extra: Contexto adicional (ex: transcrição de áudio)

        Returns:
            RespostaAgente com ação e mensagem
        """

        # Monta o contexto
        historico = memoria.get_historico(user_id)
        contexto_pendente = memoria.get_contexto(user_id)

        # Prepara categorias
        if categorias:
            cats_texto = self._formatar_categorias(categorias)
        else:
            cats_texto = ""

        # Monta prompt com contexto
        contexto_msgs = ""
        if contexto_pendente:
            contexto_msgs = f"\n\nCONTEXTO PENDENTE: Aguardando '{contexto_pendente.get('aguardando', '')}'"
            if contexto_pendente.get("transacao_parcial"):
                contexto_msgs += f"\nTransação parcial: {json.dumps(contexto_pendente['transacao_parcial'])}"

        if contexto_extra:
            contexto_msgs += f"\n\nCONTEXTO EXTRA: {json.dumps(contexto_extra)}"

        # System prompt com data atual
        system = self.system_prompt.format(data_hoje=datetime.now().strftime("%Y-%m-%d"))
        if cats_texto:
            system = system.replace(
                "CATEGORIAS DISPONÍVEIS:",
                f"CATEGORIAS DISPONÍVEIS:\n{cats_texto}"
            )
        system += contexto_msgs

        # Monta mensagens
        messages = [SystemMessage(content=system)]
        messages.extend(self._formatar_historico(historico))
        messages.append(HumanMessage(content=mensagem))

        try:
            # Chama o LLM
            response = await self.llm.ainvoke(messages)

            # Parseia resposta JSON
            resposta = self._parsear_resposta(response.content)

            # Salva no histórico
            memoria.add_mensagem(user_id, "user", mensagem)
            memoria.add_mensagem(user_id, "assistant", resposta.mensagem)

            # Atualiza contexto se necessário
            if resposta.aguardando:
                memoria.set_contexto(user_id, {
                    "aguardando": resposta.aguardando,
                    "transacao_parcial": resposta.transacao.model_dump() if resposta.transacao else None
                })
            elif resposta.acao == "registrar":
                memoria.limpar_contexto(user_id)

            return resposta

        except Exception as e:
            print(f"[Agente] Erro ao processar: {e}")
            return RespostaAgente(
                acao="conversar",
                mensagem="❌ Desculpe, tive um problema. Pode repetir?",
                transacao=None,
                aguardando=None
            )

    def _formatar_categorias(self, categorias: List[Dict]) -> str:
        """Formata lista de categorias para o prompt"""
        receitas = [c["nome"] for c in categorias if c.get("tipo") == "receita"]
        despesas = [c["nome"] for c in categorias if c.get("tipo") == "despesa"]

        texto = f"DESPESAS: {', '.join(despesas)}\n"
        texto += f"RECEITAS: {', '.join(receitas)}"
        return texto

    def _parsear_resposta(self, content: str) -> RespostaAgente:
        """Parseia a resposta do LLM para RespostaAgente"""
        import re

        # Remove markdown se houver
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        content = content.strip()

        # Tenta encontrar JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            content = json_match.group()

        try:
            data = json.loads(content)

            # Processa transação se existir
            transacao = None
            if data.get("transacao"):
                t = data["transacao"]
                # Converte data
                data_str = t.get("data", "HOJE")
                if data_str.upper() == "HOJE":
                    data_str = datetime.now().strftime("%Y-%m-%d")
                elif data_str.upper() == "ONTEM":
                    data_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

                transacao = TransacaoExtraida(
                    tipo=t.get("tipo", "despesa"),
                    valor=float(t.get("valor", 0)),
                    descricao=t.get("descricao", ""),
                    categoria=t.get("categoria", "Outros"),
                    data=data_str,
                    confianca=float(t.get("confianca", 0.5))
                )

            return RespostaAgente(
                acao=data.get("acao", "conversar"),
                mensagem=data.get("mensagem", ""),
                transacao=transacao,
                aguardando=data.get("aguardando")
            )

        except json.JSONDecodeError as e:
            print(f"[Agente] Erro ao parsear JSON: {e}")
            print(f"[Agente] Conteúdo: {content[:500]}")
            # Retorna resposta genérica
            return RespostaAgente(
                acao="conversar",
                mensagem=content if len(content) < 500 else "Entendi! Como posso ajudar?",
                transacao=None,
                aguardando=None
            )

    async def processar_audio(
        self,
        user_id: str,
        transcricao: str,
        categorias: List[Dict] = None
    ) -> RespostaAgente:
        """Processa transcrição de áudio"""
        return await self.processar_mensagem(
            user_id=user_id,
            mensagem=transcricao,
            categorias=categorias,
            contexto_extra={"origem": "audio", "transcricao": transcricao}
        )

    async def processar_imagem(
        self,
        user_id: str,
        dados_imagem: Dict,
        caption: str = "",
        categorias: List[Dict] = None
    ) -> RespostaAgente:
        """Processa dados extraídos de imagem"""
        # Se a extração de imagem já tem dados, usa eles
        mensagem = caption if caption else "Enviei uma foto de comprovante"

        return await self.processar_mensagem(
            user_id=user_id,
            mensagem=mensagem,
            categorias=categorias,
            contexto_extra={
                "origem": "imagem",
                "dados_extraidos": dados_imagem
            }
        )


# ============================================================================
# INSTÂNCIA GLOBAL
# ============================================================================

agente = AgenteFinanceiro()
