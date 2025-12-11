"""
Extractor Agent - Especialista em extrair dados de transações.

Responsabilidades:
- Extrair valor, descrição, tipo de texto livre
- Processar fotos (notas fiscais, comprovantes, QR codes PIX)
- Processar transcrições de áudio
- Detectar múltiplos itens e perguntar como registrar
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List

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


class ExtractorAgent(BaseAgent):
    """
    Agente especializado em extrair dados de transações financeiras.

    Processa:
    - Texto livre ("gastei 50 no mercado")
    - Fotos de notas fiscais e comprovantes
    - Transcrições de áudio
    """

    name = "extractor"
    description = "Especialista em extrair transações"

    # Categorias padrão (fallback se não vier do banco)
    CATEGORIAS_DESPESA = [
        "Alimentacao", "Transporte", "Saude", "Educacao",
        "Lazer", "Casa", "Vestuario", "Outros"
    ]
    CATEGORIAS_RECEITA = [
        "Salario", "Freelance", "Investimentos", "Vendas", "Aluguel", "Outros"
    ]

    def __init__(self, db_session=None, redis_client=None):
        super().__init__(db_session, redis_client)

        self.llm = ChatOpenAI(
            model=settings.OPENROUTER_MODEL,
            openai_api_key=settings.OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.2,
            max_tokens=1000,
        )

    def can_handle(self, context: AgentContext) -> bool:
        """Pode processar se intenção é REGISTRAR"""
        return context.intent == IntentType.REGISTRAR

    async def process(self, context: AgentContext) -> AgentResponse:
        """
        Extrai dados de transação da mensagem.

        1. Tenta extração rápida por regex
        2. Se não conseguir, usa LLM
        3. Verifica padrões do usuário para categoria
        4. Solicita confirmação se confiança < 90%
        """
        self.log(f"Extraindo de: {context.mensagem_original[:50]}...")

        # 1. Tenta extração rápida
        dados_rapidos = self._extracao_rapida(context.mensagem_original)

        if dados_rapidos and dados_rapidos.get("valor"):
            self.log(f"Extração rápida: {dados_rapidos}")
            dados = dados_rapidos
        else:
            # 2. Usa LLM para extração
            dados = await self._extracao_llm(context)

        if not dados or not dados.get("valor"):
            return AgentResponse(
                sucesso=False,
                mensagem="Nao consegui identificar o valor. Pode repetir?\n\n"
                        "Exemplo: \"Gastei 50 no mercado\"",
                requer_confirmacao=False
            )

        # 3. Busca padrão do usuário para categoria
        padrao = await memory_service.buscar_padrao(
            context.usuario_id,
            dados.get("descricao", "")
        )

        if padrao:
            dados["categoria"] = padrao.get("categoria_nome", dados.get("categoria", "Outros"))
            dados["categoria_id"] = padrao.get("categoria_id")
            dados["confianca"] = min(dados.get("confianca", 0.5) + 0.2, 1.0)
            self.log(f"Padrão encontrado: {padrao['descricao_norm']} -> {dados['categoria']}")

        # 4. Decide se pede confirmação
        prefs = await memory_service.obter_preferencias(context.usuario_id)
        auto_confirmar = prefs.get("auto_confirmar_confianca", 0.90)

        if dados.get("confianca", 0) >= auto_confirmar:
            # Alta confiança: registra direto
            return await self._registrar_direto(context, dados)
        else:
            # Pede confirmação
            return await self._pedir_confirmacao(context, dados)

    def _extracao_rapida(self, texto: str) -> Optional[Dict]:
        """
        Extração rápida usando regex.
        Cobre os casos mais comuns sem precisar de LLM.
        """
        texto_lower = texto.lower()
        resultado = {
            "tipo": None,
            "valor": None,
            "descricao": None,
            "categoria": "Outros",
            "data": datetime.now().strftime("%Y-%m-%d"),
            "confianca": 0.0
        }

        # Detecta tipo
        if any(p in texto_lower for p in ["gast", "pagu", "compre", "despesa"]):
            resultado["tipo"] = "despesa"
            resultado["confianca"] = 0.7
        elif any(p in texto_lower for p in ["receb", "entr", "ganhe", "receita", "salario"]):
            resultado["tipo"] = "receita"
            resultado["confianca"] = 0.7

        # Extrai valor
        patterns_valor = [
            r'r\$\s*(\d+[.,]?\d*)',                    # R$ 50, R$ 50,00
            r'(\d+[.,]?\d*)\s*reais?',                 # 50 reais
            r'(\d+[.,]?\d*)\s*conto',                  # 50 contos
            r'(?:gastei|paguei|recebi|ganhei)\s*(\d+[.,]?\d*)',  # gastei 50
        ]

        for pattern in patterns_valor:
            match = re.search(pattern, texto_lower)
            if match:
                valor_str = match.group(1).replace(',', '.')
                try:
                    resultado["valor"] = float(valor_str)
                    break
                except ValueError:
                    continue

        if not resultado["valor"]:
            return None

        # Extrai descrição (palavras após o valor ou palavras-chave)
        # Remove valor e extrai resto
        desc_patterns = [
            r'(?:no|na|em|de)\s+(.+?)(?:\s+(?:hoje|ontem|anteontem))?$',
            r'(?:gastei|paguei|com)\s+\d+[.,]?\d*\s*(?:reais?)?\s*(?:no|na|em|de)?\s*(.+)',
        ]

        for pattern in desc_patterns:
            match = re.search(pattern, texto_lower)
            if match:
                resultado["descricao"] = match.group(1).strip().title()
                break

        if not resultado["descricao"]:
            # Usa palavras significativas
            palavras = texto.split()
            palavras_sig = [p for p in palavras if len(p) > 3 and not p.isdigit()]
            resultado["descricao"] = ' '.join(palavras_sig[:3]).title() if palavras_sig else "Transacao"

        # Detecta categoria básica
        resultado["categoria"] = self._inferir_categoria(texto_lower, resultado["tipo"])

        # Detecta data
        if "ontem" in texto_lower:
            resultado["data"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "anteontem" in texto_lower:
            resultado["data"] = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        return resultado if resultado["valor"] else None

    def _inferir_categoria(self, texto: str, tipo: str) -> str:
        """Infere categoria baseado em palavras-chave"""
        if tipo == "receita":
            if any(p in texto for p in ["salario", "salário", "contracheque"]):
                return "Salario"
            if any(p in texto for p in ["freelance", "freela", "job", "projeto"]):
                return "Freelance"
            if any(p in texto for p in ["dividendo", "rendimento", "investimento"]):
                return "Investimentos"
            if any(p in texto for p in ["vend", "vendeu", "venda"]):
                return "Vendas"
            return "Outros"
        else:
            # Despesa
            if any(p in texto for p in ["almoc", "jant", "cafe", "restaurante", "mercado", "comida", "lanche", "pizza"]):
                return "Alimentacao"
            if any(p in texto for p in ["uber", "99", "taxi", "gasolina", "combustivel", "onibus", "metro"]):
                return "Transporte"
            if any(p in texto for p in ["medic", "farmacia", "hospital", "consulta", "exame"]):
                return "Saude"
            if any(p in texto for p in ["curso", "livro", "escola", "faculdade", "mensalidade"]):
                return "Educacao"
            if any(p in texto for p in ["cinema", "netflix", "spotify", "jogo", "bar", "festa"]):
                return "Lazer"
            if any(p in texto for p in ["aluguel", "condominio", "luz", "agua", "internet", "gas"]):
                return "Casa"
            if any(p in texto for p in ["roupa", "sapato", "tenis", "camisa", "calcado"]):
                return "Vestuario"
            return "Outros"

    async def _extracao_llm(self, context: AgentContext) -> Dict:
        """Extrai dados usando LLM"""
        prompt = f"""Extraia os dados financeiros da mensagem do usuario.

