"""
Funções utilitárias para processamento de mensagens WhatsApp.
"""

import hashlib
import hmac
import re

from backend.config import settings


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """
    Verifica a assinatura HMAC-SHA256 do webhook.

    Args:
        payload: Corpo da requisição em bytes
        signature: Assinatura enviada no header X-Webhook-Signature

    Returns:
        True se a assinatura for válida ou se WEBHOOK_SECRET não estiver configurado
    """
    # Se não há secret configurado, pula validação (desenvolvimento)
    if not settings.WEBHOOK_SECRET:
        return True

    if not signature:
        return False

    # Calcula HMAC-SHA256
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Compara de forma segura (timing-safe)
    return hmac.compare_digest(expected_signature, signature)


def detectar_comando_exclusao(texto: str) -> str | None:
    """
    Detecta comando de exclusão e retorna o código da transação.

    Args:
        texto: Mensagem do usuário

    Returns:
        Código da transação (5 caracteres) ou None
    """
    padroes = [
        r"excluir\s+(?:transacao|transação|registro)?\s*([A-Z0-9]{5})",
        r"cancelar\s+(?:transacao|transação|registro)?\s*([A-Z0-9]{5})",
        r"apagar\s+(?:transacao|transação|registro)?\s*([A-Z0-9]{5})",
        r"deletar\s+(?:transacao|transação|registro)?\s*([A-Z0-9]{5})",
        r"remover\s+(?:transacao|transação|registro)?\s*([A-Z0-9]{5})",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            return match.group(1).upper()
    return None


def extrair_numero(chatid: str) -> str:
    """
    Extrai número limpo do chatid.

    Args:
        chatid: ID do chat do WhatsApp (ex: "5511999999999@s.whatsapp.net")

    Returns:
        Número limpo (apenas dígitos)
    """
    numero = chatid.replace("@s.whatsapp.net", "").replace("@c.us", "")
    return "".join(filter(str.isdigit, numero))


def gerar_variacoes_numero(numero: str) -> list[str]:
    """
    Gera variações do número para busca flexível.

    Lida com diferentes formatos de números brasileiros:
    - Com/sem DDI 55
    - Com/sem nono dígito

    Args:
        numero: Número original

    Returns:
        Lista de variações possíveis
    """
    variacoes = [numero]

    if numero.startswith("55") and len(numero) >= 12:
        sem_ddi = numero[2:]
        variacoes.append(sem_ddi)
        ddd = numero[2:4]
        resto = numero[4:]

        if len(resto) == 8:
            # Adiciona nono dígito
            com_nove = f"55{ddd}9{resto}"
            variacoes.append(com_nove)
            variacoes.append(f"{ddd}9{resto}")
        elif len(resto) == 9 and resto.startswith("9"):
            # Remove nono dígito
            sem_nove = f"55{ddd}{resto[1:]}"
            variacoes.append(sem_nove)
            variacoes.append(f"{ddd}{resto[1:]}")

    return list(set(variacoes))
