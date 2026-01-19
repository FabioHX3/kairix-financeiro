"""
Cliente base para OpenRouter API.
"""

import json
import logging
import re
from datetime import UTC, datetime, timedelta

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Cliente base para chamadas à API do OpenRouter."""

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def call(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 1000,
        timeout: int = 30,
    ) -> str:
        """
        Faz chamada para a API do OpenRouter.

        Args:
            prompt: Prompt de texto
            model: Modelo a usar (default: configurado)
            max_tokens: Máximo de tokens na resposta
            timeout: Timeout em segundos

        Returns:
            Resposta do modelo
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model or self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()

        return response.json()["choices"][0]["message"]["content"]

    async def call_with_image(
        self,
        prompt: str,
        image_base64: str,
        mimetype: str = "image/jpeg",
        model: str | None = None,
        max_tokens: int = 1000,
        timeout: int = 60,
    ) -> str:
        """
        Faz chamada com imagem (vision).

        Args:
            prompt: Prompt de texto
            image_base64: Imagem em base64
            mimetype: Tipo MIME da imagem
            model: Modelo a usar
            max_tokens: Máximo de tokens
            timeout: Timeout em segundos

        Returns:
            Resposta do modelo
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mimetype};base64,{image_base64}"},
                        },
                    ],
                }
            ],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"[OpenRouter] Erro: {response.status_code} - {response.text[:200]}")
            raise Exception(f"OpenRouter error: {response.status_code}")

    async def call_with_audio(
        self,
        prompt: str,
        audio_base64: str,
        audio_format: str = "ogg",
        model: str | None = None,
        max_tokens: int = 500,
        timeout: int = 60,
    ) -> str:
        """
        Faz chamada com áudio.

        Args:
            prompt: Prompt de texto
            audio_base64: Áudio em base64
            audio_format: Formato do áudio (ogg, mp3, wav, etc)
            model: Modelo a usar
            max_tokens: Máximo de tokens
            timeout: Timeout em segundos

        Returns:
            Resposta do modelo
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": audio_base64,
                                "format": audio_format,
                            },
                        },
                    ],
                }
            ],
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=timeout,
            )

        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            logger.error(f"[OpenRouter] Erro: {response.status_code} - {response.text[:200]}")
            raise Exception(f"OpenRouter error: {response.status_code}")


def parse_llm_response(response: str) -> dict:
    """
    Parseia resposta do LLM removendo markdown se necessário.

    Args:
        response: Resposta bruta do LLM

    Returns:
        Dicionário parseado do JSON
    """
    response = re.sub(r"```json\s*", "", response)
    response = re.sub(r"```\s*", "", response)
    response = response.strip()

    json_match = re.search(r"\{.*\}", response, re.DOTALL)
    if json_match:
        response = json_match.group()

    return json.loads(response)


def convert_relative_date(data_relativa: str) -> datetime:
    """
    Converte data relativa em datetime.

    Args:
        data_relativa: "hoje", "ontem", "anteontem" ou "YYYY-MM-DD"

    Returns:
        Datetime correspondente
    """
    if not data_relativa or data_relativa == "hoje":
        return datetime.now(UTC)
    elif data_relativa == "ontem":
        return datetime.now(UTC) - timedelta(days=1)
    elif data_relativa == "anteontem":
        return datetime.now(UTC) - timedelta(days=2)
    else:
        try:
            return datetime.strptime(data_relativa, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError:
            return datetime.now(UTC)
