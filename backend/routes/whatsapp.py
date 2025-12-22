"""
Webhook do WhatsApp - Processa mensagens com Sistema Multi-Agente
Compatível com UAZAPI
"""

import logging
import re
from fastapi import APIRouter, Depends, Request, BackgroundTasks

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Dict

from backend.core.database import get_db
from backend.core.security import obter_usuario_atual
from backend.models import (
    Usuario, Transacao, Categoria, MembroFamilia,
    OrigemRegistro, TipoTransacao, StatusTransacao, gerar_codigo_unico
)
from backend.services import whatsapp_service, llm_service
from backend.services.memory_service import memory_service
from backend.services.agents.processor import processar_mensagem_v2
from backend.services.agents.base_agent import OrigemMensagem

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


# ============================================================================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# ============================================================================

def formatar_valor_br(valor: float) -> str:
    """Formata valor em formato brasileiro: R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data_br(data) -> str:
    """Formata data em formato brasileiro: dd/mm/yyyy"""
    if isinstance(data, str):
        if '-' in data and len(data) >= 10:
            try:
                data = datetime.strptime(data[:10], '%Y-%m-%d')
            except:
                return data
    if isinstance(data, datetime):
        return data.strftime('%d/%m/%Y')
    return str(data)


def formatar_data_curta(data) -> str:
    """Formata data curta: dd/mm"""
    if isinstance(data, str):
        if '-' in data and len(data) >= 10:
            try:
                data = datetime.strptime(data[:10], '%Y-%m-%d')
            except:
                return data[:5] if len(data) >= 5 else data
    if isinstance(data, datetime):
        return data.strftime('%d/%m')
    return str(data)


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def detectar_comando_exclusao(texto: str) -> str:
    """Detecta comando de exclusão e retorna o código da transação"""
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


def formatar_resposta_transacao(transacao: Transacao, categoria_nome: str = None, categoria_icone: str = None) -> str:
    """Formata resposta de transação"""
    tipo_texto = "Despesa" if transacao.tipo == TipoTransacao.DESPESA else "Receita"
    data = formatar_data_curta(transacao.data_transacao)
    categoria = categoria_nome or 'Outros'
    icone = categoria_icone or ('💸' if transacao.tipo == TipoTransacao.DESPESA else '💰')
    valor = formatar_valor_br(transacao.valor)

    msg = f"""✓ {tipo_texto} registrada

📅 {data} • {transacao.descricao or '-'}
💰 {valor}
{icone} {categoria}