IMPORTANTE:
- Se for gasto/despesa/pagamento, tipo = "despesa"
- Se for recebimento/entrada/ganho, tipo = "receita"
- Se nao conseguir determinar o tipo, pergunte
- Valor deve ser numero positivo
- Data: se nao mencionada, use HOJE. Se "ontem", calcule.
- Confianca: 0.0 a 1.0 (quanto tem certeza dos dados)

Mensagem: "{context.mensagem_original}"
Data de hoje: {datetime.now().strftime("%Y-%m-%d")}

Responda APENAS com JSON:
{{
  "tipo": "despesa" ou "receita",
  "valor": numero,
  "descricao": "descricao curta",
  "categoria": "categoria sugerida",
  "data": "YYYY-MM-DD",
  "confianca": 0.0 a 1.0,
  "multiplos_itens": false,
  "itens": []
}}

Categorias despesa: {', '.join(self.CATEGORIAS_DESPESA)}
Categorias receita: {', '.join(self.CATEGORIAS_RECEITA)}"""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="Voce extrai dados financeiros de texto. Responda apenas JSON valido."),
                HumanMessage(content=prompt)
            ])

            # Parseia resposta
            content = response.content.strip()

            # Remove markdown se houver
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)

            # Encontra JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group()

            dados = json.loads(content)
            self.log(f"Extracao LLM: {dados}")

            return dados

        except Exception as e:
            self.log(f"Erro na extracao LLM: {e}")
            return {}

    async def _registrar_direto(self, context: AgentContext, dados: Dict) -> AgentResponse:
        """Registra transação diretamente (alta confiança)"""
        from backend.models.models import Transacao, TipoTransacao, OrigemRegistro, gerar_codigo_unico

        if not self.db:
            return AgentResponse(
                sucesso=False,
                mensagem="Erro interno. Tente novamente."
            )

        try:
            # Gera código
            codigo = gerar_codigo_unico(self.db)

            # Mapeia tipo
            tipo = TipoTransacao.DESPESA if dados.get("tipo") == "despesa" else TipoTransacao.RECEITA

            # Mapeia origem
            origem_map = {
                "whatsapp_texto": OrigemRegistro.WHATSAPP_TEXTO,
                "whatsapp_audio": OrigemRegistro.WHATSAPP_AUDIO,
                "whatsapp_imagem": OrigemRegistro.WHATSAPP_IMAGEM,
            }
            origem = origem_map.get(context.origem.value, OrigemRegistro.WHATSAPP_TEXTO)

            # Busca categoria_id se não tiver
            categoria_id = dados.get("categoria_id")
            if not categoria_id:
                categoria_id = await self._buscar_categoria_id(dados.get("categoria", "Outros"), tipo.value)

            # Cria transação
            transacao = Transacao(
                codigo=codigo,
                usuario_id=context.usuario_id,
                categoria_id=categoria_id,
                tipo=tipo,
                valor=dados["valor"],
                descricao=dados.get("descricao", ""),
                data_transacao=datetime.strptime(dados.get("data", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"),
                origem=origem,
                mensagem_original=context.mensagem_original,
                confianca_ia=dados.get("confianca", 0.0)
            )

            self.db.add(transacao)
            self.db.commit()

            self.log(f"Registrado: {codigo} - R$ {transacao.valor}")

            # Salva padrão
            await memory_service.salvar_padrao_usuario(
                usuario_id=context.usuario_id,
                descricao=dados.get("descricao", ""),
                categoria_id=categoria_id,
                tipo=tipo.value
            )

            # Monta resposta
            tipo_emoji = "💸" if tipo == TipoTransacao.DESPESA else "💰"
            msg = f"{tipo_emoji} Registrado!\n\n"
            msg += f"R$ {dados['valor']:,.2f}\n"
            msg += f"{dados.get('descricao', '')}\n"
            msg += f"Categoria: {dados.get('categoria', 'Outros')}\n"
            msg += f"Codigo: {codigo}\n\n"
            msg += "Algo errado? Me avisa!"

            # Salva no histórico
            await memory_service.salvar_contexto_conversa(
                context.telefone,
                context.mensagem_original,
                msg,
                {"transacao_codigo": codigo}
            )

            return AgentResponse(
                sucesso=True,
                mensagem=msg,
                dados={"codigo": codigo, "valor": dados["valor"]},
                codigo_transacao=codigo
            )

        except Exception as e:
            self.db.rollback()
            self.log(f"Erro ao registrar: {e}")
            return AgentResponse(
                sucesso=False,
                mensagem="Erro ao registrar. Tente novamente."
            )

    async def _pedir_confirmacao(self, context: AgentContext, dados: Dict) -> AgentResponse:
        """Pede confirmação do usuário antes de registrar"""

        # Salva ação pendente
        await memory_service.salvar_acao_pendente(
            context.telefone,
            "registrar_transacao",
            {
                "tipo": dados.get("tipo"),
                "valor": dados.get("valor"),
                "descricao": dados.get("descricao"),
                "categoria": dados.get("categoria"),
                "categoria_id": dados.get("categoria_id"),
                "data": dados.get("data"),
                "confianca": dados.get("confianca", 0)
            }
        )

        # Monta mensagem de confirmação
        tipo_emoji = "💸" if dados.get("tipo") == "despesa" else "💰"
        tipo_texto = "Despesa" if dados.get("tipo") == "despesa" else "Receita"

        msg = f"Entendi isso:\n\n"
        msg += f"{tipo_emoji} {tipo_texto}\n"
        msg += f"R$ {dados['valor']:,.2f}\n"
        msg += f"{dados.get('descricao', '')}\n"
        msg += f"Categoria: {dados.get('categoria', 'Outros')}\n\n"
        msg += "Confirma? (sim/nao)"

        return AgentResponse(
            sucesso=True,
            mensagem=msg,
            requer_confirmacao=True,
            acao_pendente={
                "tipo": "registrar_transacao",
                "dados": dados
            },
            confianca=dados.get("confianca", 0)
        )

    async def _buscar_categoria_id(self, nome: str, tipo: str) -> Optional[int]:
        """Busca ID da categoria no banco"""
        if not self.db:
            return None

        from backend.models.models import Categoria, TipoTransacao

        tipo_enum = TipoTransacao.DESPESA if tipo == "despesa" else TipoTransacao.RECEITA

        categoria = self.db.query(Categoria).filter(
            Categoria.nome.ilike(f"%{nome}%"),
            Categoria.tipo == tipo_enum
        ).first()

        return categoria.id if categoria else None


# Instância global
extractor_agent = ExtractorAgent()
