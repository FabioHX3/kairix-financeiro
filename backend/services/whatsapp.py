"""
Serviço de WhatsApp para envio de mensagens
Compatível com UAZAPI
"""

import httpx
from typing import Optional
from backend.config import settings


class WhatsAppService:
    """Serviço para enviar mensagens via UAZAPI"""

    def __init__(self):
        self.base_url = settings.WHATSAPP_API_URL.rstrip('/') if settings.WHATSAPP_API_URL else ""
        self.api_key = settings.WHATSAPP_API_KEY
        self.instance = settings.WHATSAPP_INSTANCE

    def _get_headers(self) -> dict:
        """Retorna headers para requisições UAZAPI"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _formatar_numero(self, numero: str) -> str:
        """Formata número para padrão internacional"""
        numero_limpo = "".join(filter(str.isdigit, numero))

        # Adiciona DDI do Brasil se não tiver
        if len(numero_limpo) <= 11:
            numero_limpo = f"55{numero_limpo}"

        return numero_limpo

    async def enviar_mensagem(
        self,
        numero: str,
        mensagem: str,
        reply_to: Optional[str] = None
    ) -> dict:
        """
        Envia mensagem de texto para um número

        Args:
            numero: Número do WhatsApp
            mensagem: Texto da mensagem
            reply_to: ID da mensagem para responder (opcional)

        Returns:
            dict com resultado da API
        """
        if not self.base_url or not self.api_key:
            print("[WhatsApp] API não configurada")
            return {"success": False, "error": "API não configurada"}

        numero_limpo = self._formatar_numero(numero)

        # UAZAPI: POST /send/text
        url = f"{self.base_url}/send/text"

        payload = {
            "number": numero_limpo,
            "text": mensagem,
            "delay": 1000,  # Mostra "digitando..." por 1 segundo
        }

        if reply_to:
            payload["replyid"] = reply_to

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code in [200, 201]:
                    print(f"[WhatsApp] Mensagem enviada para {numero_limpo}")
                    return {"success": True, "data": response.json()}
                else:
                    print(f"[WhatsApp] Erro: {response.status_code} - {response.text}")
                    return {"success": False, "error": response.text}

        except Exception as e:
            print(f"[WhatsApp] Erro ao enviar: {e}")
            return {"success": False, "error": str(e)}

    async def enviar_imagem(
        self,
        numero: str,
        image_url: str,
        caption: str = ""
    ) -> dict:
        """Envia imagem para um número via UAZAPI"""
        if not self.base_url or not self.api_key:
            return {"success": False, "error": "API não configurada"}

        numero_limpo = self._formatar_numero(numero)

        # UAZAPI: POST /send/image
        url = f"{self.base_url}/send/image"

        payload = {
            "number": numero_limpo,
            "image": image_url,
            "caption": caption
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code in [200, 201]:
                    return {"success": True, "data": response.json()}
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def enviar_audio(
        self,
        numero: str,
        audio_url: str
    ) -> dict:
        """Envia áudio para um número via UAZAPI"""
        if not self.base_url or not self.api_key:
            return {"success": False, "error": "API não configurada"}

        numero_limpo = self._formatar_numero(numero)

        # UAZAPI: POST /send/audio
        url = f"{self.base_url}/send/audio"

        payload = {
            "number": numero_limpo,
            "audio": audio_url
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers()
                )

                if response.status_code in [200, 201]:
                    return {"success": True, "data": response.json()}
                else:
                    return {"success": False, "error": response.text}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def verificar_conexao(self) -> dict:
        """Verifica se a instância está conectada"""
        if not self.base_url or not self.api_key:
            return {"connected": False, "error": "API não configurada"}

        # UAZAPI: GET /status
        url = f"{self.base_url}/status"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._get_headers())

                if response.status_code == 200:
                    data = response.json()
                    # UAZAPI retorna status da conexão
                    connected = data.get("connected", False) or data.get("status") == "open"
                    return {
                        "connected": connected,
                        "data": data
                    }
                else:
                    return {"connected": False, "error": response.text}

        except Exception as e:
            return {"connected": False, "error": str(e)}


# Instância global
whatsapp_service = WhatsAppService()
