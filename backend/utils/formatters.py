"""
Funções de formatação para o Kairix Financeiro.
"""


def fmt_valor(v: float) -> str:
    """
    Formata valor monetário para padrão brasileiro.

    Args:
        v: Valor numérico a ser formatado

    Returns:
        String formatada no padrão R$ 1.234,56

    Exemplo:
        >>> fmt_valor(1234.56)
        'R$ 1.234,56'
    """
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
