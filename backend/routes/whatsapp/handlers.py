"""
Handlers para processamento de diferentes tipos de mensagens.
"""

import logging
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from backend.models import (
    Categoria,
    MembroFamilia,
    OrigemRegistro,
    StatusTransacao,
    TipoTransacao,
    Transacao,
    Usuario,
    gerar_codigo_unico,
)
from backend.routes.whatsapp.formatters import (
    formatar_data_br,
    formatar_resposta_transacao,
    formatar_valor_br,
)
from backend.services import whatsapp_service
from backend.services.memory_service import memory_service

logger = logging.getLogger(__name__)


async def processar_documento_fiscal(
    user_id: str,
    from_number: str,
    dados_doc: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """Processa documento fiscal (DAS, DARF, etc)."""
    valor_total = dados_doc.get("valor_total", 0)
    descricao = dados_doc.get("descricao_documento", "Documento fiscal")
    data_venc = dados_doc.get("data_vencimento", "")
    emissor = dados_doc.get("banco_ou_emissor", "")

    valor_br = formatar_valor_br(valor_total)
    data_venc_br = formatar_data_br(data_venc) if data_venc else ""

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
            "tipo": "despesa",
        },
    )

    background_tasks.add_task(whatsapp_service.enviar_mensagem, from_number, msg)

    return {
        "status": "aguardando_confirmacao",
        "tipo": "documento_fiscal",
        "valor": valor_total,
    }


async def processar_confirmacao_documento_fiscal(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia | None,
    user_id: str,
    from_number: str,
    contexto_pendente: dict,
    categorias: list,
    background_tasks: BackgroundTasks,
) -> dict:
    """Processa confirmação de documento fiscal."""
    doc = contexto_pendente.get("dados", {})
    valor = doc.get("valor", 0)
    descricao = doc.get("descricao", "Documento fiscal")
    data_venc = doc.get("data_vencimento", "")

    # Data da transação
    if data_venc:
        try:
            data_transacao = datetime.strptime(data_venc[:10], "%Y-%m-%d").replace(
                tzinfo=UTC
            )
        except ValueError:
            data_transacao = datetime.now(UTC)
    else:
        data_transacao = datetime.now(UTC)

    # Busca categoria "Impostos" ou "Outros"
    categoria = None
    for c in categorias:
        if c.nome.lower() in ["impostos", "outros"] and c.tipo == TipoTransacao.DESPESA:
            categoria = c
            break

    if not categoria:
        categoria = (
            db.query(Categoria)
            .filter(
                Categoria.nome == "Outros",
                Categoria.tipo == TipoTransacao.DESPESA,
                Categoria.padrao.is_(True),
            )
            .first()
        )

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
        mensagem_original=f"Documento fiscal: {descricao}",
    )
    db.add(transacao)
    db.commit()
    db.refresh(transacao)

    logger.info(
        f"[Webhook] Documento fiscal salvo: ID={transacao.id}, Código={codigo}, R${valor:.2f}"
    )

    # Limpa contexto
    await memory_service.limpar_acao_pendente(from_number)

    mensagem_resposta = formatar_resposta_transacao(
        transacao,
        categoria_nome=categoria.nome if categoria else "Outros",
        categoria_icone=categoria.icone if categoria else "💸",
    )

    background_tasks.add_task(whatsapp_service.enviar_mensagem, from_number, mensagem_resposta)

    return {
        "status": "success",
        "acao": "registrar_documento_fiscal",
        "id": transacao.id,
        "codigo": codigo,
    }


async def salvar_transacao_de_imagem(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia | None,
    dados_imagem: dict,
    origem: OrigemRegistro,
    categorias: list,
) -> dict | None:
    """Salva transação extraída de imagem."""
    try:
        # Busca categoria
        categoria = None
        cat_nome = dados_imagem.get("categoria_sugerida", "Outros")
        tipo = dados_imagem.get("tipo", "despesa")

        for cat in categorias:
            if cat.nome.lower() == cat_nome.lower() and cat.tipo.value == tipo:
                categoria = cat
                break

        if not categoria:
            categoria = next(
                (c for c in categorias if c.nome == "Outros" and c.tipo.value == tipo),
                None,
            )

        # Data
        data_transacao = dados_imagem.get("data_transacao")
        if not data_transacao:
            data_str = dados_imagem.get("data_documento", "")
            if data_str:
                try:
                    data_transacao = datetime.strptime(data_str, "%Y-%m-%d").replace(
                        tzinfo=UTC
                    )
                except ValueError:
                    data_transacao = datetime.now(UTC)
            else:
                data_transacao = datetime.now(UTC)

        codigo = gerar_codigo_unico(db)

        # Monta descrição
        descricao = dados_imagem.get("descricao", "")
        estabelecimento = dados_imagem.get("estabelecimento", "")
        if estabelecimento and estabelecimento not in descricao:
            descricao = f"{descricao} - {estabelecimento}".strip(" -")

        transacao = Transacao(
            codigo=codigo,
            usuario_id=usuario.id,
            tipo=TipoTransacao(tipo),
            valor=float(dados_imagem.get("valor", 0)),
            descricao=descricao,
            data_transacao=data_transacao,
            categoria_id=categoria.id if categoria else None,
            membro_familia_id=membro_familia.id if membro_familia else None,
            status=StatusTransacao.CONFIRMADA,
            origem=origem,
            confianca_ia=float(dados_imagem.get("confianca", 0.8)),
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
            "categoria_icone": categoria.icone if categoria else "📌",
        }

    except Exception as e:
        logger.error(f"[Webhook] Erro ao salvar transação de imagem: {e}")
        db.rollback()
        return None


