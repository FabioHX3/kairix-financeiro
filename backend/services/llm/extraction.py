"""
Extração de transações de texto usando LLM.
"""

import logging
import re
from datetime import UTC, datetime

from backend.services.llm.client import OpenRouterClient, convert_relative_date, parse_llm_response

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extrai informações de transações de texto."""

    def __init__(self, client: OpenRouterClient):
        self.client = client

    async def extract_transaction(
        self,
        texto: str,
        categorias_disponiveis: list,
    ) -> dict:
        """
        Extrai informações de transação financeira de um texto usando LLM.

        Args:
            texto: Mensagem do usuário
            categorias_disponiveis: Lista de categorias disponíveis

        Returns:
            Dicionário com dados extraídos
        """
        cats_receitas = [c for c in categorias_disponiveis if c["tipo"] == "receita"]
        cats_despesas = [c for c in categorias_disponiveis if c["tipo"] == "despesa"]

        categorias_texto = "RECEITAS: " + ", ".join([f"{c['nome']}" for c in cats_receitas])
        categorias_texto += "\nDESPESAS: " + ", ".join([f"{c['nome']}" for c in cats_despesas])

        prompt = f"""Você é um assistente financeiro brasileiro especializado em extrair informações de transações financeiras de mensagens informais.

Analise a seguinte mensagem do usuário e extraia as informações financeiras:
"{texto}"

Categorias disponíveis no sistema:
{categorias_texto}

IMPORTANTE: Retorne APENAS um JSON válido (sem markdown, sem explicações, sem ```json```) com esta estrutura:
{{
  "tipo": "receita" ou "despesa",
  "valor": número decimal (ex: 150.50),
  "descricao": "descrição clara e curta da transação",
  "categoria_sugerida": "nome exato de uma das categorias disponíveis acima",
  "data_relativa": "hoje", "ontem", ou data no formato "YYYY-MM-DD",
  "confianca": número de 0 a 1,
  "entendeu": true ou false,
  "pergunta": "pergunta para o usuário se não entendeu algo" ou null
}}

REGRAS DE CLASSIFICAÇÃO:
- Palavras como "gastei", "paguei", "comprei", "despesa", "conta", "boleto" = DESPESA
- Palavras como "recebi", "ganhei", "entrou", "salário", "pagamento", "vendi" = RECEITA
- Valor sempre POSITIVO (apenas números)
- Se a data não for mencionada, use "hoje"
- Escolha a categoria mais adequada da lista acima

REGRAS DE CONFIANÇA:
- confianca >= 0.8: Informações claras e completas
- confianca 0.5-0.7: Algumas informações ambíguas
- confianca < 0.5: Muita ambiguidade, precisa confirmar
- entendeu = false: Não conseguiu extrair informações essenciais (valor ou tipo)

REGRAS DE PERGUNTA:
- Se não encontrar o VALOR, pergunte: "Qual foi o valor?"
- Se não souber se é receita ou despesa, pergunte: "Isso foi um gasto ou um recebimento?"
- Se encontrou tudo claramente, pergunta deve ser null

Exemplos:
- "gastei 50 no almoço" → tipo: despesa, valor: 50, categoria: Alimentação, confianca: 0.95
- "recebi 1500 de salário" → tipo: receita, valor: 1500, categoria: Salário, confianca: 0.95
- "comprei umas coisas" → entendeu: false, pergunta: "Qual foi o valor da compra?"
- "150 reais" → entendeu: false, pergunta: "Isso foi um gasto ou um recebimento?"
"""

        try:
            response = await self.client.call(prompt, timeout=30)
            resultado = parse_llm_response(response)

            resultado["data_transacao"] = convert_relative_date(
                resultado.get("data_relativa", "hoje")
            )

            if "entendeu" not in resultado:
                resultado["entendeu"] = resultado.get("confianca", 0) >= 0.5
            if "pergunta" not in resultado:
                resultado["pergunta"] = None

            return resultado

        except Exception as e:
            logger.error(f"Erro ao processar com LLM: {e}")
            return self._basic_extraction(texto, categorias_disponiveis)

    def _basic_extraction(
        self,
        texto: str,
        categorias_disponiveis: list,
    ) -> dict:
        """Extração básica sem LLM como fallback."""
        padroes_valor = [
            r"R?\$?\s*(\d+(?:[.,]\d{1,2})?)",
            r"(\d+(?:[.,]\d{1,2})?)\s*(?:reais?|conto|pila)",
        ]

        valor = 0.0
        for padrao in padroes_valor:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                valor_str = match.group(1).replace(",", ".")
                valor = float(valor_str)
                break

        palavras_receita = [
            "recebi",
            "recebimento",
            "ganho",
            "ganhei",
            "salário",
            "salario",
            "pagamento recebido",
            "entrou",
            "vendi",
            "vendeu",
        ]
        palavras_despesa = [
            "gastei",
            "paguei",
            "comprei",
            "despesa",
            "gasto",
            "conta",
            "boleto",
            "pagar",
            "comprar",
            "gastar",
        ]

        tipo = None
        for palavra in palavras_receita:
            if palavra in texto.lower():
                tipo = "receita"
                break

        if not tipo:
            for palavra in palavras_despesa:
                if palavra in texto.lower():
                    tipo = "despesa"
                    break

        entendeu = True
        pergunta = None

        if valor == 0:
            entendeu = False
            pergunta = "Qual foi o valor?"
        elif not tipo:
            entendeu = False
            pergunta = "Isso foi um gasto ou um recebimento?"
            tipo = "despesa"

        return {
            "tipo": tipo or "despesa",
            "valor": valor,
            "descricao": texto[:200],
            "categoria_sugerida": "Outros",
            "data_transacao": datetime.now(UTC),
            "confianca": 0.3,
            "entendeu": entendeu,
            "pergunta": pergunta,
        }
