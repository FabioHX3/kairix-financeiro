"""
Módulo de rotas do WhatsApp.

Este módulo contém:
- webhook.py: Endpoint principal do webhook
- handlers.py: Handlers para processamento de mensagens
- formatters.py: Funções de formatação de respostas
- utils.py: Funções utilitárias
"""

from backend.routes.whatsapp.webhook import router

__all__ = ["router"]
