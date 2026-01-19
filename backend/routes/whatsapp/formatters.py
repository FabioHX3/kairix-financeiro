"""
Funções de formatação para respostas do WhatsApp.
"""

from datetime import datetime

from backend.models import TipoTransacao, Transacao


def formatar_valor_br(valor: float) -> str:
    """Formata valor em formato brasileiro: R$ 1.234,56"""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data_br(data: str | datetime) -> str:
    """Formata data em formato brasileiro: dd/mm/yyyy"""
    if isinstance(data, str) and "-" in data and len(data) >= 10:
        try:
            data = datetime.strptime(data[:10], "%Y-%m-%d")
        except ValueError:
            return data
    if isinstance(data, datetime):
        return data.strftime("%d/%m/%Y")
    return str(data)


def formatar_data_curta(data: str | datetime) -> str:
    """Formata data curta: dd/mm"""
    if isinstance(data, str) and "-" in data and len(data) >= 10:
        try:
            data = datetime.strptime(data[:10], "%Y-%m-%d")
        except ValueError:
            return data[:5] if len(data) >= 5 else data
    if isinstance(data, datetime):
        return data.strftime("%d/%m")
    return str(data)


def formatar_resposta_transacao(
    transacao: Transacao,
    categoria_nome: str | None = None,
    categoria_icone: str | None = None,
) -> str:
    """Formata resposta de transação única."""
    tipo_texto = "Despesa" if transacao.tipo == TipoTransacao.DESPESA else "Receita"
    data = formatar_data_curta(transacao.data_transacao)
    categoria = categoria_nome or "Outros"
    icone = categoria_icone or ("💸" if transacao.tipo == TipoTransacao.DESPESA else "💰")
    valor = formatar_valor_br(transacao.valor)

    return f"""✓ {tipo_texto} registrada

📅 {data} • {transacao.descricao or '-'}
💰 {valor}
{icone} {categoria}

Código: {transacao.codigo}
Para excluir: excluir {transacao.codigo}"""


def formatar_resposta_multiplas(transacoes: list[dict], info: dict | None = None) -> str:
    """Formata resposta para múltiplas transações."""
    if not transacoes:
        return "Nenhuma transação encontrada na imagem."

    total_receitas = sum(t["valor"] for t in transacoes if t.get("tipo") == "receita")
    total_despesas = sum(t["valor"] for t in transacoes if t.get("tipo") == "despesa")

    origem = info.get("banco_ou_emissor", "") if info else ""
    if origem:
        msg = f"✓ {len(transacoes)} transações registradas ({origem})\n\n"
    else:
        msg = f"✓ {len(transacoes)} transações registradas\n\n"

    for t in transacoes[:15]:
        data = formatar_data_curta(t.get("data", ""))
        if not data or data == "None":
            data = "--/--"

        codigo = t.get("codigo", "-----")
        descricao = t.get("descricao", "-")[:25]
        valor = t.get("valor", 0)
        tipo_simbolo = "-" if t.get("tipo") == "despesa" else "+"

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
        sinal = "+" if saldo >= 0 else ""
        msg += f"Saldo: {sinal}{formatar_valor_br(abs(saldo))}\n"

    msg += "\nPara excluir: excluir [CÓDIGO]"

    return msg
