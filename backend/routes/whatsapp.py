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

        # UAZAPI envia com EventType e message dentro do payload
        event_type = payload.get("EventType", "") or payload.get("event", "")

        if event_type and event_type not in ["messages", "message", "messages.upsert"]:
            return {"status": "ignored", "reason": f"event type: {event_type}"}

        # UAZAPI: dados da mensagem estão em payload.message
        message = payload.get("message", {})

        # Ignora mensagens enviadas por nós
        if message.get("fromMe", False):
            return {"status": "ignored", "reason": "own message"}

        # Extrai número do remetente - UAZAPI usa message.chatid ou message.sender
        chatid = message.get("chatid", "") or message.get("sender", "")

        # Fallback para outros formatos
        if not chatid:
            chatid = payload.get("chat", {}).get("wa_chatid", "")

        from_number = extrair_numero(chatid)

        if not from_number:
            print("[Webhook] Número não encontrado no payload")
            return {"status": "error", "reason": "number not found"}

        # Gera variações do número (com/sem 9, com/sem DDI)
        def gerar_variacoes_numero(numero: str) -> list:
            """Gera variações do número para busca flexível"""
            variacoes = [numero]

            # Remove DDI se tiver
            if numero.startswith("55") and len(numero) >= 12:
                sem_ddi = numero[2:]
                variacoes.append(sem_ddi)
                ddd = numero[2:4]
                resto = numero[4:]

                # Se tem 8 dígitos após DDD, adiciona o 9
                if len(resto) == 8:
                    com_nove = f"55{ddd}9{resto}"
                    variacoes.append(com_nove)
                    variacoes.append(f"{ddd}9{resto}")

                # Se tem 9 dígitos após DDD e começa com 9, remove o 9
                elif len(resto) == 9 and resto.startswith("9"):
                    sem_nove = f"55{ddd}{resto[1:]}"
                    variacoes.append(sem_nove)
                    variacoes.append(f"{ddd}{resto[1:]}")

            return list(set(variacoes))  # Remove duplicatas

        variacoes = gerar_variacoes_numero(from_number)

        # Procura usuário pelo WhatsApp (busca flexível)
        from sqlalchemy import or_
        filtros_usuario = []
        for var in variacoes:
            filtros_usuario.extend([
                Usuario.whatsapp == var,
                Usuario.telefone == var
            ])

        usuario = db.query(Usuario).filter(or_(*filtros_usuario)).first()

        membro_familia = None

        # Se não encontrou, procura nos membros da família
        if not usuario:
            filtros_membro = [MembroFamilia.telefone == var for var in variacoes]
            membro_familia = db.query(MembroFamilia).filter(
                or_(*filtros_membro),
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

        # Nome do usuário: prioriza sistema, fallback para WhatsApp
        nome_sistema = usuario.nome if usuario.nome else None
        nome_whatsapp = message.get("senderName", "") or chat.get("wa_name", "") or chat.get("name", "")
        sender_name = nome_sistema or nome_whatsapp
        contexto_extra = {"nome_usuario": sender_name} if sender_name else None

        # UAZAPI: tipo em message.messageType ou message.type
        message_type = message.get("messageType", "") or message.get("type", "text")
        message_type = message_type.lower()

        print(f"[Webhook] Tipo: {message_type}, Texto: {message.get('text', '')[:50]}")

        # TEXTO (Conversation, ExtendedTextMessage, text)
        if message_type in ["conversation", "extendedtextmessage", "text"]:
            mensagem_original = message.get("text", "")

            if mensagem_original:
                resultado = await agente.processar_mensagem(
                    user_id=user_id,
                    mensagem=mensagem_original,
                    categorias=categorias_lista,
                    contexto_extra=contexto_extra
                )

        # ÁUDIO
        elif message_type in ["audio", "audiomessage", "ptt"]:
            origem = OrigemRegistro.WHATSAPP_AUDIO
            arquivo_url = message.get("fileURL", "") or message.get("url", "")
            message_id = message.get("messageid", "")

            print(f"[Webhook] Áudio recebido - URL: {arquivo_url[:60] if arquivo_url else 'N/A'}...")

            texto = ""
            sucesso = False

            # Tenta baixar mídia descriptografada via UAZAPI
            if message_id:
                midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)

                if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
                    # Usa base64 da mídia descriptografada
                    base64_data = midia_result["data"]["base64Data"]
                    mimetype = midia_result["data"].get("mimetype", "audio/ogg")
                    print(f"[Webhook] Áudio descriptografado ({mimetype}, {len(base64_data)} chars)")
                    texto, sucesso = llm_service.transcrever_audio_base64(base64_data, mimetype)

            # Fallback: tenta URL direta (pode falhar se criptografado)
            if not sucesso and arquivo_url:
                print(f"[Webhook] Fallback para URL direta do áudio")
                texto, sucesso = llm_service.transcrever_audio(arquivo_url)

            if sucesso and texto:
                mensagem_original = texto
                resultado = await agente.processar_audio(
                    user_id=user_id,
                    transcricao=texto,
                    categorias=categorias_lista,
                    contexto_extra=contexto_extra
                )
            else:
                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    "🎤 Não consegui entender o áudio. Pode enviar por texto?"
                )
                return {"status": "audio_transcription_failed"}

        # IMAGEM
        elif message_type in ["image", "imagemessage"]:
            origem = OrigemRegistro.WHATSAPP_IMAGEM
            # UAZAPI: URL pode estar em content.URL, fileURL ou url
            content = message.get("content", {})
            if isinstance(content, dict):
                arquivo_url = content.get("URL", "") or content.get("url", "")
                caption = content.get("caption", "") or message.get("text", "")
            else:
                arquivo_url = message.get("fileURL", "") or message.get("url", "")
                caption = message.get("text", "") or message.get("caption", "")
            mensagem_original = caption
            print(f"[Webhook] Imagem URL: {arquivo_url[:80] if arquivo_url else 'VAZIA'}...")

            if arquivo_url:
                print(f"[Webhook] Processando imagem: {arquivo_url[:80]}...")

                # Tenta baixar mídia descriptografada via UAZAPI
                message_id = message.get("messageid", "")
                midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)

                if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
                    # Usa base64 da mídia descriptografada
                    base64_data = midia_result["data"]["base64Data"]
                    mimetype = midia_result["data"].get("mimetype", "image/jpeg")
                    print(f"[Webhook] Usando mídia descriptografada (base64, {len(base64_data)} chars)")
                    dados_imagem = llm_service.extrair_de_imagem_base64(base64_data, mimetype, caption)
                elif midia_result.get("success") and midia_result.get("data", {}).get("fileURL"):
                    # Usa URL pública retornada
                    url_publica = midia_result["data"]["fileURL"]
                    print(f"[Webhook] Usando URL pública: {url_publica[:60]}...")
                    dados_imagem = llm_service.extrair_de_imagem(url_publica, caption)
                else:
                    # Fallback: tenta URL original (pode falhar se criptografada)
                    print(f"[Webhook] Fallback para URL original")
                    dados_imagem = llm_service.extrair_de_imagem(arquivo_url, caption)

                print(f"[Webhook] Dados extraídos da imagem: {dados_imagem}")

                resultado = await agente.processar_imagem(
                    user_id=user_id,
                    dados_imagem=dados_imagem,
                    caption=caption,
                    categorias=categorias_lista,
                    contexto_extra=contexto_extra
                )

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
