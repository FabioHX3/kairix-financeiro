"""
Agente Financeiro com LangChain
- Memória de conversa por usuário (Redis para persistência)
- Tools para registrar transações
- Processamento inteligente de mensagens
"""

import json
import redis
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
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
# MEMÓRIA DE CONVERSA COM REDIS
# ============================================================================

class MemoriaUsuarios:
    """
    Gerencia memória de conversa por usuário usando Redis para persistência.
    - Histórico de mensagens persiste entre reinicializações
    - Contextos pendentes (aguardando confirmação) também persistem
    - TTL de 24h para limpeza automática de conversas antigas
    """

    def __init__(self, max_messages: int = 20, ttl_hours: int = 24):
        self.max_messages = max_messages
        self.ttl_seconds = ttl_hours * 3600

        # Conecta ao Redis
        try:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
            self._redis.ping()
            print("[Memória] Conectado ao Redis para persistência de conversas")
        except Exception as e:
            print(f"[Memória] Redis não disponível, usando fallback in-memory: {e}")
            self._redis = None

        # Fallback in-memory caso Redis não esteja disponível
        self._memorias_fallback: Dict[str, List[Dict]] = {}
        self._contextos_fallback: Dict[str, Dict] = {}

    def _key_historico(self, user_id: str) -> str:
        """Gera chave Redis para histórico"""
        return f"kairix:chat:{user_id}:historico"

    def _key_contexto(self, user_id: str) -> str:
        """Gera chave Redis para contexto"""
        return f"kairix:chat:{user_id}:contexto"

    def get_historico(self, user_id: str) -> List[Dict]:
        """Retorna histórico de mensagens do usuário"""
        if self._redis:
            try:
                data = self._redis.get(self._key_historico(user_id))
                if data:
                    return json.loads(data)
                return []
            except Exception as e:
                print(f"[Memória] Erro ao ler histórico: {e}")
                return self._memorias_fallback.get(user_id, [])
        return self._memorias_fallback.get(user_id, [])

    def add_mensagem(self, user_id: str, role: str, content: str):
        """Adiciona mensagem ao histórico"""
        historico = self.get_historico(user_id)

        historico.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })

        # Mantém apenas as últimas N mensagens
        if len(historico) > self.max_messages:
            historico = historico[-self.max_messages:]

        if self._redis:
            try:
                self._redis.setex(
                    self._key_historico(user_id),
                    self.ttl_seconds,
                    json.dumps(historico)
                )
            except Exception as e:
                print(f"[Memória] Erro ao salvar histórico: {e}")
                self._memorias_fallback[user_id] = historico
        else:
            self._memorias_fallback[user_id] = historico

    def get_contexto(self, user_id: str) -> Dict:
        """Retorna contexto pendente do usuário"""
        if self._redis:
            try:
                data = self._redis.get(self._key_contexto(user_id))
                if data:
                    return json.loads(data)
                return {}
            except Exception as e:
                print(f"[Memória] Erro ao ler contexto: {e}")
                return self._contextos_fallback.get(user_id, {})
        return self._contextos_fallback.get(user_id, {})

    def set_contexto(self, user_id: str, contexto: Dict):
        """Define contexto pendente"""
        if self._redis:
            try:
                # Contexto expira em 1 hora (usuário deve confirmar em tempo razoável)
                self._redis.setex(
                    self._key_contexto(user_id),
                    3600,  # 1 hora
                    json.dumps(contexto)
                )
            except Exception as e:
                print(f"[Memória] Erro ao salvar contexto: {e}")
                self._contextos_fallback[user_id] = contexto
        else:
            self._contextos_fallback[user_id] = contexto

    def limpar_contexto(self, user_id: str):
        """Limpa contexto pendente"""
        if self._redis:
            try:
                self._redis.delete(self._key_contexto(user_id))
            except Exception as e:
                print(f"[Memória] Erro ao limpar contexto: {e}")
        if user_id in self._contextos_fallback:
            del self._contextos_fallback[user_id]

    def limpar_historico(self, user_id: str):
        """Limpa histórico do usuário"""
        if self._redis:
            try:
                self._redis.delete(self._key_historico(user_id))
                self._redis.delete(self._key_contexto(user_id))
            except Exception as e:
                print(f"[Memória] Erro ao limpar histórico: {e}")
        if user_id in self._memorias_fallback:
            del self._memorias_fallback[user_id]
        self.limpar_contexto(user_id)


# Instância global de memória (agora com Redis)
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

