"""
Webhook do WhatsApp - Processa mensagens com o Agente Financeiro
Compatível com UAZAPI
"""

from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from backend.core.database import get_db
from backend.models import Usuario, Transacao, Categoria, MembroFamilia, OrigemRegistro, TipoTransacao, StatusTransacao
from backend.services import agente, whatsapp_service, llm_service

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


def extrair_numero(chatid: str) -> str:
    """Extrai número limpo do chatid"""
    # Remove sufixos do WhatsApp
    numero = chatid.replace("@s.whatsapp.net", "").replace("@c.us", "")
    # Remove caracteres não numéricos
    return "".join(filter(str.isdigit, numero))


@router.post("/webhook")
async def webhook_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook para receber mensagens do UAZAPI

    Formato UAZAPI:
    {
        "chatid": "5511999999999@s.whatsapp.net",
        "sender": "5511999999999",
        "fromMe": false,
        "messageType": "text",
        "text": "mensagem",
        "fileURL": "url do arquivo",
        ...
    }
    """

    try:
        payload = await request.json()

        # Log para debug
        print(f"[Webhook] Payload recebido: {payload}")

        # UAZAPI pode enviar evento ou mensagem direta
        # Se tiver "event", é um wrapper
        if "event" in payload:
            event = payload.get("event", "")
            if event not in ["messages", "message", "messages.upsert"]:
                return {"status": "ignored", "reason": f"event type: {event}"}
            # Extrai dados do wrapper
            data = payload.get("data", payload)
        else:
            # Mensagem direta
            data = payload

        # Ignora mensagens enviadas por nós
        if data.get("fromMe", False):
            return {"status": "ignored", "reason": "own message"}

        # Extrai número do remetente
        chatid = data.get("chatid", "") or data.get("key", {}).get("remoteJid", "")
        sender = data.get("sender", "")

        from_number = extrair_numero(chatid or sender)

        if not from_number:
            print("[Webhook] Número não encontrado no payload")
            return {"status": "error", "reason": "number not found"}

        # Busca com e sem DDI
        numero_sem_ddi = from_number[2:] if from_number.startswith("55") else from_number

        # Procura usuário pelo WhatsApp
        usuario = db.query(Usuario).filter(
            (Usuario.whatsapp == from_number) |
            (Usuario.whatsapp == numero_sem_ddi) |
            (Usuario.telefone == from_number) |
            (Usuario.telefone == numero_sem_ddi)
        ).first()

        membro_familia = None

        # Se não encontrou, procura nos membros da família
        if not usuario:
            membro_familia = db.query(MembroFamilia).filter(
                (MembroFamilia.telefone == from_number) |
                (MembroFamilia.telefone == numero_sem_ddi),
                MembroFamilia.ativo == True
            ).first()

            if membro_familia:
                usuario = db.query(Usuario).filter(Usuario.id == membro_familia.usuario_id).first()

        if not usuario:
            print(f"[Webhook] Usuário não encontrado: {from_number}")
            background_tasks.add_task(
                _enviar_mensagem_nao_cadastrado,
                from_number
            )
            return {"status": "user_not_found", "from": from_number}

        if not usuario.ativo:
            return {"status": "user_inactive"}

        # Busca categorias do usuário
        categorias = db.query(Categoria).filter(
            (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
        ).all()

        categorias_lista = [
            {"id": c.id, "nome": c.nome, "tipo": c.tipo.value}
            for c in categorias
        ]

        # Processa mensagem baseado no tipo
        user_id = f"user_{usuario.id}"
        resultado = None
        origem = OrigemRegistro.WHATSAPP_TEXTO
        mensagem_original = ""
        arquivo_url = None

        # Tipo de mensagem UAZAPI
        message_type = data.get("messageType", "text")

        # Também suporta formato Evolution (message.conversation, etc)
        message = data.get("message", {})

        # TEXTO
        if message_type == "text" or "conversation" in message or "extendedTextMessage" in message:
            # UAZAPI: texto direto em "text"
            # Evolution: texto em message.conversation
            mensagem_original = (
                data.get("text", "") or
                message.get("conversation", "") or
                message.get("extendedTextMessage", {}).get("text", "")
            )

            if mensagem_original:
                resultado = await agente.processar_mensagem(
                    user_id=user_id,
                    mensagem=mensagem_original,
                    categorias=categorias_lista
                )

        # ÁUDIO
        elif message_type == "audio" or "audioMessage" in message:
            origem = OrigemRegistro.WHATSAPP_AUDIO
            # UAZAPI: URL em fileURL
            # Evolution: URL em message.audioMessage.url
            arquivo_url = (
                data.get("fileURL", "") or
                message.get("audioMessage", {}).get("url", "")
            )

            if arquivo_url:
                texto, sucesso = llm_service.transcrever_audio(arquivo_url)

                if sucesso and texto:
                    mensagem_original = texto
                    resultado = await agente.processar_audio(
                        user_id=user_id,
                        transcricao=texto,
                        categorias=categorias_lista
                    )
                else:
                    background_tasks.add_task(
                        whatsapp_service.enviar_mensagem,
                        from_number,
                        "🎤 Não consegui entender o áudio. Pode enviar por texto?"
                    )
                    return {"status": "audio_transcription_failed"}

        # IMAGEM
        elif message_type == "image" or "imageMessage" in message:
            origem = OrigemRegistro.WHATSAPP_IMAGEM
            # UAZAPI: URL em fileURL, caption em text
            # Evolution: URL em message.imageMessage.url
            arquivo_url = (
                data.get("fileURL", "") or
                message.get("imageMessage", {}).get("url", "")
            )
            caption = (
                data.get("text", "") or
                message.get("imageMessage", {}).get("caption", "")
            )
            mensagem_original = caption

            if arquivo_url:
                dados_imagem = llm_service.extrair_de_imagem(arquivo_url, caption)

                resultado = await agente.processar_imagem(
                    user_id=user_id,
                    dados_imagem=dados_imagem,
                    caption=caption,
                    categorias=categorias_lista
                )

                # Se extraiu dados da imagem, usa eles
                if dados_imagem.get("valor", 0) > 0 and resultado and resultado.transacao:
                    resultado.transacao.valor = dados_imagem["valor"]
                    if dados_imagem.get("descricao"):
                        resultado.transacao.descricao = dados_imagem["descricao"]

        else:
            print(f"[Webhook] Tipo não suportado: {message_type}")
            return {"status": "unsupported_message_type", "type": message_type}

        if not resultado:
            return {"status": "no_result"}

        # Processa a ação do agente
        transacao_id = None

        if resultado.acao == "registrar" and resultado.transacao:
            transacao_id = await _salvar_transacao(
                db=db,
                usuario=usuario,
                membro_familia=membro_familia,
                dados=resultado.transacao,
                origem=origem,
                mensagem_original=mensagem_original,
                arquivo_url=arquivo_url,
                categorias=categorias
            )

        # Envia resposta ao usuário
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            resultado.mensagem
        )

        return {
            "status": "success",
            "acao": resultado.acao,
            "transacao_id": transacao_id
        }

    except Exception as e:
        print(f"[Webhook] Erro: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e)}


async def _salvar_transacao(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia,
    dados,
    origem: OrigemRegistro,
    mensagem_original: str,
    arquivo_url: str,
    categorias: list
) -> int:
    """Salva transação no banco de dados"""

    try:
        # Busca categoria pelo nome
        categoria = None
        for cat in categorias:
            if cat.nome.lower() == dados.categoria.lower():
                categoria = cat
                break

        # Se não encontrou, usa "Outros"
        if not categoria:
            categoria = next(
                (c for c in categorias if c.nome == "Outros" and c.tipo.value == dados.tipo),
                None
            )

        # Converte data
        try:
            data_transacao = datetime.strptime(dados.data, "%Y-%m-%d")
        except:
            data_transacao = datetime.now()

        # Cria transação
        transacao = Transacao(
            usuario_id=usuario.id,
            tipo=TipoTransacao(dados.tipo),
            valor=dados.valor,
            descricao=dados.descricao,
            data_transacao=data_transacao,
            categoria_id=categoria.id if categoria else None,
            membro_familia_id=membro_familia.id if membro_familia else None,
            status=StatusTransacao.CONFIRMADA,
            origem=origem,
            mensagem_original=mensagem_original,
            arquivo_url=arquivo_url,
            confianca_ia=dados.confianca
        )

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        print(f"[Webhook] Transação salva: ID={transacao.id}, R${dados.valor:.2f} ({dados.tipo})")
        return transacao.id

    except Exception as e:
        print(f"[Webhook] Erro ao salvar: {e}")
        db.rollback()
        raise


async def _enviar_mensagem_nao_cadastrado(numero: str):
    """Envia mensagem para usuário não cadastrado"""
    mensagem = """👋 Olá! Sou o *Kairix*, seu assistente financeiro!

Parece que você ainda não tem uma conta.

📱 Acesse nosso site para criar sua conta:
🔗 https://kairix.com.br

Depois volte aqui e me conte seus gastos! 💰"""

    await whatsapp_service.enviar_mensagem(numero, mensagem)


@router.get("/status")
async def verificar_status():
    """Verifica status da conexão com WhatsApp"""
    resultado = await whatsapp_service.verificar_conexao()
    return resultado


@router.post("/enviar")
async def enviar_mensagem_manual(numero: str, mensagem: str):
    """Endpoint para enviar mensagem (para testes)"""
    resultado = await whatsapp_service.enviar_mensagem(numero, mensagem)
    return resultado


@router.post("/teste")
async def teste_webhook():
    """Endpoint para testar se webhook está funcionando"""
    return {
        "status": "ok",
        "message": "Webhook funcionando!",
        "timestamp": datetime.now().isoformat()
    }
