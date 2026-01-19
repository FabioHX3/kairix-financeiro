"""
LLM Service - Processamento com OpenRouter (Gemini).

Módulos:
- client: Cliente base para OpenRouter API
- transcription: Transcrição de áudio
- extraction: Extração de texto
- vision: Análise de imagens
"""

from backend.services.llm.client import OpenRouterClient
from backend.services.llm.extraction import TextExtractor
from backend.services.llm.transcription import AudioTranscriber
from backend.services.llm.vision import ImageAnalyzer


class LLMService:
    """
    Serviço unificado para processamento com LLM via OpenRouter.

    Mantém compatibilidade com a interface anterior.
    """

    def __init__(self):
        self.client = OpenRouterClient()
        self._transcriber = AudioTranscriber(self.client)
        self._extractor = TextExtractor(self.client)
        self._analyzer = ImageAnalyzer(self.client)

    # =========================================================================
    # Text Extraction
    # =========================================================================

    async def extrair_transacao_de_texto(
        self,
        texto: str,
        categorias_disponiveis: list,
    ) -> dict:
        """Extrai informações de transação financeira de um texto."""
        return await self._extractor.extract_transaction(texto, categorias_disponiveis)

    # =========================================================================
    # Audio Transcription
    # =========================================================================

    async def transcrever_audio(self, audio_url: str) -> tuple[str, bool]:
        """Transcreve áudio para texto usando Gemini via OpenRouter."""
        return await self._transcriber.transcribe_from_url(audio_url)

    async def transcrever_audio_base64(
        self,
        base64_data: str,
        mimetype: str = "audio/ogg",
    ) -> tuple[str, bool]:
        """Transcreve áudio a partir de base64."""
        return await self._transcriber.transcribe_from_base64(base64_data, mimetype)

    # =========================================================================
    # Image Analysis
    # =========================================================================

    async def extrair_de_imagem(self, image_url: str, caption: str = "") -> dict:
        """Extrai informações de nota fiscal/recibo de uma imagem."""
        return await self._analyzer.extract_from_url(image_url, caption)

    async def extrair_de_imagem_base64(
        self,
        base64_data: str,
        mimetype: str = "image/jpeg",
        caption: str = "",
    ) -> dict:
        """Extrai informações de imagem a partir de base64."""
        return await self._analyzer.extract_from_base64(base64_data, mimetype, caption)

    async def extrair_extrato_multiplo(
        self,
        base64_data: str,
        mimetype: str = "image/jpeg",
        caption: str = "",
    ) -> dict:
        """Extrai MÚLTIPLAS transações de um extrato bancário/fatura."""
        return await self._analyzer.extract_statement(base64_data, mimetype, caption)

    async def extrair_de_pdf_base64(self, base64_data: str) -> dict:
        """Extrai transações de um PDF de extrato bancário."""
        return await self._analyzer.extract_from_pdf(base64_data)

    # =========================================================================
    # Message Generation
    # =========================================================================

    def gerar_mensagem_confirmacao(
        self,
        transacao_info: dict,
        transacao_id: int | None = None,
    ) -> str:
        """Gera mensagem de confirmação para enviar ao usuário."""
        tipo_emoji = "💸" if transacao_info["tipo"] == "despesa" else "💰"
        tipo_texto = "Despesa" if transacao_info["tipo"] == "despesa" else "Receita"

        valor = transacao_info.get("valor", 0)
        descricao = transacao_info.get("descricao", "Sem descrição")
        categoria = transacao_info.get("categoria_sugerida", "Outros")

        return f"""{tipo_emoji} *{tipo_texto} registrada!*

💵 *Valor:* R$ {valor:.2f}
📝 *Descrição:* {descricao}
🏷️ *Categoria:* {categoria}

✅ Está correto? Responda:
• *SIM* para confirmar
• *CORRIGIR* para editar
• Ou envie nova transação"""

    def gerar_pergunta_esclarecimento(self, pergunta: str) -> str:
        """Gera mensagem de pergunta quando não entendeu algo."""
        return f"""🤔 *Preciso de uma informação*

{pergunta}

Por favor, responda para eu registrar corretamente."""

    def gerar_mensagem_erro(self) -> str:
        """Gera mensagem de erro genérica."""
        return """❌ *Ops! Algo deu errado*

Não consegui processar sua mensagem. Por favor, tente novamente.

💡 *Dica:* Envie mensagens como:
• "Gastei 50 reais no almoço"
• "Recebi 1500 de salário"
• Foto de nota fiscal"""


# Instância global para compatibilidade
llm_service = LLMService()