IMPORTANTE - CONTEXTO DE TRANSAÇÕES:
- Você receberá uma lista das ÚLTIMAS TRANSAÇÕES do usuário
- Quando o usuário perguntar sobre "essa", "a última", "foi salva", "registrou" - SEMPRE consulte a lista de últimas transações
- A PRIMEIRA transação da lista é a MAIS RECENTE (última registrada)
- Use os dados reais das transações (valor, data, descrição) para responder

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
  "mensagem": "💸 Registrei sua despesa!\n\n💵 R$ 50,00\n📝 Almoço\n🏷️ Alimentação\n\n✅ Registrado! Se algo estiver errado, me avisa.",
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
            nome_usuario = contexto_extra.get("nome_usuario", "")
            if nome_usuario:
                contexto_msgs += f"\n\nNOME DO USUÁRIO: {nome_usuario} (use esse nome para se referir ao usuário de forma personalizada)"

            ultimas_transacoes = contexto_extra.get("ultimas_transacoes", "")
            if ultimas_transacoes:
                contexto_msgs += f"\n\nÚLTIMAS TRANSAÇÕES DO USUÁRIO (mais recente primeiro):\n{ultimas_transacoes}\n(Use essas informações para responder perguntas sobre transações recentes)"
                print(f"[Agente] Contexto transações:\n{ultimas_transacoes}")

        # System prompt com data atual
        system = self.system_prompt.replace("{data_hoje}", datetime.now().strftime("%Y-%m-%d"))
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

        # Sanitiza o JSON: escapa quebras de linha dentro de strings
        # O LLM às vezes retorna newlines literais dentro de valores string
        def sanitize_json_strings(s: str) -> str:
            """Escapa newlines literais dentro de strings JSON"""
            result = []
            in_string = False
            escape_next = False
            for char in s:
                if escape_next:
                    result.append(char)
                    escape_next = False
                elif char == '\\':
                    result.append(char)
                    escape_next = True
                elif char == '"':
                    result.append(char)
                    in_string = not in_string
                elif in_string and char == '\n':
                    result.append('\\n')  # Escapa newline literal
                elif in_string and char == '\r':
                    result.append('')  # Remove carriage return
                else:
                    result.append(char)
            return ''.join(result)

        content = sanitize_json_strings(content)

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
        categorias: List[Dict] = None,
        contexto_extra: Dict = None
    ) -> RespostaAgente:
        """Processa transcrição de áudio"""
        # Mescla contexto extra com info de áudio
        contexto = {"origem": "audio", "transcricao": transcricao}
        if contexto_extra:
            contexto.update(contexto_extra)

        return await self.processar_mensagem(
            user_id=user_id,
            mensagem=transcricao,
            categorias=categorias,
            contexto_extra=contexto
        )

    async def processar_imagem(
        self,
        user_id: str,
        dados_imagem: Dict,
        caption: str = "",
        categorias: List[Dict] = None,
        contexto_extra: Dict = None
    ) -> RespostaAgente:
        """Processa dados extraídos de imagem"""

        # Se a visão não entendeu e tem pergunta, retorna a pergunta diretamente
        if not dados_imagem.get("entendeu", True) and dados_imagem.get("pergunta"):
            # Salva contexto para continuar depois
            memoria.set_contexto(user_id, {
                "aguardando": "esclarecimento_imagem",
                "dados_imagem_parcial": dados_imagem
            })

            return RespostaAgente(
                acao="perguntar",
                mensagem=f"📷 {dados_imagem['pergunta']}",
                transacao=None,
                aguardando="esclarecimento_imagem"
            )

        # Se entendeu e tem valor, prepara para registrar
        if dados_imagem.get("entendeu") and dados_imagem.get("valor", 0) > 0:
            # Monta descrição completa
            descricao = dados_imagem.get("descricao", "")
            estabelecimento = dados_imagem.get("estabelecimento", "")
            if estabelecimento and estabelecimento not in descricao:
                descricao = f"{descricao} - {estabelecimento}".strip(" -")

            transacao = TransacaoExtraida(
                tipo=dados_imagem.get("tipo", "despesa"),
                valor=float(dados_imagem["valor"]),
                descricao=descricao,
                categoria=dados_imagem.get("categoria_sugerida", "Outros"),
                data=dados_imagem.get("data_documento") or datetime.now().strftime("%Y-%m-%d"),
                confianca=float(dados_imagem.get("confianca", 0.8))
            )

            # Monta mensagem de confirmação
            obs = dados_imagem.get("observacoes", "")
            msg = f"📷 Encontrei na imagem:\n\n"
            msg += f"💵 R$ {transacao.valor:,.2f}\n"
            msg += f"📝 {transacao.descricao}\n"
            msg += f"🏷️ {transacao.categoria}\n"
            if obs:
                msg += f"📌 {obs}\n"
            msg += f"\n✅ Registrado! Se algo estiver errado, me avisa."

            # Salva no histórico
            memoria.add_mensagem(user_id, "user", f"[Imagem] {caption}" if caption else "[Imagem enviada]")
            memoria.add_mensagem(user_id, "assistant", msg)

            return RespostaAgente(
                acao="registrar",
                mensagem=msg,
                transacao=transacao,
                aguardando=None
            )

        # Fallback: processa como mensagem normal com contexto da imagem
        mensagem = caption if caption else "Enviei uma foto de comprovante"

        # Merge contexto_extra se vier
        ctx = {
            "origem": "imagem",
            "dados_extraidos": dados_imagem
        }
        if contexto_extra:
            ctx.update(contexto_extra)

        return await self.processar_mensagem(
            user_id=user_id,
            mensagem=mensagem,
            categorias=categorias,
            contexto_extra=ctx
        )


# ============================================================================
# INSTÂNCIA GLOBAL
# ============================================================================

agente = AgenteFinanceiro()