async def salvar_multiplas_transacoes(
    db: Session,
    usuario: Usuario,
    membro_familia: MembroFamilia | None,
    transacoes: list[dict],
    origem: OrigemRegistro,
    categorias: list,
) -> list[dict]:
    """Salva múltiplas transações de um extrato."""
    transacoes_salvas = []

    for t in transacoes:
        try:
            categoria = None
            cat_nome = t.get("categoria_sugerida", "Outros")
            tipo = t.get("tipo", "despesa")

            for cat in categorias:
                if cat.nome.lower() == cat_nome.lower() and cat.tipo.value == tipo:
                    categoria = cat
                    break

            if not categoria:
                categoria = next(
                    (c for c in categorias if c.nome == "Outros" and c.tipo.value == tipo),
                    None,
                )

            data_transacao = t.get("data_transacao")
            if not data_transacao:
                data_str = t.get("data", "")
                if isinstance(data_str, str) and data_str:
                    try:
                        data_transacao = datetime.strptime(data_str, "%Y-%m-%d").replace(
                            tzinfo=UTC
                        )
                    except ValueError:
                        data_transacao = datetime.now(UTC)
                else:
                    data_transacao = datetime.now(UTC)

            codigo = gerar_codigo_unico(db)

            transacao = Transacao(
                codigo=codigo,
                usuario_id=usuario.id,
                tipo=TipoTransacao(tipo),
                valor=float(t.get("valor", 0)),
                descricao=t.get("descricao", ""),
                data_transacao=data_transacao,
                categoria_id=categoria.id if categoria else None,
                membro_familia_id=membro_familia.id if membro_familia else None,
                status=StatusTransacao.CONFIRMADA,
                origem=origem,
                confianca_ia=0.8,
            )

            db.add(transacao)
            db.flush()

            transacoes_salvas.append(
                {
                    "id": transacao.id,
                    "codigo": codigo,
                    "tipo": tipo,
                    "valor": transacao.valor,
                    "descricao": transacao.descricao,
                    "data": data_transacao.strftime("%Y-%m-%d") if data_transacao else "",
                    "categoria": cat_nome,
                }
            )

        except Exception as e:
            logger.error(f"[Webhook] Erro ao salvar transação: {e}")
            continue

    db.commit()
    logger.info(f"[Webhook] {len(transacoes_salvas)} transações salvas")
    return transacoes_salvas


async def excluir_transacao_por_codigo(
    db: Session,
    usuario: Usuario,
    codigo: str,
    numero: str,
    background_tasks: BackgroundTasks,
) -> dict:
    """Exclui uma transação pelo código único."""
    transacao = (
        db.query(Transacao)
        .filter(
            Transacao.codigo == codigo,
            Transacao.usuario_id == usuario.id,
        )
        .first()
    )

    if not transacao:
        background_tasks.add_task(
            whatsapp_service.enviar_mensagem,
            numero,
            f"Transação *{codigo}* não encontrada.\n\nVerifique o código e tente novamente.",
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
        f"✓ Transação excluída!\n\n{tipo_emoji} R$ {valor:,.2f}\n📝 {descricao}\nCódigo: {codigo}",
    )

    logger.info(f"[Webhook] Transação {codigo} excluída")
    return {"status": "deleted", "codigo": codigo}


async def enviar_mensagem_nao_cadastrado(numero: str) -> None:
    """Envia mensagem para usuário não cadastrado."""
    mensagem = """Olá! Sou o Kairix, seu assistente financeiro!

Parece que você ainda não tem uma conta.

Acesse nosso site para criar sua conta:
https://kairix.com.br

Depois volte aqui e me conte seus gastos!"""

    await whatsapp_service.enviar_mensagem(numero, mensagem)
