"""
Webhook principal do WhatsApp - Processa mensagens com Sistema Multi-Agente.
Compatível com UAZAPI.
"""

import base64 as b64
import json
import logging
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import Categoria, MembroFamilia, OrigemRegistro, Usuario
from backend.routes.whatsapp.formatters import (
    formatar_resposta_multiplas,
    formatar_resposta_transacao,
)
from backend.routes.whatsapp.handlers import (
    enviar_mensagem_nao_cadastrado,
    excluir_transacao_por_codigo,
    processar_confirmacao_documento_fiscal,
    processar_documento_fiscal,
    salvar_multiplas_transacoes,
    salvar_transacao_de_imagem,
)
from backend.routes.whatsapp.utils import (
    detectar_comando_exclusao,
    extrair_numero,
    gerar_variacoes_numero,
    verify_webhook_signature,
)
from backend.services import llm_service, whatsapp_service
from backend.services.agents.base_agent import OrigemMensagem
from backend.services.agents.processor import processar_mensagem_v2
from backend.services.memory_service import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


@router.post("/webhook")
async def webhook_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
):
    """
    Webhook para receber mensagens do UAZAPI.

    Usa sistema multi-agente para processamento.
    Valida assinatura HMAC-SHA256 se WEBHOOK_SECRET estiver configurado.
    """
    # Valida assinatura HMAC
    body = await request.body()
    if not verify_webhook_signature(body, x_webhook_signature):
        logger.warning("[Webhook] Assinatura inválida - rejeitando requisição")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
        logger.debug(f"[Webhook] Payload recebido: {payload}")

        # UAZAPI envia com EventType
        event_type = payload.get("EventType", "") or payload.get("event", "")

        if event_type and event_type not in ["messages", "message", "messages.upsert"]:
            return {"status": "ignored", "reason": f"event type: {event_type}"}

        message = payload.get("message", {})

        # Ignora mensagens enviadas por nós
        if message.get("fromMe", False):
            return {"status": "ignored", "reason": "own message"}

        # Extrai número do remetente
        chatid = message.get("chatid", "") or message.get("sender", "")
        if not chatid:
            chatid = payload.get("chat", {}).get("wa_chatid", "")

        from_number = extrair_numero(chatid)

        if not from_number:
            logger.warning("[Webhook] Número não encontrado no payload")
            return {"status": "error", "reason": "number not found"}

        # Busca usuário
        variacoes = gerar_variacoes_numero(from_number)
        filtros_usuario = [Usuario.whatsapp == var for var in variacoes]

        usuario = db.query(Usuario).filter(or_(*filtros_usuario)).first()

        membro_familia = None

        if not usuario:
            filtros_membro = [MembroFamilia.whatsapp == var for var in variacoes]
            membro_familia = (
                db.query(MembroFamilia)
                .filter(or_(*filtros_membro), MembroFamilia.ativo.is_(True))
                .first()
            )

            if membro_familia:
                usuario = db.query(Usuario).filter(Usuario.id == membro_familia.usuario_id).first()

        if not usuario:
            logger.warning(f"[Webhook] Usuário não encontrado: {from_number}")
            background_tasks.add_task(enviar_mensagem_nao_cadastrado, from_number)
            return {"status": "user_not_found", "from": from_number}

        if not usuario.ativo:
            return {"status": "user_inactive"}

        # Busca categorias do usuário
        categorias = (
            db.query(Categoria)
            .filter((Categoria.padrao.is_(True)) | (Categoria.usuario_id == usuario.id))
            .all()
        )

        # Prepara processamento
        user_id = f"user_{usuario.id}"

        # Nome do usuário
        nome_whatsapp = message.get("senderName", "")
        sender_name = usuario.nome or nome_whatsapp

        # Tipo de mensagem
        message_type = message.get("messageType", "") or message.get("type", "text")
        message_type = message_type.lower()

        logger.debug(f"[Webhook] Tipo: {message_type}, Texto: {message.get('text', '')[:50]}")

        # ============================================================
        # PROCESSAMENTO POR TIPO DE MENSAGEM
        # ============================================================

        # TEXTO
        if message_type in ["conversation", "extendedtextmessage", "text"]:
            return await _processar_texto(
                message,
                db,
                usuario,
                membro_familia,
                user_id,
                from_number,
                sender_name,
                categorias,
                background_tasks,
            )

        # ÁUDIO
        elif message_type in ["audio", "audiomessage", "ptt"]:
            return await _processar_audio(
                message,
                db,
                usuario,
                from_number,
                sender_name,
                background_tasks,
            )

        # IMAGEM
        elif message_type in ["image", "imagemessage"]:
            return await _processar_imagem(
                message,
                db,
                usuario,
                membro_familia,
                user_id,
                from_number,
                categorias,
                background_tasks,
            )

        # DOCUMENTO (PDF)
        elif message_type in ["document", "documentmessage"]:
            return await _processar_documento(
                message,
                db,
                usuario,
                membro_familia,
                from_number,
                categorias,
                background_tasks,
            )

        else:
            logger.warning(f"[Webhook] Tipo não suportado: {message_type}")
            return {"status": "unsupported_message_type", "type": message_type}

    except Exception as e:
        logger.error(f"[Webhook] Erro: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


async def _processar_texto(
    message: dict,
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia | None,
    user_id: str,
    from_number: str,
    sender_name: str,
    categorias: list,
    background_tasks: BackgroundTasks,
) -> dict:
    """Processa mensagem de texto."""
    mensagem_original = message.get("text", "")

    if not mensagem_original:
        return {"status": "empty_message"}

    # Verifica comando de exclusão
    codigo_exclusao = detectar_comando_exclusao(mensagem_original)
    if codigo_exclusao:
        return await excluir_transacao_por_codigo(
            db, usuario, codigo_exclusao, from_number, background_tasks
        )

    # Verifica contexto pendente (documento fiscal)
    contexto_pendente = await memory_service.obter_acao_pendente(from_number) or {}

    if contexto_pendente.get("tipo") == "confirmacao_documento_fiscal" and mensagem_original.strip().lower() in [
        "sim",
        "s",
        "ok",
        "confirma",
        "confirmar",
        "yes",
    ]:
        return await processar_confirmacao_documento_fiscal(
            db,
            usuario,
            membro_familia,
            user_id,
            from_number,
            contexto_pendente,
            categorias,
            background_tasks,
        )

    # Processa com sistema multi-agente
    resultado = await processar_mensagem_v2(
        usuario_id=usuario.id,
        whatsapp=from_number,
        mensagem=mensagem_original,
        origem=OrigemMensagem.WHATSAPP_TEXTO.value,
        db=db,
        contexto_extra={"nome_usuario": sender_name},
    )

    # Envia resposta
    if resultado.mensagem:
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem, from_number, resultado.mensagem
        )

    return {
        "status": "success" if resultado.sucesso else "processed",
        "intent": resultado.dados.get("intent"),
        "transacao_id": resultado.dados.get("transacao_id"),
    }


