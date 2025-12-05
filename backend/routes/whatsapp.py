"""
Webhook do WhatsApp - Processa mensagens com o Agente Financeiro
Compatível com UAZAPI
"""

import re
from fastapi import APIRouter, Depends, Request, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Dict

from backend.core.database import get_db
from backend.models import Usuario, Transacao, Categoria, MembroFamilia, OrigemRegistro, TipoTransacao, StatusTransacao, gerar_codigo_unico
from backend.services import agente, whatsapp_service, llm_service
from backend.services.agent import memoria  # Memória de conversa

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


# ============================================================================
# FUNÇÕES DE FORMATAÇÃO BRASILEIRA
# ============================================================================

def formatar_valor_br(valor: float) -> str:
    """Formata valor em formato brasileiro: R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data_br(data) -> str:
    """Formata data em formato brasileiro: dd/mm/yyyy ou dd/mm"""
    if isinstance(data, str):
        # Tenta converter de ISO (YYYY-MM-DD)
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
    """Formata resposta de transação - estilo A com ícone"""
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


def verificar_duplicado(db: Session, usuario_id: int, valor: float, descricao: str, data: datetime) -> Transacao:
    """
    Verifica se já existe uma transação similar (possível duplicado).
    Retorna a transação duplicada se encontrar, None caso contrário.
    """
    from datetime import timedelta

    # Busca transações com mesmo valor no mesmo dia ou dia anterior
    data_inicio = data - timedelta(days=1)
    data_fim = data + timedelta(days=1)

    transacoes_similares = db.query(Transacao).filter(
        Transacao.usuario_id == usuario_id,
        Transacao.valor == valor,
        Transacao.data_transacao >= data_inicio,
        Transacao.data_transacao <= data_fim
    ).all()

    # Verifica similaridade na descrição
    for t in transacoes_similares:
        if t.descricao and descricao:
            # Compara palavras-chave
            palavras_existente = set(t.descricao.lower().split())
            palavras_nova = set(descricao.lower().split())
            # Se mais de 50% das palavras são iguais, considera duplicado
            if len(palavras_existente & palavras_nova) / max(len(palavras_nova), 1) > 0.5:
                return t
        elif not t.descricao and not descricao:
            # Ambas sem descrição, mesmo valor, mesma data = duplicado
            return t

    return None


def formatar_resposta_multiplas(transacoes: List[Dict], info: Dict = None) -> str:
    """Formata resposta para múltiplas transações - opção 1 com código no início"""
    if not transacoes:
        return "Nenhuma transação encontrada na imagem."

    total_receitas = sum(t['valor'] for t in transacoes if t.get('tipo') == 'receita')
    total_despesas = sum(t['valor'] for t in transacoes if t.get('tipo') == 'despesa')

    # Cabeçalho
    origem = info.get('banco_ou_emissor', '') if info else ''
    if origem:
        msg = f"✓ {len(transacoes)} transações registradas ({origem})\n\n"
    else:
        msg = f"✓ {len(transacoes)} transações registradas\n\n"

    # Lista de transações - formato alinhado com código no início
    for t in transacoes[:15]:  # Limita a 15
        data = formatar_data_curta(t.get('data', ''))
        if not data or data == 'None':
            data = '--/--'

        codigo = t.get('codigo', '-----')
        descricao = t.get('descricao', '-')[:25]
        valor = t.get('valor', 0)
        tipo_simbolo = "-" if t.get('tipo') == 'despesa' else "+"

        # Formato: [CÓDIGO] DATA • Descrição
        #          +/-R$ valor (formato brasileiro)
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        msg += f"[{codigo}] {data} • {descricao}\n"
        msg += f"        {tipo_simbolo}R$ {valor_formatado}\n\n"

    if len(transacoes) > 15:
        msg += f"... e mais {len(transacoes) - 15}\n\n"

    # Resumo com formato brasileiro
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

        # Busca últimas transações para contexto do agente
        ultimas_transacoes = db.query(Transacao).filter(
            Transacao.usuario_id == usuario.id
        ).order_by(Transacao.criado_em.desc()).limit(5).all()

        ultimas_str = []
        for t in ultimas_transacoes:
            tipo = "despesa" if t.tipo == TipoTransacao.DESPESA else "receita"
            data = t.data_transacao.strftime('%d/%m/%Y')
            ultimas_str.append(f"[{t.codigo}] {data} - {t.descricao} - R$ {t.valor:.2f} ({tipo})")

        contexto_extra = {
            "nome_usuario": sender_name,
            "ultimas_transacoes": "\n".join(ultimas_str) if ultimas_str else "Nenhuma transação registrada ainda"
        }

        # UAZAPI: tipo em message.messageType ou message.type
        message_type = message.get("messageType", "") or message.get("type", "text")
        message_type = message_type.lower()

        print(f"[Webhook] Tipo: {message_type}, Texto: {message.get('text', '')[:50]}")

        # TEXTO (Conversation, ExtendedTextMessage, text)
        if message_type in ["conversation", "extendedtextmessage", "text"]:
            mensagem_original = message.get("text", "")

            if mensagem_original:
                # Verifica se é comando de exclusão
                codigo_exclusao = detectar_comando_exclusao(mensagem_original)
                if codigo_exclusao:
                    resultado_exclusao = await _excluir_transacao_por_codigo(
                        db, usuario, codigo_exclusao, from_number, background_tasks
                    )
                    return resultado_exclusao

                # ============================================================
                # VERIFICA CONTEXTO PENDENTE (documento fiscal, etc)
                # ============================================================
                contexto_pendente = memoria.get_contexto(user_id)

                # Se tem documento fiscal pendente e usuário confirma
                if (contexto_pendente.get("aguardando") == "confirmacao_documento_fiscal"
                    and mensagem_original.strip().lower() in ["sim", "s", "ok", "confirma", "confirmar", "yes"]):

                    doc = contexto_pendente.get("documento_fiscal", {})
                    valor = doc.get("valor", 0)
                    descricao = doc.get("descricao", "Documento fiscal")
                    data_venc = doc.get("data_vencimento", "")

                    # Determina a data da transação
                    if data_venc:
                        try:
                            data_transacao = datetime.strptime(data_venc[:10], '%Y-%m-%d')
                        except:
                            data_transacao = datetime.now()
                    else:
                        data_transacao = datetime.now()

                    # Busca categoria "Outros" para despesa
                    categoria = db.query(Categoria).filter(
                        Categoria.nome == "Outros",
                        Categoria.tipo == TipoTransacao.DESPESA,
                        Categoria.padrao == True
                    ).first()

                    # Gera código único
                    codigo = gerar_codigo_unico(db)

                    # Cria transação
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

                    print(f"[Webhook] Documento fiscal salvo: ID={transacao.id}, Código={codigo}, R${valor:.2f}")

                    # Limpa contexto
                    memoria.limpar_contexto(user_id)

                    # Formata resposta usando o template padrão
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

                # Processamento normal pelo agente
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

            # Tenta baixar mídia descriptografada via UAZAPI
            message_id = message.get("messageid", "")
            base64_data = None
            mimetype = "image/jpeg"

            if message_id:
                midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)
                if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
                    base64_data = midia_result["data"]["base64Data"]
                    mimetype = midia_result["data"].get("mimetype", "image/jpeg")
                    print(f"[Webhook] Mídia descriptografada ({len(base64_data)} chars)")

            # Se não conseguiu via UAZAPI, tenta URL direta
            if not base64_data and arquivo_url:
                try:
                    import requests
                    import base64 as b64
                    resp = requests.get(arquivo_url, timeout=30)
                    if resp.status_code == 200:
                        base64_data = b64.b64encode(resp.content).decode('utf-8')
                        mimetype = resp.headers.get('content-type', 'image/jpeg')
                        print(f"[Webhook] Imagem baixada via URL ({len(base64_data)} chars)")
                except Exception as e:
                    print(f"[Webhook] Erro ao baixar imagem: {e}")

            if base64_data:
                # Analisa o documento
                print(f"[Webhook] Analisando imagem...")
                dados_doc = llm_service.extrair_extrato_multiplo(base64_data, mimetype, caption)
                tipo_doc = dados_doc.get('tipo_documento', 'outro')
                print(f"[Webhook] Tipo documento: {tipo_doc}")

                # DOCUMENTO FISCAL (DAS, Simples Nacional, DARF, etc)
                if tipo_doc == 'documento_fiscal':
                    valor_total = dados_doc.get('valor_total', 0)
                    descricao = dados_doc.get('descricao_documento', 'Documento fiscal')
                    data_venc = dados_doc.get('data_vencimento', '')
                    emissor = dados_doc.get('banco_ou_emissor', '')

                    # Formata valores em brasileiro
                    valor_br = formatar_valor_br(valor_total)
                    data_venc_br = formatar_data_br(data_venc) if data_venc else ''

                    msg = f"""Identifiquei um documento fiscal

