"""
Personality Agent - Aplica estilo de comunicação nas respostas.

Responsabilidades:
- Aplicar personalidade (formal, amigável, divertido)
- Adaptar tom e linguagem
- Manter consistência na comunicação
"""

from typing import Dict
from datetime import datetime, timezone

from backend.services.agents.base_agent import (
    BaseAgent,
    AgentContext,
    AgentResponse
)


class PersonalityAgent(BaseAgent):
    """
    Agente de personalidade - transforma mensagens para o estilo do usuário.

    Personalidades:
    - FORMAL: Profissional, direto, sem emojis
    - AMIGAVEL: Simpático, usa emojis moderados, tom casual
    - DIVERTIDO: Descontraído, muitos emojis, gírias, brincadeiras
    """

    name = "personality"
    description = "Aplica estilo de comunicação"

    # Templates de saudação por personalidade
    SAUDACOES = {
        "formal": {
            "manha": "Bom dia.",
            "tarde": "Boa tarde.",
            "noite": "Boa noite.",
            "ola": "Olá."
        },
        "amigavel": {
            "manha": "Bom dia!",
            "tarde": "Boa tarde!",
            "noite": "Boa noite!",
            "ola": "Oi!"
        },
        "divertido": {
            "manha": "Bom diaaaa! ☀️",
            "tarde": "Boa tardee! 🌤️",
            "noite": "Boa noitee! 🌙",
            "ola": "E aíí! 👋"
        }
    }

    # Confirmações por personalidade
    CONFIRMACOES = {
        "formal": [
            "Registrado.",
            "Transação salva.",
            "Concluído.",
            "Feito."
        ],
        "amigavel": [
            "Registrado!",
            "Pronto!",
            "Anotado!",
            "Feito!"
        ],
        "divertido": [
            "Anotadíssimo! ✅",
            "Na conta! 💰",
            "Fechou! 🎯",
            "Beleza! 👍"
        ]
    }

    # Emojis por categoria
    EMOJIS_CATEGORIA = {
        "Alimentacao": "🍽️",
        "Alimentação": "🍽️",
        "Transporte": "🚗",
        "Saude": "🏥",
        "Saúde": "🏥",
        "Educacao": "📚",
        "Educação": "📚",
        "Lazer": "🎮",
        "Casa": "🏠",
        "Vestuario": "👕",
        "Vestuário": "👕",
        "Outros": "📌",
        "Salario": "💼",
        "Salário": "💼",
        "Freelance": "💻",
        "Investimentos": "📈",
        "Vendas": "🛒",
        "Aluguel": "🏡"
    }

    def can_handle(self, context: AgentContext) -> bool:
        """Personality Agent é chamado internamente"""
        return False

    async def process(self, context: AgentContext) -> AgentResponse:
        """Não processa diretamente"""
        return AgentResponse(
            sucesso=False,
            mensagem="Personality Agent não processa mensagens diretamente"
        )

    def obter_saudacao(self, personalidade: str = "amigavel") -> str:
        """Retorna saudação apropriada para hora e personalidade"""
        hora = datetime.now(timezone.utc).hour

        if hora < 12:
            periodo = "manha"
        elif hora < 18:
            periodo = "tarde"
        else:
            periodo = "noite"

        saudacoes = self.SAUDACOES.get(personalidade, self.SAUDACOES["amigavel"])
        return saudacoes.get(periodo, saudacoes["ola"])

    def obter_confirmacao(self, personalidade: str = "amigavel") -> str:
        """Retorna confirmação aleatória para a personalidade"""
        import random
        confirmacoes = self.CONFIRMACOES.get(personalidade, self.CONFIRMACOES["amigavel"])
        return random.choice(confirmacoes)

    def obter_emoji_categoria(self, categoria: str) -> str:
        """Retorna emoji para categoria"""
        return self.EMOJIS_CATEGORIA.get(categoria, "📌")

    def formatar_mensagem_transacao(
        self,
        personalidade: str,
        tipo: str,
        valor: float,
        descricao: str,
        categoria: str,
        codigo: str
    ) -> str:
        """
        Formata mensagem de transação salva conforme personalidade.

        Args:
            personalidade: formal, amigavel, divertido
            tipo: receita ou despesa
            valor: valor da transação
            descricao: descrição
            categoria: nome da categoria
            codigo: código da transação

        Returns:
            Mensagem formatada
        """
        tipo_texto = "Receita" if tipo == "receita" else "Despesa"
        emoji_tipo = "💰" if tipo == "receita" else "💸"
        emoji_cat = self.obter_emoji_categoria(categoria)
        confirmacao = self.obter_confirmacao(personalidade)

        valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        if personalidade == "formal":
            return (
                f"{confirmacao}\n\n"
                f"Tipo: {tipo_texto}\n"
                f"Valor: {valor_fmt}\n"
                f"Descricao: {descricao}\n"
                f"Categoria: {categoria}\n"
                f"Codigo: {codigo}\n\n"
                f"Para corrigir ou excluir, informe o codigo."
            )

        elif personalidade == "divertido":
            return (
                f"{confirmacao}\n\n"
                f"{emoji_tipo} {tipo_texto}\n"
                f"💵 {valor_fmt}\n"
                f"📝 {descricao}\n"
                f"{emoji_cat} {categoria}\n"
                f"🔖 Codigo: {codigo}\n\n"
                f"Algo errado, me conta que a gente resolve!"
            )

        else:  # amigavel (default)
            return (
                f"{confirmacao}\n\n"
                f"{emoji_tipo} {tipo_texto}\n"
                f"R$ {valor_fmt}\n"
                f"{descricao}\n"
                f"{emoji_cat} {categoria}\n"
                f"Codigo: {codigo}\n\n"
                f"Algo errado, me avisa!"
            )

    def formatar_pedido_confirmacao(
        self,
        personalidade: str,
        tipo: str,
        valor: float,
        descricao: str,
        categoria: str
    ) -> str:
        """
        Formata mensagem pedindo confirmação.
        """
        tipo_texto = "Receita" if tipo == "receita" else "Despesa"
        emoji_tipo = "💰" if tipo == "receita" else "💸"
        emoji_cat = self.obter_emoji_categoria(categoria)

        valor_fmt = f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        if personalidade == "formal":
            return (
                f"Dados extraidos:\n\n"
                f"Tipo: {tipo_texto}\n"
                f"Valor: {valor_fmt}\n"
                f"Descricao: {descricao}\n"
                f"Categoria: {categoria}\n\n"
                f"Confirma o registro? (sim/nao)"
            )

        elif personalidade == "divertido":
            return (
                f"Olha o que eu entendi! 🤔\n\n"
                f"{emoji_tipo} {tipo_texto}\n"
                f"💵 {valor_fmt}\n"
                f"📝 {descricao}\n"
                f"{emoji_cat} {categoria}\n\n"
                f"Ta certinho? Manda um 'sim' ou 'nao'! 😊"
            )

        else:  # amigavel
            return (
                f"Entendi isso:\n\n"
                f"{emoji_tipo} {tipo_texto}\n"
                f"{valor_fmt}\n"
                f"{descricao}\n"
                f"{emoji_cat} {categoria}\n\n"
                f"Certo? Se nao, me corrija!"
            )

    def formatar_saudacao_inicial(self, personalidade: str, nome: str = None) -> str:
        """Formata saudação inicial do assistente"""
        saudacao = self.obter_saudacao(personalidade)

        if personalidade == "formal":
            msg = f"{saudacao} Sou o assistente financeiro Kairix."
            if nome:
                msg = f"{saudacao} {nome}. Sou o assistente financeiro Kairix."
            msg += "\n\nInforme seus gastos e receitas para registro."
            msg += "\n\nExemplo: 'Despesa de 50 reais no mercado'"

        elif personalidade == "divertido":
            msg = f"{saudacao}"
            if nome:
                msg += f" {nome}!"
            msg += " Sou o Kairix, seu parceiro das financas! 🤑"
            msg += "\n\nMe conta seus gastos e ganhos que eu organizo tudo!"
            msg += "\n\n💡 Manda assim: 'gastei 50 no mercado'"

        else:  # amigavel
            msg = f"{saudacao}"
            if nome:
                msg += f" {nome}!"
            msg += " Sou o Kairix, seu assistente financeiro."
            msg += "\n\nMe conta seus gastos e receitas que eu organizo pra voce!"
            msg += "\n\nExemplo: 'Gastei 50 no almoco'"

        return msg

    def formatar_erro(self, personalidade: str, mensagem: str = None) -> str:
        """Formata mensagem de erro"""
        if personalidade == "formal":
            base = "Nao foi possivel processar a solicitacao."
            if mensagem:
                base += f"\n{mensagem}"
            base += "\nPor favor, tente novamente."

        elif personalidade == "divertido":
            base = "Ops! Deu ruim aqui 😅"
            if mensagem:
                base += f"\n{mensagem}"
            base += "\nPode tentar de novo?"

        else:  # amigavel
            base = "Desculpe, tive um problema."
            if mensagem:
                base += f"\n{mensagem}"
            base += "\nPode repetir?"

        return base

    def formatar_ajuda(self, personalidade: str) -> str:
        """Formata mensagem de ajuda"""
        if personalidade == "formal":
            return (
                "Funcionalidades disponiveis:\n\n"
                "- Registro de despesas e receitas\n"
                "- Analise de fotos de comprovantes\n"
                "- Transcricao de audios\n"
                "- Consulta de saldo e gastos\n"
                "- Organizacao por categorias\n\n"
                "Exemplos de uso:\n"
                "- 'Despesa de 150 reais no supermercado'\n"
                "- 'Recebi 3000 de salario'\n"
                "- Envie foto de nota fiscal\n"
                "- Envie audio descrevendo um gasto"
            )

        elif personalidade == "divertido":
            return (
                "Bora la! Olha o que eu faco: 🎯\n\n"
                "💸 Anoto seus gastos e ganhos\n"
                "📷 Leio fotos de notas e comprovantes\n"
                "🎤 Entendo audios com gastos\n"
                "📊 Organizo tudo em categorias\n\n"
                "Exemplos:\n"
                "- 'gastei 150 no mercado'\n"
                "- 'recebi 3k de salario 🤑'\n"
                "- Manda foto de nota fiscal\n"
                "- Manda audio falando um gasto"
            )

        else:  # amigavel
            return (
                "Posso te ajudar a organizar suas financas!\n\n"
                "O que eu faco:\n"
                "- Registro gastos e receitas\n"
                "- Entendo fotos de notas e comprovantes\n"
                "- Transcrevo audios com gastos\n"
                "- Organizo por categorias\n\n"
                "Exemplos:\n"
                "- 'Gastei 150 no mercado'\n"
                "- 'Recebi 3000 de salario'\n"
                "- Envie foto de uma nota fiscal\n"
                "- Envie audio falando um gasto"
            )


# Instância global
personality_agent = PersonalityAgent()