async def _processar_audio(
    message: dict,
    db: Session,
    usuario: Usuario,
    from_number: str,
    sender_name: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """Processa mensagem de áudio."""
    arquivo_url = message.get("fileURL", "") or message.get("url", "")
    message_id = message.get("messageid", "")

    logger.debug(f"[Webhook] Áudio recebido - URL: {arquivo_url[:60] if arquivo_url else 'N/A'}...")

    texto = ""
    sucesso = False

    # Tenta baixar mídia descriptografada via UAZAPI
    if message_id:
        midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)

        if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
            base64_data = midia_result["data"]["base64Data"]
            mimetype = midia_result["data"].get("mimetype", "audio/ogg")
            logger.debug(f"[Webhook] Áudio descriptografado ({mimetype}, {len(base64_data)} chars)")
            texto, sucesso = await llm_service.transcrever_audio_base64(base64_data, mimetype)

    # Fallback: URL direta
    if not sucesso and arquivo_url:
        logger.debug("[Webhook] Fallback para URL direta do áudio")
        texto, sucesso = await llm_service.transcrever_audio(arquivo_url)

    if sucesso and texto:
        # Processa transcrição com multi-agente
        resultado = await processar_mensagem_v2(
            usuario_id=usuario.id,
            whatsapp=from_number,
            mensagem=f"[Áudio transcrito] {texto}",
            origem=OrigemMensagem.WHATSAPP_AUDIO.value,
            db=db,
            contexto_extra={"nome_usuario": sender_name},
        )

        if resultado.mensagem:
            background_tasks.add_task(
                whatsapp_service.enviar_mensagem, from_number, resultado.mensagem
            )

        return {"status": "success", "transcricao": texto[:100]}
    else:
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            "Não consegui entender o áudio. Pode enviar por texto?",
        )
        return {"status": "audio_transcription_failed"}


