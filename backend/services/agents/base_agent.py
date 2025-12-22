"""
Base Agent - Classe abstrata para todos os agentes do sistema Kairix.

Cada agente especializado herda desta classe e implementa sua lógica específica.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Tipos de intenção detectados pelo Gateway"""
    REGISTRAR = "registrar"           # Registrar transação
    CONSULTAR = "consultar"           # Consultar saldo, gastos, etc
    LISTAR = "listar"                 # Listar transações
    EDITAR = "editar"                 # Editar transação existente
    DELETAR = "deletar"               # Deletar transação
    CONFIGURAR = "configurar"         # Configurar preferências
    AJUDA = "ajuda"                   # Pedir ajuda
    SAUDACAO = "saudacao"             # Saudação/conversa
    CONFIRMAR = "confirmar"           # Confirmar ação pendente
    CANCELAR = "cancelar"             # Cancelar ação pendente
    DESCONHECIDO = "desconhecido"     # Não identificado


class OrigemMensagem(str, Enum):
    """Origem da mensagem do usuário"""
    WHATSAPP_TEXTO = "whatsapp_texto"
    WHATSAPP_AUDIO = "whatsapp_audio"
    WHATSAPP_IMAGEM = "whatsapp_imagem"
    WEB = "web"
    API = "api"


@dataclass
class AgentContext:
    """Contexto compartilhado entre agentes"""
    usuario_id: int
    telefone: str
    mensagem_original: str
    origem: OrigemMensagem
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Localização do usuário
    timezone: str = "America/Sao_Paulo"  # Default, será preenchido do perfil

    # Dados extraídos/processados
    intent: Optional[IntentType] = None
    dados_extraidos: dict = field(default_factory=dict)

    # Estado da conversa
    aguardando_confirmacao: bool = False
    acao_pendente: Optional[dict] = None

    # Mídia (se houver)
    media_url: Optional[str] = None
    media_type: Optional[str] = None

    # Metadados
    confianca_ia: float = 0.0
    historico_conversa: list = field(default_factory=list)


@dataclass
class AgentResponse:
    """Resposta padronizada de qualquer agente"""
    sucesso: bool
    mensagem: str
    dados: dict = field(default_factory=dict)

    # Controle de fluxo
    requer_confirmacao: bool = False
    acao_pendente: Optional[dict] = None

    # Próximo agente (se precisar encadear)
    proximo_agente: Optional[str] = None

    # Metadados
    confianca: float = 1.0
    codigo_transacao: Optional[str] = None


class BaseAgent(ABC):
    """
    Classe base abstrata para todos os agentes.

    Cada agente deve implementar:
    - process(): Lógica principal de processamento
    - can_handle(): Verifica se pode processar o contexto
    """

    name: str = "base"
    description: str = "Agente base"

    def __init__(self, db_session=None, redis_client=None):
        self.db = db_session
        self.redis = redis_client

    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResponse:
        """
        Processa o contexto e retorna uma resposta.

        Args:
            context: Contexto com dados do usuário e mensagem

        Returns:
            AgentResponse com resultado do processamento
        """
        pass

    @abstractmethod
    def can_handle(self, context: AgentContext) -> bool:
        """
        Verifica se este agente pode processar o contexto.

        Args:
            context: Contexto a ser verificado

        Returns:
            True se pode processar, False caso contrário
        """
        pass

    def log(self, message: str, level: str = "info"):
        """Log padronizado com nome do agente"""
        prefix = f"[{self.name.upper()}]"
        log_func = getattr(logger, level, logger.info)
        log_func(f"{prefix} {message}")
