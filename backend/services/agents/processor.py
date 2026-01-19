"""
Processor - Ponto de entrada para processar mensagens com o novo sistema de agentes.

Esta função pode ser usada no lugar do agente antigo gradualmente.
"""

import logging

from sqlalchemy.orm import Session

from backend.services.agents.base_agent import AgentContext, AgentResponse, OrigemMensagem
from backend.services.agents.gateway_agent import GatewayAgent

logger = logging.getLogger(__name__)


async def processar_mensagem_v2(
    usuario_id: int,
    whatsapp: str,
    mensagem: str,
    origem: str = "whatsapp_texto",
    db: Session | None = None,
    media_url: str | None = None,
    media_type: str | None = None,
    contexto_extra: dict | None = None
) -> AgentResponse:
    """
    Processa mensagem usando o novo sistema multi-agente.

    Args:
        usuario_id: ID do usuário no banco
        whatsapp: Número do WhatsApp do usuário
        mensagem: Texto da mensagem
        origem: Tipo de origem (whatsapp_texto, whatsapp_audio, etc)
        db: Sessão do banco de dados
        media_url: URL da mídia (se houver)
        media_type: Tipo da mídia (audio, image, etc)
        contexto_extra: Dados adicionais

    Returns:
        AgentResponse com resultado do processamento
    """

    # Mapeia origem
    origem_map = {
        "whatsapp_texto": OrigemMensagem.WHATSAPP_TEXTO,
        "whatsapp_audio": OrigemMensagem.WHATSAPP_AUDIO,
        "whatsapp_imagem": OrigemMensagem.WHATSAPP_IMAGEM,
        "web": OrigemMensagem.WEB,
        "api": OrigemMensagem.API,
    }

    origem_enum = origem_map.get(origem, OrigemMensagem.WHATSAPP_TEXTO)

    # Busca timezone do usuário (default: Brasília)
    user_timezone = "America/Sao_Paulo"
    if db:
        from backend.models.models import UserPreferences
        prefs = db.query(UserPreferences).filter(
            UserPreferences.usuario_id == usuario_id
        ).first()
        if prefs and prefs.timezone:
            user_timezone = prefs.timezone

    # Cria contexto
    context = AgentContext(
        usuario_id=usuario_id,
        whatsapp=whatsapp,
        mensagem_original=mensagem,
        origem=origem_enum,
        timezone=user_timezone,
        media_url=media_url,
        media_type=media_type,
        historico_conversa=contexto_extra.get("historico", []) if contexto_extra else []
    )

    # Processa com Gateway Agent
    gateway = GatewayAgent(db_session=db)

    try:
        response = await gateway.process(context)
        return response

    except Exception as e:
        logger.error(f"[Processor] Erro: {e}")
        return AgentResponse(
            sucesso=False,
            mensagem="Desculpe, tive um problema. Pode repetir?"
        )


def converter_resposta_para_legado(response: AgentResponse) -> dict:
    """
    Converte AgentResponse para o formato esperado pelo código legado.

    Isso permite migração gradual sem quebrar o sistema existente.
    """
    return {
        "acao": "registrar" if response.codigo_transacao else "conversar",
        "mensagem": response.mensagem,
        "transacao": {
            "codigo": response.codigo_transacao,
            **response.dados
        } if response.codigo_transacao else None,
        "aguardando": "confirmacao" if response.requer_confirmacao else None
    }