async def _processar_imagem(
    message: dict,
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia | None,
    user_id: str,
    from_number: str,
    categorias: list,
    background_tasks: BackgroundTasks,
) -> dict:
    """Processa mensagem de imagem."""
    origem = OrigemRegistro.WHATSAPP_IMAGEM
    content = message.get("content", {})
    if isinstance(content, dict):
        arquivo_url = content.get("URL", "") or content.get("url", "")
        caption = content.get("caption", "") or message.get("text", "")
    else:
        arquivo_url = message.get("fileURL", "") or message.get("url", "")
        caption = message.get("text", "") or message.get("caption", "")

    logger.debug(f"[Webhook] Imagem URL: {arquivo_url[:80] if arquivo_url else 'VAZIA'}...")

    # Tenta baixar mídia descriptografada
    message_id = message.get("messageid", "")
    base64_data = None
    mimetype = "image/jpeg"

    if message_id:
        midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)
        if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
            base64_data = midia_result["data"]["base64Data"]
            mimetype = midia_result["data"].get("mimetype", "image/jpeg")
            logger.debug(f"[Webhook] Mídia descriptografada ({len(base64_data)} chars)")

    # Fallback: URL direta
    if not base64_data and arquivo_url:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(arquivo_url, timeout=30)
            if resp.status_code == 200:
                base64_data = b64.b64encode(resp.content).decode("utf-8")
                mimetype = resp.headers.get("content-type", "image/jpeg")
                logger.debug(f"[Webhook] Imagem baixada via URL ({len(base64_data)} chars)")
        except Exception as e:
            logger.error(f"[Webhook] Erro ao baixar imagem: {e}")

    if not base64_data:
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            "Não consegui acessar a imagem. Pode enviar novamente?",
        )
        return {"status": "image_download_failed"}

    # Analisa o documento
    dados_doc = await llm_service.extrair_extrato_multiplo(base64_data, mimetype, caption)
    tipo_doc = dados_doc.get("tipo_documento", "outro")
    logger.debug(f"[Webhook] Tipo documento: {tipo_doc}")

    # DOCUMENTO FISCAL
    if tipo_doc == "documento_fiscal":
        return await processar_documento_fiscal(user_id, from_number, dados_doc, background_tasks)

    # EXTRATO/FATURA
    elif tipo_doc in ["extrato_bancario", "fatura_cartao"] and dados_doc.get("transacoes") and len(
        dados_doc["transacoes"]
    ) > 1:
        logger.info(f"[Webhook] Extrato: {len(dados_doc['transacoes'])} transações")

        transacoes_salvas = await salvar_multiplas_transacoes(
            db=db,
            usuario=usuario,
            membro_familia=membro_familia,
            transacoes=dados_doc["transacoes"],
            origem=origem,
            categorias=categorias,
        )

        mensagem_resposta = formatar_resposta_multiplas(transacoes_salvas, dados_doc)

        background_tasks.add_task(whatsapp_service.enviar_mensagem, from_number, mensagem_resposta)

        return {
            "status": "success",
            "acao": "registrar_multiplas",
            "total": len(transacoes_salvas),
        }

    # COMPROVANTE ou transação única
    else:
        dados_imagem = await llm_service.extrair_de_imagem_base64(base64_data, mimetype, caption)
        logger.debug(f"[Webhook] Dados extraídos: {dados_imagem}")

        if dados_imagem.get("entendeu") and dados_imagem.get("valor", 0) > 0:
            # Salva transação
            transacao_info = await salvar_transacao_de_imagem(
                db, usuario, membro_familia, dados_imagem, origem, categorias
            )

            if transacao_info and transacao_info.get("transacao"):
                t = transacao_info["transacao"]
                mensagem_formatada = formatar_resposta_transacao(
                    t,
                    transacao_info.get("categoria_nome"),
                    transacao_info.get("categoria_icone"),
                )

                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem, from_number, mensagem_formatada
                )

                return {
                    "status": "success",
                    "transacao_id": transacao_info["id"],
                    "codigo": transacao_info["codigo"],
                }
        else:
            # Não entendeu - pede esclarecimento
            pergunta = dados_imagem.get("pergunta", "O que você gostaria de registrar desta imagem?")
            background_tasks.add_task(
                whatsapp_service.enviar_mensagem, from_number, f"📷 {pergunta}"
            )
            return {"status": "awaiting_clarification"}


