from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models import Usuario, Transacao, Categoria, MembroFamilia, OrigemRegistro, TipoTransacao
from backend.services import llm_service

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


@router.post("/webhook")
async def webhook_whatsapp(request: Request, db: Session = Depends(get_db)):
    """
    Webhook para receber mensagens do Evolution API
    """

    try:
        payload = await request.json()

        if payload.get("event") != "messages.upsert":
            return {"status": "ignored", "reason": "not a message event"}

        data = payload.get("data", {})
        message = data.get("message", {})
        key = data.get("key", {})

        remote_jid = key.get("remoteJid", "")
        from_number = remote_jid.replace("@s.whatsapp.net", "")

        # Procura usuário
        usuario = db.query(Usuario).filter(Usuario.whatsapp == from_number).first()
        membro_familia_id = None

        if not usuario:
            membro = db.query(MembroFamilia).filter(
                MembroFamilia.telefone == from_number,
                MembroFamilia.ativo == True
            ).first()

            if membro:
                usuario = db.query(Usuario).filter(Usuario.id == membro.usuario_id).first()
                membro_familia_id = membro.id

        if not usuario:
            return {
                "status": "user_not_found",
                "message": "Telefone não cadastrado no sistema",
                "from": from_number
            }

        if not usuario.ativo:
            return {"status": "user_inactive"}

        # Processa mensagem
        resultado = None

        if "conversation" in message:
            texto = message["conversation"]
            resultado = await _processar_mensagem_texto(db, usuario, texto, membro_familia_id)

        elif "extendedTextMessage" in message:
            texto = message["extendedTextMessage"].get("text", "")
            resultado = await _processar_mensagem_texto(db, usuario, texto, membro_familia_id)

        elif "audioMessage" in message:
            audio_url = message["audioMessage"].get("url", "")
            resultado = await _processar_mensagem_audio(db, usuario, audio_url, membro_familia_id)

        elif "imageMessage" in message:
            image_url = message["imageMessage"].get("url", "")
            caption = message["imageMessage"].get("caption", "")
            resultado = await _processar_mensagem_imagem(db, usuario, image_url, caption, membro_familia_id)

        else:
            return {"status": "unsupported_message_type"}

        return {
            "status": "success",
            "transacao_id": resultado.get("transacao_id") if resultado else None,
            "message": resultado.get("message") if resultado else "Processado"
        }

    except Exception as e:
        print(f"Erro no webhook: {e}")
        return {"status": "error", "error": str(e)}


async def _processar_mensagem_texto(db: Session, usuario: Usuario, texto: str, membro_familia_id: int = None) -> dict:
    """Processa mensagem de texto e cria transação"""

    try:
        categorias = db.query(Categoria).filter(
            (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
        ).all()

        categorias_lista = [
            {"id": c.id, "nome": c.nome, "tipo": c.tipo.value}
            for c in categorias
        ]

        info = llm_service.extrair_transacao_de_texto(texto, categorias_lista)

        categoria = db.query(Categoria).filter(
            Categoria.nome == info['categoria_sugerida'],
            (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
        ).first()

        categoria_id = categoria.id if categoria else None

        transacao = Transacao(
            usuario_id=usuario.id,
            tipo=TipoTransacao(info['tipo']),
            valor=info['valor'],
            descricao=info['descricao'],
            data_transacao=info['data_transacao'],
            categoria_id=categoria_id,
            membro_familia_id=membro_familia_id,
            origem=OrigemRegistro.WHATSAPP_TEXTO,
            mensagem_original=texto,
            confianca_ia=info.get('confianca', 0.5)
        )

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        return {
            "transacao_id": transacao.id,
            "message": "Transação registrada com sucesso"
        }

    except Exception as e:
        print(f"Erro ao processar texto: {e}")
        db.rollback()
        raise


async def _processar_mensagem_audio(db: Session, usuario: Usuario, audio_url: str, membro_familia_id: int = None) -> dict:
    """Processa mensagem de áudio"""

    try:
        texto, sucesso = llm_service.transcrever_audio(audio_url)

        if not sucesso or not texto:
            return {
                "transacao_id": None,
                "message": "Não foi possível transcrever o áudio"
            }

        categorias = db.query(Categoria).filter(
            (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
        ).all()

        categorias_lista = [
            {"id": c.id, "nome": c.nome, "tipo": c.tipo.value}
            for c in categorias
        ]

        info = llm_service.extrair_transacao_de_texto(texto, categorias_lista)

        categoria = db.query(Categoria).filter(
            Categoria.nome == info['categoria_sugerida'],
            (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
        ).first()

        transacao = Transacao(
            usuario_id=usuario.id,
            tipo=TipoTransacao(info['tipo']),
            valor=info['valor'],
            descricao=info['descricao'],
            data_transacao=info['data_transacao'],
            categoria_id=categoria.id if categoria else None,
            membro_familia_id=membro_familia_id,
            origem=OrigemRegistro.WHATSAPP_AUDIO,
            mensagem_original=texto,
            arquivo_url=audio_url,
            confianca_ia=info.get('confianca', 0.5)
        )

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        return {
            "transacao_id": transacao.id,
            "message": "Áudio processado e transação registrada"
        }

    except Exception as e:
        print(f"Erro ao processar áudio: {e}")
        db.rollback()
        raise


async def _processar_mensagem_imagem(db: Session, usuario: Usuario, image_url: str, caption: str = "", membro_familia_id: int = None) -> dict:
    """Processa mensagem de imagem (nota fiscal/recibo)"""

    try:
        info = llm_service.extrair_de_imagem(image_url, caption)

        if caption:
            categorias = db.query(Categoria).filter(
                (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
            ).all()

            categorias_lista = [
                {"id": c.id, "nome": c.nome, "tipo": c.tipo.value}
                for c in categorias
            ]

            info_texto = llm_service.extrair_transacao_de_texto(caption, categorias_lista)

            if info_texto['valor'] > 0:
                info['valor'] = info_texto['valor']
            if info_texto['descricao']:
                info['descricao'] = info_texto['descricao']

        categoria = db.query(Categoria).filter(
            Categoria.nome == info['categoria_sugerida'],
            (Categoria.padrao == True) | (Categoria.usuario_id == usuario.id)
        ).first()

        transacao = Transacao(
            usuario_id=usuario.id,
            tipo=TipoTransacao(info['tipo']),
            valor=info['valor'],
            descricao=info['descricao'],
            data_transacao=info['data_transacao'],
            categoria_id=categoria.id if categoria else None,
            membro_familia_id=membro_familia_id,
            origem=OrigemRegistro.WHATSAPP_IMAGEM,
            mensagem_original=caption,
            arquivo_url=image_url,
            confianca_ia=info.get('confianca', 0.3)
        )

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        return {
            "transacao_id": transacao.id,
            "message": "Imagem processada e transação registrada"
        }

    except Exception as e:
        print(f"Erro ao processar imagem: {e}")
        db.rollback()
        raise