Tipo: {emissor or descricao}
Valor: {valor_br}
{f"Vencimento: {data_venc_br}" if data_venc_br else ""}

Registrar como despesa única de {valor_br}?
Responda SIM para confirmar ou informe como deseja registrar."""

                    # IMPORTANTE: Salva contexto para lembrar quando responder "Sim"
                    memoria.set_contexto(user_id, {
                        "aguardando": "confirmacao_documento_fiscal",
                        "documento_fiscal": {
                            "valor": valor_total,
                            "descricao": emissor or descricao,
                            "data_vencimento": data_venc,
                            "tipo": "despesa"
                        }
                    })

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

                # EXTRATO/FATURA com múltiplas transações
                elif tipo_doc in ['extrato_bancario', 'fatura_cartao'] and dados_doc.get('transacoes') and len(dados_doc['transacoes']) > 1:
                    print(f"[Webhook] Extrato: {len(dados_doc['transacoes'])} transações")

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
                    dados_imagem = llm_service.extrair_de_imagem_base64(base64_data, mimetype, caption)
                    print(f"[Webhook] Dados extraídos: {dados_imagem}")

                    resultado = await agente.processar_imagem(
                        user_id=user_id,
                        dados_imagem=dados_imagem,
                        caption=caption,
                        categorias=categorias_lista,
                        contexto_extra=contexto_extra
                    )
            else:
                # Não conseguiu obter a imagem
                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    "📷 Não consegui acessar a imagem. Pode enviar novamente?"
                )
                return {"status": "image_download_failed"}

        # DOCUMENTO (PDF)
        elif message_type in ["document", "documentmessage"]:
            origem = OrigemRegistro.WHATSAPP_IMAGEM
            message_id = message.get("messageid", "")
            filename = message.get("filename", "") or message.get("content", {}).get("filename", "")

            if filename.lower().endswith('.pdf'):
                print(f"[Webhook] PDF recebido: {filename}")

                midia_result = await whatsapp_service.baixar_midia(message_id, return_base64=True)

                if midia_result.get("success") and midia_result.get("data", {}).get("base64Data"):
                    base64_data = midia_result["data"]["base64Data"]
                    print(f"[Webhook] PDF descriptografado ({len(base64_data)} chars)")

                    dados_pdf = llm_service.extrair_de_pdf_base64(base64_data)

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
                            "📄 Não encontrei transações neste PDF. É um extrato bancário?"
                        )
                        return {"status": "pdf_no_transactions"}
                else:
                    background_tasks.add_task(
                        whatsapp_service.enviar_mensagem,
                        from_number,
                        "📄 Não consegui ler o PDF. Pode tentar enviar como imagem?"
                    )
                    return {"status": "pdf_download_failed"}
            else:
                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    "📎 Por enquanto só aceito PDFs de extratos. Pode enviar como imagem?"
                )
                return {"status": "unsupported_document"}

        else:
            print(f"[Webhook] Tipo não suportado: {message_type}")
            return {"status": "unsupported_message_type", "type": message_type}

        if not resultado:
            return {"status": "no_result"}

        # Processa a ação do agente
        transacao_info = None

        if resultado.acao == "registrar" and resultado.transacao:
            transacao_info = await _salvar_transacao(
                db=db,
                usuario=usuario,
                membro_familia=membro_familia,
                dados=resultado.transacao,
                origem=origem,
                mensagem_original=mensagem_original,
                arquivo_url=arquivo_url,
                categorias=categorias
            )

            # Verifica se é duplicado
            if transacao_info and transacao_info.get("duplicado"):
                existente = transacao_info["transacao_existente"]
                msg_duplicado = f"""⚠️ *Possível duplicado detectado!*