async def _processar_documento(
    message: dict,
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia | None,
    from_number: str,
    categorias: list,
    background_tasks: BackgroundTasks,
) -> dict:
    """Processa documento (PDF)."""
    origem = OrigemRegistro.WHATSAPP_IMAGEM
    message_id = message.get("messageid", "")
    filename = message.get("filename", "") or message.get("content", {}).get("filename", "")

    if not filename.lower().endswith(".pdf"):
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            "Por enquanto só aceito PDFs de extratos. Pode enviar como imagem?",
        )
        return {"status": "unsupported_document"}

    logger.info(f"[Webhook] PDF recebido: {filename}")

    midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)

    if not midia_result.get("success") or not midia_result.get("data", {}).get("base64Data"):
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            "Não consegui ler o PDF. Pode tentar enviar como imagem?",
        )
        return {"status": "pdf_download_failed"}

    base64_data = midia_result["data"]["base64Data"]
    logger.debug(f"[Webhook] PDF descriptografado ({len(base64_data)} chars)")

    dados_pdf = await llm_service.extrair_de_pdf_base64(base64_data)

    if not dados_pdf.get("transacoes"):
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            "Não encontrei transações neste PDF. É um extrato bancário?",
        )
        return {"status": "pdf_no_transactions"}

    transacoes_salvas = await salvar_multiplas_transacoes(
        db=db,
        usuario=usuario,
        membro_familia=membro_familia,
        transacoes=dados_pdf["transacoes"],
        origem=origem,
        categorias=categorias,
    )

    mensagem_resposta = formatar_resposta_multiplas(transacoes_salvas, dados_pdf)

    background_tasks.add_task(whatsapp_service.enviar_mensagem, from_number, mensagem_resposta)

    return {
        "status": "success",
        "acao": "registrar_pdf",
        "total": len(transacoes_salvas),
    }


# ============================================================================
# ENDPOINTS AUXILIARES
# ============================================================================


@router.get("/status")
async def verificar_status(usuario: Usuario = Depends(obter_usuario_atual)):
    """Verifica status da conexão com WhatsApp."""
    resultado = await whatsapp_service.verificar_conexao()
    return resultado


@router.post("/enviar")
async def enviar_mensagem_manual(
    numero: str,
    mensagem: str,
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Endpoint para enviar mensagem (requer autenticação)."""
    resultado = await whatsapp_service.enviar_mensagem(numero, mensagem)
    return resultado


@router.post("/teste")
async def teste_webhook(usuario: Usuario = Depends(obter_usuario_atual)):
    """Endpoint para testar se webhook está funcionando."""
    return {
        "status": "ok",
        "message": "Webhook funcionando!",
        "timestamp": datetime.now(UTC).isoformat(),
    }
