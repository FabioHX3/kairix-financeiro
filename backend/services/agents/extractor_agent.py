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
from datetime import datetime, timedelta, timezone
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
from backend.services.agents.personality_agent import personality_agent
from backend.services.agents.learning_agent import learning_agent


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
        dados_rapidos = self._extracao_rapida(context.mensagem_original, context.timezone)

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

        # 2.5. Trata múltiplos itens
        if dados.get("multiplos_itens") and dados.get("itens"):
            return await self._pedir_confirmacao_multiplos(context, dados)

        # 3. Busca padrão do usuário para categoria (do banco)
        padrao = None
        if self.db:
            padrao = await learning_agent.buscar_padrao(
                db=self.db,
                usuario_id=context.usuario_id,
                descricao=dados.get("descricao", ""),
                tipo=dados.get("tipo", "despesa")
            )

        if padrao and padrao.get("encontrado"):
            dados["categoria"] = padrao.get("categoria_nome", dados.get("categoria", "Outros"))
            dados["categoria_id"] = padrao.get("categoria_id")
            # Usa a confiança do padrão salvo no banco
            dados["confianca"] = padrao.get("confianca", 0.5)
            self.log(f"Padrão encontrado: {padrao['palavras_chave']} -> {dados['categoria']} (confiança: {dados['confianca']:.0%})")

        # 4. Decide se pede confirmação (pega preferências do banco)
        auto_confirmar = 0.90  # default
        if self.db:
            prefs = await learning_agent.obter_preferencias(self.db, context.usuario_id)
            auto_confirmar = prefs.get("auto_confirmar_confianca", 0.90)

        if dados.get("confianca", 0) >= auto_confirmar:
            # Alta confiança: registra direto
            return await self._registrar_direto(context, dados)
        else:
            # Pede confirmação
            return await self._pedir_confirmacao(context, dados)

    def _extracao_rapida(self, texto: str, timezone: str = "America/Sao_Paulo") -> Optional[Dict]:
        """
        Extração rápida usando regex.
        Cobre os casos mais comuns sem precisar de LLM.
        Retorna None se detectar múltiplas transações (vai para LLM).
        """
        texto_lower = texto.lower()

        # Detecta se tem múltiplas transações (receita E despesa)
        tem_despesa = any(p in texto_lower for p in ["gast", "pagu", "compre", "despesa"])
        tem_receita = any(p in texto_lower for p in ["receb", "entr", "ganhe", "receita", "salario", "salário"])

        # Se tem ambos tipos, vai para LLM (múltiplas transações)
        if tem_despesa and tem_receita:
            self.log("Múltiplas transações detectadas, usando LLM")
            return None

        # Conta quantos valores numéricos existem (pode indicar múltiplos itens)
        valores_encontrados = re.findall(r'\b\d+[.,]?\d*\b', texto_lower)
        valores_significativos = [v for v in valores_encontrados if float(v.replace(',', '.')) >= 5]
        if len(valores_significativos) > 2:
            self.log(f"Múltiplos valores detectados ({len(valores_significativos)}), usando LLM")
            return None

        from zoneinfo import ZoneInfo
        agora = datetime.now(ZoneInfo(timezone))

        resultado = {
            "tipo": None,
            "valor": None,
            "descricao": None,
            "categoria": "Outros",
            "data": agora.strftime("%Y-%m-%d"),
            "confianca": 0.0
        }

        # Detecta tipo (prioridade para receita se tiver "recebi/salário")
        if tem_receita:
            resultado["tipo"] = "receita"
            resultado["confianca"] = 0.7
        elif tem_despesa:
            resultado["tipo"] = "despesa"
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

        # Limpa e melhora a descrição
        resultado["descricao"] = self._limpar_descricao(resultado["descricao"], texto)

        # Detecta categoria básica
        resultado["categoria"] = self._inferir_categoria(texto_lower, resultado["tipo"])

        # Detecta data (usa agora com timezone)
        if "ontem" in texto_lower:
            resultado["data"] = (agora - timedelta(days=1)).strftime("%Y-%m-%d")
        elif "anteontem" in texto_lower:
            resultado["data"] = (agora - timedelta(days=2)).strftime("%Y-%m-%d")

        return resultado if resultado["valor"] else None

    def _limpar_descricao(self, descricao: str, texto_original: str) -> str:
        """
        Limpa e melhora a descrição extraída.
        - Remove verbos financeiros (gastei, paguei, recebi)
        - Remove valores numéricos e "reais"
        - Remove palavras temporais (agora, hoje, ontem)
        - Remove artigos e preposições
        """
        if not descricao:
            return "Transação"

        desc = descricao.strip()

        # Palavras a remover (verbos, valores, temporais, artigos)
        palavras_remover = {
            # Verbos financeiros
            "gastei", "gasta", "gastou", "gastamos", "gastar",
            "paguei", "paga", "pagou", "pagamos", "pagar",
            "recebi", "recebeu", "recebemos", "receber",
            "comprei", "comprou", "compramos", "comprar",
            "ganhei", "ganhou", "ganhamos", "ganhar",
            # Valores
            "reais", "real", "r$", "conto", "contos",
            # Temporais
            "agora", "hoje", "ontem", "anteontem", "amanha", "amanhã",
            "já", "ja", "mesmo", "aqui", "ali", "la", "lá",
            "acabei", "acabou",
            # Artigos e preposições
            "de", "da", "do", "no", "na", "em", "a", "o", "um", "uma",
            "com", "para", "pro", "pra",
        }

        # Remove números (valores)
        desc = re.sub(r'\b\d+[.,]?\d*\b', '', desc)

        # Remove palavras indesejadas
        palavras = desc.split()
        palavras = [p for p in palavras if p.lower() not in palavras_remover]
        desc = " ".join(palavras).strip()

        # Remove artigos/preposições soltos no final
        sufixos_remover = [" de", " da", " do", " no", " na", " em", " a", " o"]
        for sufixo in sufixos_remover:
            if desc.lower().endswith(sufixo):
                desc = desc[:-len(sufixo)].strip()

        # Melhora nomenclatura de contas comuns
        # Usa regex para palavras inteiras (evita "gas" em "gastei")
        texto_lower = texto_original.lower()
        palavras_texto = set(re.findall(r'\b\w+\b', texto_lower))

        mapeamento_contas = {
            "luz": ("Conta de Luz", ["luz", "energia", "eletrica", "cpfl", "cemig", "enel"]),
            "agua": ("Conta de Água", ["agua", "água", "saneamento", "sabesp", "copasa"]),
            "gas": ("Conta de Gás", ["gás", "comgas"]),  # Removido "gas" sozinho para evitar conflito
            "internet": ("Internet", ["internet", "wifi", "banda"]),
            "telefone": ("Telefone", ["telefone", "celular"]),
            "aluguel": ("Aluguel", ["aluguel", "locacao"]),
            "condominio": ("Condomínio", ["condominio", "condomínio", "condo"]),
            "iptu": ("IPTU", ["iptu"]),
            "ipva": ("IPVA", ["ipva"]),
        }

        for chave, (nome_bonito, palavras_chave) in mapeamento_contas.items():
            # Verifica se alguma palavra-chave está como palavra inteira
            if any(p in palavras_texto for p in palavras_chave):
                return nome_bonito

        # Se descrição ficou vazia, extrai do texto original
        if not desc or len(desc) < 2:
            palavras = texto_original.split()
            palavras_sig = [p for p in palavras if len(p) > 3 and not p.isdigit()
                           and p.lower() not in ["gastei", "paguei", "recebi", "ganhei", "reais"]]
            desc = " ".join(palavras_sig[:3]).title() if palavras_sig else "Transação"

        return desc.title() if desc else "Transação"

    def _inferir_categoria(self, texto: str, tipo: str) -> str:
        """Infere categoria baseado em palavras-chave (palavras inteiras)"""
        # Extrai palavras inteiras para evitar falsos positivos
        palavras = set(re.findall(r'\b\w+\b', texto.lower()))

        if tipo == "receita":
            if palavras & {"salario", "salário", "contracheque"}:
                return "Salario"
            if palavras & {"freelance", "freela", "job", "projeto"}:
                return "Freelance"
            if palavras & {"dividendo", "rendimento", "investimento"}:
                return "Investimentos"
            if palavras & {"venda", "vendas", "vendeu", "vendi"}:
                return "Vendas"
            return "Outros"
        else:
            # Despesa
            if palavras & {"almoco", "almoço", "jantar", "janta", "cafe", "café", "restaurante", "mercado", "comida", "lanche", "pizza"}:
                return "Alimentacao"
            if palavras & {"uber", "99", "taxi", "gasolina", "combustivel", "onibus", "metro", "passagem"}:
                return "Transporte"
            if palavras & {"medico", "médico", "farmacia", "farmácia", "hospital", "consulta", "exame", "remedio", "remédio"}:
                return "Saude"
            if palavras & {"curso", "livro", "escola", "faculdade", "mensalidade"}:
                return "Educacao"
            if palavras & {"cinema", "netflix", "spotify", "jogo", "bar", "festa", "show"}:
                return "Lazer"
            if palavras & {"aluguel", "condominio", "condomínio", "luz", "agua", "água", "internet", "gás"}:
                return "Casa"
            if palavras & {"roupa", "sapato", "tenis", "tênis", "camisa", "calcado", "calçado"}:
                return "Vestuario"
            return "Outros"

    async def _extracao_llm(self, context: AgentContext) -> Dict:
        """Extrai dados usando LLM"""
        from zoneinfo import ZoneInfo
        hoje = datetime.now(ZoneInfo(context.timezone))
        ontem = hoje - timedelta(days=1)

        prompt = f"""Extraia os dados financeiros da mensagem do usuario.

REGRAS:
- gasto/despesa/pagamento = tipo "despesa"
- recebimento/entrada/ganho/salario = tipo "receita"
- Valor deve ser numero positivo
- "hoje" = {hoje.strftime("%Y-%m-%d")}, "ontem" = {ontem.strftime("%Y-%m-%d")}

IMPORTANTE - MULTIPLAS TRANSACOES:
Se a mensagem tiver MAIS DE UMA transacao (ex: "recebi salario e gastei no mercado"),
retorne multiplos_itens=true e liste cada uma em "itens".

Mensagem: "{context.mensagem_original}"

Responda APENAS com JSON:
{{
  "tipo": "despesa" ou "receita",
  "valor": numero,
  "descricao": "descricao curta (2-4 palavras)",
  "categoria": "categoria",
  "data": "YYYY-MM-DD",
  "confianca": 0.0 a 1.0,
  "multiplos_itens": true/false,
  "itens": [
    {{"tipo": "receita", "valor": 5000, "descricao": "Salario", "categoria": "Salario", "data": "YYYY-MM-DD"}},
    {{"tipo": "despesa", "valor": 30, "descricao": "Uber", "categoria": "Transporte", "data": "YYYY-MM-DD"}}
  ]
}}

Se multiplos_itens=false, "itens" deve ser [].
Se multiplos_itens=true, preencha "itens" e deixe tipo/valor/descricao do primeiro item nos campos principais.

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

            # Aplica limpeza de descrição também na extração LLM
            if dados.get("descricao"):
                dados["descricao"] = self._limpar_descricao(
                    dados["descricao"],
                    context.mensagem_original
                )

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
                data_transacao=datetime.strptime(dados.get("data", datetime.now(timezone.utc).strftime("%Y-%m-%d")), "%Y-%m-%d").replace(tzinfo=timezone.utc),
                origem=origem,
                mensagem_original=context.mensagem_original,
                confianca_ia=dados.get("confianca", 0.0)
            )

            self.db.add(transacao)
            self.db.commit()

            self.log(f"Registrado: {codigo} - R$ {transacao.valor}")

            # Salva padrão no banco
            if categoria_id:
                await learning_agent.registrar_padrao(
                    db=self.db,
                    usuario_id=context.usuario_id,
                    descricao=dados.get("descricao", ""),
                    categoria_id=categoria_id,
                    tipo=tipo.value
                )

            # Obtém personalidade do usuário
            personalidade = "amigavel"
            from backend.models import UserPreferences
            prefs = self.db.query(UserPreferences).filter(
                UserPreferences.usuario_id == context.usuario_id
            ).first()
            if prefs:
                personalidade = prefs.personalidade.value

            # Monta resposta com personalidade
            msg = personality_agent.formatar_mensagem_transacao(
                personalidade=personalidade,
                tipo=tipo.value,
                valor=dados["valor"],
                descricao=dados.get("descricao", ""),
                categoria=dados.get("categoria", "Outros"),
                codigo=codigo
            )

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

        # Obtém personalidade do usuário
        personalidade = "amigavel"  # default
        if self.db:
            from backend.models import UserPreferences
            prefs = self.db.query(UserPreferences).filter(
                UserPreferences.usuario_id == context.usuario_id
            ).first()
            if prefs:
                personalidade = prefs.personalidade.value

        # Monta mensagem de confirmação usando personality_agent
        msg = personality_agent.formatar_pedido_confirmacao(
            personalidade=personalidade,
            tipo=dados.get("tipo", "despesa"),
            valor=dados.get("valor", 0),
            descricao=dados.get("descricao", ""),
            categoria=dados.get("categoria", "Outros")
        )

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

    async def _pedir_confirmacao_multiplos(self, context: AgentContext, dados: Dict) -> AgentResponse:
        """Pede confirmação para múltiplas transações"""
        itens = dados.get("itens", [])

        if not itens:
            # Fallback para confirmação simples
            return await self._pedir_confirmacao(context, dados)

        # Salva ação pendente com todos os itens
        await memory_service.salvar_acao_pendente(
            context.telefone,
            "registrar_multiplas",
            {"itens": itens}
        )

        # Monta mensagem listando todos os itens
        msg = f"Encontrei {len(itens)} transacoes:\n\n"

        for i, item in enumerate(itens, 1):
            tipo_emoji = "💸" if item.get("tipo") == "despesa" else "💰"
            tipo_texto = "Despesa" if item.get("tipo") == "despesa" else "Receita"
            valor = item.get("valor", 0)
            desc = item.get("descricao", "")
            cat = item.get("categoria", "Outros")

            msg += f"{i}. {tipo_emoji} {tipo_texto}: R$ {valor:,.2f}\n"
            msg += f"   {desc} ({cat})\n\n"

        msg += "Certo? Diga *sim* para registrar todas!"

        return AgentResponse(
            sucesso=True,
            mensagem=msg,
            requer_confirmacao=True,
            acao_pendente={
                "tipo": "registrar_multiplas",
                "dados": {"itens": itens}
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