Encontrei uma transação similar já registrada:

📋 Código: {existente.codigo}
💸 Valor: R$ {existente.valor:,.2f}
📝 {existente.descricao}
🗓 {existente.data_transacao.strftime('%d/%m/%Y')}

🔄 Quer que eu registre mesmo assim?
• Responda *SIM* para registrar
• Ou *EXCLUIR {existente.codigo}* para apagar o antigo"""

                background_tasks.add_task(
                    whatsapp_service.enviar_mensagem,
                    from_number,
                    msg_duplicado
                )

                return {
                    "status": "duplicado_detectado",
                    "codigo_existente": existente.codigo
                }

            # Transação salva com sucesso - usa formato melhorado
            elif transacao_info and transacao_info.get("transacao"):
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
                    "acao": "registrar",
                    "transacao_id": transacao_info["id"],
                    "codigo": transacao_info["codigo"]
                }

        # Envia resposta do agente (para ações não-registrar)
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            from_number,
            resultado.mensagem
        )

        return {
            "status": "success",
            "acao": resultado.acao
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
) -> Dict:
    """Salva transação no banco de dados. Retorna dict com info da transação."""

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

        # Verifica duplicado
        duplicado = verificar_duplicado(db, usuario.id, dados.valor, dados.descricao, data_transacao)
        if duplicado:
            print(f"[Webhook] Possível duplicado encontrado: {duplicado.codigo}")
            return {
                "id": None,
                "codigo": None,
                "duplicado": True,
                "transacao_existente": duplicado,
                "categoria_nome": categoria.nome if categoria else "Outros",
                "categoria_icone": categoria.icone if categoria else "📌"
            }

        # Gera código único (com verificação no banco)
        codigo = gerar_codigo_unico(db)

        # Cria transação
        transacao = Transacao(
            codigo=codigo,
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

        print(f"[Webhook] Transação salva: ID={transacao.id}, Código={codigo}, R${dados.valor:.2f} ({dados.tipo})")
        return {
            "id": transacao.id,
            "codigo": codigo,
            "duplicado": False,
            "transacao": transacao,
            "categoria_nome": categoria.nome if categoria else "Outros",
            "categoria_icone": categoria.icone if categoria else "📌"
        }

    except Exception as e:
        print(f"[Webhook] Erro ao salvar: {e}")
        db.rollback()
        raise


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
            # Busca categoria pelo nome
            categoria = None
            cat_nome = t.get('categoria_sugerida', 'Outros')
            tipo = t.get('tipo', 'despesa')

            for cat in categorias:
                if cat.nome.lower() == cat_nome.lower() and cat.tipo.value == tipo:
                    categoria = cat
                    break

            # Se não encontrou, usa "Outros"
            if not categoria:
                categoria = next(
                    (c for c in categorias if c.nome == "Outros" and c.tipo.value == tipo),
                    None
                )

            # Converte data
            data_transacao = t.get('data_transacao')
            if not data_transacao:
                data_str = t.get('data', '')
                if isinstance(data_str, str) and data_str:
                    try:
                        data_transacao = datetime.strptime(data_str, "%Y-%m-%d")
                    except:
                        data_transacao = datetime.now()
                else:
                    data_transacao = datetime.now()

            # Gera código único (com verificação no banco)
            codigo = gerar_codigo_unico(db)

            # Cria transação
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
            db.flush()  # Para obter o ID

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
            print(f"[Webhook] Erro ao salvar transação: {e}")
            continue

    db.commit()
    print(f"[Webhook] {len(transacoes_salvas)} transações salvas")
    return transacoes_salvas


async def _excluir_transacao_por_codigo(
    db: Session,
    usuario: Usuario,
    codigo: str,
    numero: str,
    background_tasks: BackgroundTasks
) -> Dict:
    """Exclui uma transação pelo código único"""

    # Busca transação pelo código
    transacao = db.query(Transacao).filter(
        Transacao.codigo == codigo,
        Transacao.usuario_id == usuario.id
    ).first()

    if not transacao:
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            numero,
            f"❌ Transação *{codigo}* não encontrada.\n\nVerifique o código e tente novamente."
        )
        return {"status": "not_found", "codigo": codigo}

    # Guarda informações antes de excluir
    valor = transacao.valor
    descricao = transacao.descricao
    tipo = transacao.tipo.value

    # Exclui a transação
    db.delete(transacao)
    db.commit()

    tipo_emoji = "💸" if tipo == "despesa" else "💰"
    background_tasks.add_task(
        whatsapp_service.enviar_mensagem,
        numero,
        f"✅ Transação excluída!\n\n{tipo_emoji} R$ {valor:,.2f}\n📝 {descricao}\n🔖 Código: {codigo}"
    )

    print(f"[Webhook] Transação {codigo} excluída")
    return {"status": "deleted", "codigo": codigo}


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
