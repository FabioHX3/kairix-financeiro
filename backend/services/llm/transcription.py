"""
Transcrição de áudio usando Gemini via OpenRouter.
"""

import base64
import logging

import httpx

from backend.services.llm.client import OpenRouterClient

logger = logging.getLogger(__name__)


class AudioTranscriber:
    """Serviço de transcrição de áudio."""

    def __init__(self, client: OpenRouterClient):
        self.client = client

    async def transcribe_from_url(self, audio_url: str) -> tuple[str, bool]:
        """
        Transcreve áudio a partir de URL.

        Args:
            audio_url: URL do arquivo de áudio

        Returns:
            Tuple (texto_transcrito, sucesso)
        """
        if not self.client.api_key:
            logger.warning("[Audio] OPENROUTER_API_KEY não configurada")
            return "", False

        try:
            logger.debug(f"[Audio] Baixando áudio de: {audio_url}")
            async with httpx.AsyncClient() as client:
                response = await client.get(audio_url, timeout=30)
                response.raise_for_status()

            audio_base64 = base64.b64encode(response.content).decode("utf-8")

            # Detecta formato do áudio
            content_type = response.headers.get("content-type", "audio/ogg")
            audio_format = self._detect_format(content_type)

            return await self._transcribe(audio_base64, audio_format)

        except Exception as e:
            logger.error(f"[Audio] Erro: {e}")
            return "", False

    async def transcribe_from_base64(
        self,
        base64_data: str,
        mimetype: str = "audio/ogg",
    ) -> tuple[str, bool]:
        """
        Transcreve áudio a partir de base64.

        Args:
            base64_data: Dados do áudio em base64
            mimetype: Tipo MIME do áudio

        Returns:
            Tuple (texto_transcrito, sucesso)
        """
        if not self.client.api_key:
            logger.warning("[Audio] OPENROUTER_API_KEY não configurada")
            return "", False

        audio_format = self._detect_format(mimetype)
        return await self._transcribe(base64_data, audio_format)

    def _detect_format(self, content_type: str) -> str:
        """Detecta formato do áudio a partir do content-type."""
        if "mp3" in content_type or "mpeg" in content_type:
            return "mp3"
        elif "wav" in content_type:
            return "wav"
        elif "mp4" in content_type or "m4a" in content_type:
            return "mp4"
        elif "webm" in content_type:
            return "webm"
        else:
            return "ogg"

    async def _transcribe(
        self,
        audio_base64: str,
        audio_format: str = "ogg",
    ) -> tuple[str, bool]:
        """Executa a transcrição usando Gemini via OpenRouter."""
        try:
            logger.debug(f"[Audio] Transcrevendo áudio ({audio_format}, {len(audio_base64)} chars)")

            prompt = """Transcreva este áudio em português brasileiro.
Retorne APENAS o texto transcrito, sem explicações ou formatação adicional.
Se o áudio estiver inaudível ou vazio, retorne: [INAUDÍVEL]"""

            texto = await self.client.call_with_audio(
                prompt=prompt,
                audio_base64=audio_base64,
                audio_format=audio_format,
                timeout=60,
            )

            texto = texto.strip()
            logger.debug(f"[Audio] Transcrição: {texto[:100]}...")

            if texto and texto != "[INAUDÍVEL]":
                return texto, True
            else:
                logger.warning("[Audio] Áudio inaudível")
                return "", False

        except Exception as e:
            logger.error(f"[Audio] Erro ao transcrever: {e}")
            return "", False