Código: {transacao.codigo}
Para excluir: excluir {transacao.codigo}"""
    return msg


def formatar_resposta_multiplas(transacoes: List[Dict], info: Dict = None) -> str:
    """Formata resposta para múltiplas transações"""
    if not transacoes:
        return "Nenhuma transação encontrada na imagem."

    total_receitas = sum(t['valor'] for t in transacoes if t.get('tipo') == 'receita')
    total_despesas = sum(t['valor'] for t in transacoes if t.get('tipo') == 'despesa')

    origem = info.get('banco_ou_emissor', '') if info else ''
    if origem:
        msg = f"✓ {len(transacoes)} transações registradas ({origem})\n\n"
    else:
        msg = f"✓ {len(transacoes)} transações registradas\n\n"

    for t in transacoes[:15]:
        data = formatar_data_curta(t.get('data', ''))
        if not data or data == 'None':
            data = '--/--'

        codigo = t.get('codigo', '-----')
        descricao = t.get('descricao', '-')[:25]
        valor = t.get('valor', 0)
        tipo_simbolo = "-" if t.get('tipo') == 'despesa' else "+"

        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"[{codigo}] {data} • {descricao}\n"
        msg += f"        {tipo_simbolo}R$ {valor_formatado}\n\n"

    if len(transacoes) > 15:
        msg += f"... e mais {len(transacoes) - 15}\n\n"

    msg += "─────────────────\n"
    if total_receitas > 0:
        msg += f"Receitas: +{formatar_valor_br(total_receitas)}\n"
    if total_despesas > 0:
        msg += f"Despesas: -{formatar_valor_br(total_despesas)}\n"

    saldo = total_receitas - total_despesas
    if total_receitas > 0 and total_despesas > 0:
        sinal = '+' if saldo >= 0 else ''
        msg += f"Saldo: {sinal}{formatar_valor_br(abs(saldo))}\n"

    msg += f"\nPara excluir: excluir [CÓDIGO]"

    return msg


def extrair_numero(chatid: str) -> str:
    """Extrai número limpo do chatid"""
    numero = chatid.replace("@s.whatsapp.net", "").replace("@c.us", "")
    return "".join(filter(str.isdigit, numero))


def gerar_variacoes_numero(numero: str) -> list:
    """Gera variações do número para busca flexível"""
    variacoes = [numero]

    if numero.startswith("55") and len(numero) >= 12:
        sem_ddi = numero[2:]
        variacoes.append(sem_ddi)
        ddd = numero[2:4]
        resto = numero[4:]

        if len(resto) == 8:
            com_nove = f"55{ddd}9{resto}"
            variacoes.append(com_nove)
            variacoes.append(f"{ddd}9{resto}")
        elif len(resto) == 9 and resto.startswith("9"):
            sem_nove = f"55{ddd}{resto[1:]}"
            variacoes.append(sem_nove)
            variacoes.append(f"{ddd}{resto[1:]}")

    return list(set(variacoes))


# ============================================================================
# WEBHOOK PRINCIPAL
# ============================================================================

@router.post("/webhook")
async def webhook_whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Webhook para receber mensagens do UAZAPI
    Usa sistema multi-agente para processamento
    """

    try:
        payload = await request.json()
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

        from sqlalchemy import or_
        filtros_usuario = []
        for var in variacoes:
            filtros_usuario.extend([
                Usuario.whatsapp == var,
                Usuario.telefone == var
            ])

        usuario = db.query(Usuario).filter(or_(*filtros_usuario)).first()

        membro_familia = None

        if not usuario:
            filtros_membro = [MembroFamilia.telefone == var for var in variacoes]
            membro_familia = db.query(MembroFamilia).filter(
                or_(*filtros_membro),
                MembroFamilia.ativo == True
            ).first()

            if membro_familia:
                usuario = db.query(Usuario).filter(Usuario.id == membro_familia.usuario_id).first()

        if not usuario:
            logger.warning(f"[Webhook] Usuário não encontrado: {from_number}")
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

        # Prepara processamento
        user_id = f"user_{usuario.id}"
        origem = OrigemRegistro.WHATSAPP_TEXTO
        mensagem_original = ""
        arquivo_url = None

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
            mensagem_original = message.get("text", "")

            if mensagem_original:
                # Verifica comando de exclusão
                codigo_exclusao = detectar_comando_exclusao(mensagem_original)
                if codigo_exclusao:
                    resultado_exclusao = await _excluir_transacao_por_codigo(
                        db, usuario, codigo_exclusao, from_number, background_tasks
                    )
                    return resultado_exclusao

                # Verifica contexto pendente (documento fiscal)
                contexto_pendente = await memory_service.obter_acao_pendente(from_number) or {}

                if (contexto_pendente.get("tipo") == "confirmacao_documento_fiscal"
                    and mensagem_original.strip().lower() in ["sim", "s", "ok", "confirma", "confirmar", "yes"]):

                    return await _processar_confirmacao_documento_fiscal(
                        db, usuario, membro_familia, user_id, from_number,
                        contexto_pendente, categorias, background_tasks
                    )

                # Processa com sistema multi-agente
                resultado = await processar_mensagem_v2(
                    usuario_id=usuario.id,
                    telefone=from_number,
                    mensagem=mensagem_original,
                    origem=OrigemMensagem.WHATSAPP_TEXTO.value,
                    db=db,
                    contexto_extra={"nome_usuario": sender_name}
                )

                # Envia resposta
                if resultado.mensagem:
                    background_tasks.add_task(
                        whatsapp_service.enviar_mensagem,
                        from_number,
                        resultado.mensagem
                    )

                return {
                    "status": "success" if resultado.sucesso else "processed",
                    "intent": resultado.dados.get("intent"),
                    "transacao_id": resultado.dados.get("transacao_id")
                }

        # ÁUDIO
        elif message_type in ["audio", "audiomessage", "ptt"]:
            origem = OrigemRegistro.WHATSAPP_AUDIO
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
                logger.debug(f"[Webhook] Fallback para URL direta do áudio")
                texto, sucesso = await llm_service.transcrever_audio(arquivo_url)

            if sucesso and texto:
                mensagem_original = texto

                # Processa transcrição com multi-agente
                resultado = await processar_mensagem_v2(
                    usuario_id=usuario.id,
                    telefone=from_number,
                    mensagem=f"[Áudio transcrito] {texto}",
                    origem=OrigemMensagem.WHATSAPP_AUDIO.value,
                    db=db,
                    contexto_extra={"nome_usuario": sender_name}
                )

                if resultado.mensagem:
                    background_tasks.add_task(
                        whatsapp_service.enviar_mensagem,
                        from_number,
                        resultado.mensagem
                    )

                return {"status": "success", "transcricao": texto[:100]}
            else:
                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    "Não consegui entender o áudio. Pode enviar por texto?"
                )
                return {"status": "audio_transcription_failed"}

        # IMAGEM
        elif message_type in ["image", "imagemessage"]:
            origem = OrigemRegistro.WHATSAPP_IMAGEM
            content = message.get("content", {})
            if isinstance(content, dict):
                arquivo_url = content.get("URL", "") or content.get("url", "")
                caption = content.get("caption", "") or message.get("text", "")
            else:
                arquivo_url = message.get("fileURL", "") or message.get("url", "")
                caption = message.get("text", "") or message.get("caption", "")
            mensagem_original = caption
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
                    import httpx
                    import base64 as b64
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(arquivo_url, timeout=30)
                    if resp.status_code == 200:
                        base64_data = b64.b64encode(resp.content).decode('utf-8')
                        mimetype = resp.headers.get('content-type', 'image/jpeg')
                        logger.debug(f"[Webhook] Imagem baixada via URL ({len(base64_data)} chars)")
                except Exception as e:
                    logger.error(f"[Webhook] Erro ao baixar imagem: {e}")

            if base64_data:
                # Analisa o documento
                dados_doc = await llm_service.extrair_extrato_multiplo(base64_data, mimetype, caption)
                tipo_doc = dados_doc.get('tipo_documento', 'outro')
                logger.debug(f"[Webhook] Tipo documento: {tipo_doc}")

                # DOCUMENTO FISCAL
                if tipo_doc == 'documento_fiscal':
                    return await _processar_documento_fiscal(
                        user_id, from_number, dados_doc, background_tasks
                    )

                # EXTRATO/FATURA
                elif tipo_doc in ['extrato_bancario', 'fatura_cartao'] and dados_doc.get('transacoes') and len(dados_doc['transacoes']) > 1:
                    logger.info(f"[Webhook] Extrato: {len(dados_doc['transacoes'])} transações")

                    transacoes_salvas = await _salvar_multiplas_transacoes(
                        db=db,
                        usuario=usuario,
                        membro_familia=membro_familia,
                        transacoes=dados_doc['transacoes'],
                        origem=origem,
                        categorias=categorias
                    )

                    mensagem_resposta = formatar_resposta_multiplas(transacoes_salvas, dados_doc)

                    background_tasks.add_task(
                        whatsapp_service.enviar_mensagem,
                        from_number,
                        mensagem_resposta
                    )

                    return {
                        "status": "success",
                        "acao": "registrar_multiplas",
                        "total": len(transacoes_salvas)
                    }

                # COMPROVANTE ou transação única
                else:
                    dados_imagem = await llm_service.extrair_de_imagem_base64(base64_data, mimetype, caption)
                    logger.debug(f"[Webhook] Dados extraídos: {dados_imagem}")

                    if dados_imagem.get("entendeu") and dados_imagem.get("valor", 0) > 0:
                        # Salva transação
                        transacao_info = await _salvar_transacao_de_imagem(
                            db, usuario, membro_familia, dados_imagem, origem, categorias
                        )

                        if transacao_info and transacao_info.get("transacao"):
                            t = transacao_info["transacao"]
                            mensagem_formatada = formatar_resposta_transacao(
                                t,
                                transacao_info.get("categoria_nome"),
                                transacao_info.get("categoria_icone")
                            )

                            background_tasks.add_task(
                                whatsapp_service.enviar_mensagem,
                                from_number,
                                mensagem_formatada
                            )

                            return {
                                "status": "success",
                                "transacao_id": transacao_info["id"],
                                "codigo": transacao_info["codigo"]
                            }
                    else:
                        # Não entendeu - pede esclarecimento
                        pergunta = dados_imagem.get("pergunta", "O que você gostaria de registrar desta imagem?")
                        background_tasks.add_task(
                            whatsapp_service.enviar_mensagem,
                            from_number,
                            f"📷 {pergunta}"
                        )
                        return {"status": "awaiting_clarification"}
            else:
                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    "Não consegui acessar a imagem. Pode enviar novamente?"
                )
                return {"status": "image_download_failed"}

        # DOCUMENTO (PDF)
        elif message_type in ["document", "documentmessage"]:
            origem = OrigemRegistro.WHATSAPP_IMAGEM
            message_id = message.get("messageid", "")
            filename = message.get("filename", "") or message.get("content", {}).get("filename", "")

            if filename.lower().endswith('.pdf'):
                logger.info(f"[Webhook] PDF recebido: {filename}")

                midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)

                if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
                    base64_data = midia_result["data"]["base64Data"]
                    logger.debug(f"[Webhook] PDF descriptografado ({len(base64_data)} chars)")

                    dados_pdf = await llm_service.extrair_de_pdf_base64(base64_data)

                    if dados_pdf.get('transacoes'):
                        transacoes_salvas = await _salvar_multiplas_transacoes(
                            db=db,
                            usuario=usuario,
                            membro_familia=membro_familia,
                            transacoes=dados_pdf['transacoes'],
                            origem=origem,
                            categorias=categorias
                        )

                        mensagem_resposta = formatar_resposta_multiplas(transacoes_salvas, dados_pdf)

                        background_tasks.add_task(
                            whatsapp_service.enviar_mensagem,
                            from_number,
                            mensagem_resposta
                        )

                        return {
                            "status": "success",
                            "acao": "registrar_pdf",
                            "total": len(transacoes_salvas)
                        }
                    else:
                        background_tasks.add_task(
                            whatsapp_service.enviar_mensagem,
                            from_number,
                            "Não encontrei transações neste PDF. É um extrato bancário?"
                        )
                        return {"status": "pdf_no_transactions"}
                else:
                    background_tasks.add_task(
                        whatsapp_service.enviar_mensagem,
                        from_number,
                        "Não consegui ler o PDF. Pode tentar enviar como imagem?"
                    )
                    return {"status": "pdf_download_failed"}
            else:
                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    "Por enquanto só aceito PDFs de extratos. Pode enviar como imagem?"
                )
                return {"status": "unsupported_document"}

        else:
            logger.warning(f"[Webhook] Tipo não suportado: {message_type}")
            return {"status": "unsupported_message_type", "type": message_type}

    except Exception as e:
        logger.error(f"[Webhook] Erro: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


# ============================================================================
# FUNÇÕES AUXILIARES DE PROCESSAMENTO
# ============================================================================

async def _processar_documento_fiscal(
    user_id: str,
    from_number: str,
    dados_doc: Dict,
    background_tasks: BackgroundTasks
) -> Dict:
    """Processa documento fiscal (DAS, DARF, etc)"""
    valor_total = dados_doc.get('valor_total', 0)
    descricao = dados_doc.get('descricao_documento', 'Documento fiscal')
    data_venc = dados_doc.get('data_vencimento', '')
    emissor = dados_doc.get('banco_ou_emissor', '')

    valor_br = formatar_valor_br(valor_total)
    data_venc_br = formatar_data_br(data_venc) if data_venc else ''

    msg = f"""Identifiquei um documento fiscal

Tipo: {emissor or descricao}
Valor: {valor_br}
{f"Vencimento: {data_venc_br}" if data_venc_br else ""}

Registrar como despesa única de {valor_br}?
Responda SIM para confirmar ou informe como deseja registrar."""

    # Salva contexto
    await memory_service.salvar_acao_pendente(
        from_number,
        "confirmacao_documento_fiscal",
        {
            "valor": valor_total,
            "descricao": emissor or descricao,
            "data_vencimento": data_venc,
            "tipo": "despesa"
        }
    )

    background_tasks.add_task(
        whatsapp_service.enviar_mensagem,
        from_number,
        msg
    )

    return {
        "status": "aguardando_confirmacao",
        "tipo": "documento_fiscal",
        "valor": valor_total
    }


async def _processar_confirmacao_documento_fiscal(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia,
    user_id: str,
    from_number: str,
    contexto_pendente: Dict,
    categorias: list,
    background_tasks: BackgroundTasks
) -> Dict:
    """Processa confirmação de documento fiscal"""
    doc = contexto_pendente.get("dados", {})
    valor = doc.get("valor", 0)
    descricao = doc.get("descricao", "Documento fiscal")
    data_venc = doc.get("data_vencimento", "")

    # Data da transação
    if data_venc:
        try:
            data_transacao = datetime.strptime(data_venc[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except ValueError:
            data_transacao = datetime.now(timezone.utc)
    else:
        data_transacao = datetime.now(timezone.utc)

    # Busca categoria "Impostos" ou "Outros"
    categoria = None
    for c in categorias:
        if c.nome.lower() in ["impostos", "outros"] and c.tipo == TipoTransacao.DESPESA:
            categoria = c
            break

    if not categoria:
        categoria = db.query(Categoria).filter(
            Categoria.nome == "Outros",
            Categoria.tipo == TipoTransacao.DESPESA,
            Categoria.padrao == True
        ).first()

    codigo = gerar_codigo_unico(db)

    transacao = Transacao(
        codigo=codigo,
        usuario_id=usuario.id,
        tipo=TipoTransacao.DESPESA,
        valor=valor,
        descricao=descricao,
        data_transacao=data_transacao,
        categoria_id=categoria.id if categoria else None,
        membro_familia_id=membro_familia.id if membro_familia else None,
        status=StatusTransacao.CONFIRMADA,
        origem=OrigemRegistro.WHATSAPP_IMAGEM,
        mensagem_original=f"Documento fiscal: {descricao}"
    )
    db.add(transacao)
    db.commit()
    db.refresh(transacao)

    logger.info(f"[Webhook] Documento fiscal salvo: ID={transacao.id}, Código={codigo}, R${valor:.2f}")

    # Limpa contexto
    await memory_service.limpar_acao_pendente(from_number)

    mensagem_resposta = formatar_resposta_transacao(
        transacao,
        categoria_nome=categoria.nome if categoria else "Outros",
        categoria_icone=categoria.icone if categoria else "💸"
    )

    background_tasks.add_task(
        whatsapp_service.enviar_mensagem,
        from_number,
        mensagem_resposta
    )

    return {
        "status": "success",
        "acao": "registrar_documento_fiscal",
        "id": transacao.id,
        "codigo": codigo
    }


async def _salvar_transacao_de_imagem(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia,
    dados_imagem: Dict,
    origem: OrigemRegistro,
    categorias: list
) -> Dict:
    """Salva transação extraída de imagem"""
    try:
        # Busca categoria
        categoria = None
        cat_nome = dados_imagem.get('categoria_sugerida', 'Outros')
        tipo = dados_imagem.get('tipo', 'despesa')

        for cat in categorias:
            if cat.nome.lower() == cat_nome.lower() and cat.tipo.value == tipo:
                categoria = cat
                break

        if not categoria:
            categoria = next(
                (c for c in categorias if c.nome == "Outros" and c.tipo.value == tipo),
                None
            )

        # Data
        data_transacao = dados_imagem.get('data_transacao')
        if not data_transacao:
            data_str = dados_imagem.get('data_documento', '')
            if data_str:
                try:
                    data_transacao = datetime.strptime(data_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    data_transacao = datetime.now(timezone.utc)
            else:
                data_transacao = datetime.now(timezone.utc)

        codigo = gerar_codigo_unico(db)

        # Monta descrição
        descricao = dados_imagem.get('descricao', '')
        estabelecimento = dados_imagem.get('estabelecimento', '')
        if estabelecimento and estabelecimento not in descricao:
            descricao = f"{descricao} - {estabelecimento}".strip(" -")

        transacao = Transacao(
            codigo=codigo,
            usuario_id=usuario.id,
            tipo=TipoTransacao(tipo),
            valor=float(dados_imagem.get('valor', 0)),
            descricao=descricao,
            data_transacao=data_transacao,
            categoria_id=categoria.id if categoria else None,
            membro_familia_id=membro_familia.id if membro_familia else None,
            status=StatusTransacao.CONFIRMADA,
            origem=origem,
            confianca_ia=float(dados_imagem.get('confianca', 0.8))
        )

        db.add(transacao)
        db.commit()
        db.refresh(transacao)

        logger.info(f"[Webhook] Transação de imagem salva: ID={transacao.id}, Código={codigo}")

        return {
            "id": transacao.id,
            "codigo": codigo,
            "transacao": transacao,
            "categoria_nome": categoria.nome if categoria else "Outros",
            "categoria_icone": categoria.icone if categoria else "📌"
        }

    except Exception as e:
        logger.error(f"[Webhook] Erro ao salvar transação de imagem: {e}")
        db.rollback()
        return None


async def _salvar_multiplas_transacoes(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia,
    transacoes: List[Dict],
    origem: OrigemRegistro,
    categorias: list
) -> List[Dict]:
    """Salva múltiplas transações de um extrato"""
    transacoes_salvas = []

    for t in transacoes:
        try:
            categoria = None
            cat_nome = t.get('categoria_sugerida', 'Outros')
            tipo = t.get('tipo', 'despesa')

            for cat in categorias:
                if cat.nome.lower() == cat_nome.lower() and cat.tipo.value == tipo:
                    categoria = cat
                    break

            if not categoria:
                categoria = next(
                    (c for c in categorias if c.nome == "Outros" and c.tipo.value == tipo),
                    None
                )

            data_transacao = t.get('data_transacao')
            if not data_transacao:
                data_str = t.get('data', '')
                if isinstance(data_str, str) and data_str:
                    try:
                        data_transacao = datetime.strptime(data_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    except ValueError:
                        data_transacao = datetime.now(timezone.utc)
                else:
                    data_transacao = datetime.now(timezone.utc)

            codigo = gerar_codigo_unico(db)

            transacao = Transacao(
                codigo=codigo,
                usuario_id=usuario.id,
                tipo=TipoTransacao(tipo),
                valor=float(t.get('valor', 0)),
                descricao=t.get('descricao', ''),
                data_transacao=data_transacao,
                categoria_id=categoria.id if categoria else None,
                membro_familia_id=membro_familia.id if membro_familia else None,
                status=StatusTransacao.CONFIRMADA,
                origem=origem,
                confianca_ia=0.8
            )

            db.add(transacao)
            db.flush()

            transacoes_salvas.append({
                'id': transacao.id,
                'codigo': codigo,
                'tipo': tipo,
                'valor': transacao.valor,
                'descricao': transacao.descricao,
                'data': data_transacao.strftime('%Y-%m-%d') if data_transacao else '',
                'categoria': cat_nome
            })

        except Exception as e:
            logger.error(f"[Webhook] Erro ao salvar transação: {e}")
            continue

    db.commit()
    logger.info(f"[Webhook] {len(transacoes_salvas)} transações salvas")
    return transacoes_salvas


async def _excluir_transacao_por_codigo(
    db: Session,
    usuario: Usuario,
    codigo: str,
    numero: str,
    background_tasks: BackgroundTasks
) -> Dict:
    """Exclui uma transação pelo código único"""

    transacao = db.query(Transacao).filter(
        Transacao.codigo == codigo,
        Transacao.usuario_id == usuario.id
    ).first()

    if not transacao:
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            numero,
            f"Transação *{codigo}* não encontrada.\n\nVerifique o código e tente novamente."
        )
        return {"status": "not_found", "codigo": codigo}

    valor = transacao.valor
    descricao = transacao.descricao
    tipo = transacao.tipo.value

    db.delete(transacao)
    db.commit()

    tipo_emoji = "💸" if tipo == "despesa" else "💰"
    background_tasks.add_task(
        whatsapp_service.enviar_mensagem,
        numero,
        f"✓ Transação excluída!\n\n{tipo_emoji} R$ {valor:,.2f}\n📝 {descricao}\nCódigo: {codigo}"
    )

    logger.info(f"[Webhook] Transação {codigo} excluída")
    return {"status": "deleted", "codigo": codigo}


async def _enviar_mensagem_nao_cadastrado(numero: str):
    """Envia mensagem para usuário não cadastrado"""
    mensagem = """Olá! Sou o Kairix, seu assistente financeiro!

Parece que você ainda não tem uma conta.

Acesse nosso site para criar sua conta:
https://kairix.com.br

Depois volte aqui e me conte seus gastos!"""

    await whatsapp_service.enviar_mensagem(numero, mensagem)


# ============================================================================
# ENDPOINTS AUXILIARES
# ============================================================================

@router.get("/status")
async def verificar_status(usuario: Usuario = Depends(obter_usuario_atual)):
    """Verifica status da conexão com WhatsApp"""
    resultado = await whatsapp_service.verificar_conexao()
    return resultado


@router.post("/enviar")
async def enviar_mensagem_manual(
    numero: str,
    mensagem: str,
    usuario: Usuario = Depends(obter_usuario_atual)
):
    """Endpoint para enviar mensagem (requer autenticação)"""
    resultado = await whatsapp_service.enviar_mensagem(numero, mensagem)
    return resultado


@router.post("/teste")
async def teste_webhook(usuario: Usuario = Depends(obter_usuario_atual)):
    """Endpoint para testar se webhook está funcionando"""
    return {
        "status": "ok",
        "message": "Webhook funcionando!",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
