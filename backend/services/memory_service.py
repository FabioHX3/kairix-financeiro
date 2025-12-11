"""
Memory Service - Gerenciamento de memória do sistema Kairix.

Três níveis de memória:
- Curta (Redis, TTL 24h): Conversa ativa, contexto pendente
- Média (Redis, TTL 30d): Padrões do usuário, preferências
- Longa (PostgreSQL): Transações, histórico permanente
"""

import json
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Optional, Any
from dataclasses import asdict

from backend.config import settings


class MemoryService:
    """Serviço unificado de memória"""

    # TTLs padrão
    TTL_CURTA = 60 * 60 * 24           # 24 horas
    TTL_MEDIA = 60 * 60 * 24 * 30      # 30 dias
    TTL_CONFIRMACAO = 60 * 5           # 5 minutos para confirmação

    # Prefixos de chaves Redis
    PREFIX_CONVERSA = "kairix:conversa:"
    PREFIX_PENDENTE = "kairix:pendente:"
    PREFIX_PADROES = "kairix:padroes:"
    PREFIX_PREFERENCIAS = "kairix:prefs:"

    def __init__(self):
        self._redis: Optional[redis.Redis] = None

    async def connect(self):
        """Conecta ao Redis"""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
        return self._redis

    async def close(self):
        """Fecha conexão com Redis"""
        if self._redis:
            await self._redis.close()
            self._redis = None

    # ==================== MEMÓRIA CURTA (Conversa) ====================

    async def salvar_contexto_conversa(
        self,
        telefone: str,
        mensagem: str,
        resposta: str,
        dados_extras: dict = None
    ):
        """
        Salva contexto da conversa atual.
        Mantém histórico das últimas N mensagens.
        """
        r = await self.connect()
        key = f"{self.PREFIX_CONVERSA}{telefone}"

        # Recupera histórico existente
        historico = await self.obter_historico_conversa(telefone)

        # Adiciona nova interação
        historico.append({
            "timestamp": datetime.utcnow().isoformat(),
            "usuario": mensagem,
            "assistente": resposta,
            "dados": dados_extras or {}
        })

        # Mantém apenas últimas 10 interações
        historico = historico[-10:]

        await r.setex(key, self.TTL_CURTA, json.dumps(historico))

    async def obter_historico_conversa(self, telefone: str) -> list:
        """Retorna histórico da conversa"""
        r = await self.connect()
        key = f"{self.PREFIX_CONVERSA}{telefone}"

        data = await r.get(key)
        if data:
            return json.loads(data)
        return []

    async def limpar_conversa(self, telefone: str):
        """Limpa histórico da conversa"""
        r = await self.connect()
        key = f"{self.PREFIX_CONVERSA}{telefone}"
        await r.delete(key)

    # ==================== AÇÕES PENDENTES (Confirmação) ====================

    async def salvar_acao_pendente(
        self,
        telefone: str,
        tipo_acao: str,
        dados: dict,
        ttl: int = None
    ):
        """
        Salva ação aguardando confirmação do usuário.
        Ex: transação extraída aguardando "sim" ou "não"
        """
        r = await self.connect()
        key = f"{self.PREFIX_PENDENTE}{telefone}"

        acao = {
            "tipo": tipo_acao,
            "dados": dados,
            "criado_em": datetime.utcnow().isoformat()
        }

        await r.setex(key, ttl or self.TTL_CONFIRMACAO, json.dumps(acao))

    async def obter_acao_pendente(self, telefone: str) -> Optional[dict]:
        """Retorna ação pendente se existir"""
        r = await self.connect()
        key = f"{self.PREFIX_PENDENTE}{telefone}"

        data = await r.get(key)
        if data:
            return json.loads(data)
        return None

    async def limpar_acao_pendente(self, telefone: str):
        """Remove ação pendente (após confirmação/cancelamento)"""
        r = await self.connect()
        key = f"{self.PREFIX_PENDENTE}{telefone}"
        await r.delete(key)

    # ==================== MEMÓRIA MÉDIA (Padrões) ====================

    async def salvar_padrao_usuario(
        self,
        usuario_id: int,
        descricao: str,
        categoria_id: int,
        tipo: str
    ):
        """
        Salva padrão aprendido do usuário.
        Ex: "mercado" -> categoria "Alimentação"
        """
        r = await self.connect()
        key = f"{self.PREFIX_PADROES}{usuario_id}"

        # Recupera padrões existentes
        padroes = await self.obter_padroes_usuario(usuario_id)

        # Normaliza descrição para busca
        desc_norm = self._normalizar(descricao)

        # Atualiza ou adiciona padrão
        encontrado = False
        for p in padroes:
            if p["descricao_norm"] == desc_norm:
                p["categoria_id"] = categoria_id
                p["tipo"] = tipo
                p["ocorrencias"] = p.get("ocorrencias", 0) + 1
                p["ultima_vez"] = datetime.utcnow().isoformat()
                encontrado = True
                break

        if not encontrado:
            padroes.append({
                "descricao": descricao,
                "descricao_norm": desc_norm,
                "categoria_id": categoria_id,
                "tipo": tipo,
                "ocorrencias": 1,
                "criado_em": datetime.utcnow().isoformat(),
                "ultima_vez": datetime.utcnow().isoformat()
            })

        await r.setex(key, self.TTL_MEDIA, json.dumps(padroes))

    async def obter_padroes_usuario(self, usuario_id: int) -> list:
        """Retorna padrões aprendidos do usuário"""
        r = await self.connect()
        key = f"{self.PREFIX_PADROES}{usuario_id}"

        data = await r.get(key)
        if data:
            return json.loads(data)
        return []

    async def buscar_padrao(
        self,
        usuario_id: int,
        descricao: str
    ) -> Optional[dict]:
        """Busca padrão correspondente à descrição"""
        padroes = await self.obter_padroes_usuario(usuario_id)
        desc_norm = self._normalizar(descricao)

        # Busca por match exato ou parcial
        for p in padroes:
            if p["descricao_norm"] in desc_norm or desc_norm in p["descricao_norm"]:
                return p

        return None

    # ==================== PREFERÊNCIAS DO USUÁRIO ====================

    async def salvar_preferencias(
        self,
        usuario_id: int,
        preferencias: dict
    ):
        """Salva preferências do usuário"""
        r = await self.connect()
        key = f"{self.PREFIX_PREFERENCIAS}{usuario_id}"

        # Merge com preferências existentes
        prefs_atuais = await self.obter_preferencias(usuario_id)
        prefs_atuais.update(preferencias)

        await r.setex(key, self.TTL_MEDIA, json.dumps(prefs_atuais))

    async def obter_preferencias(self, usuario_id: int) -> dict:
        """Retorna preferências do usuário"""
        r = await self.connect()
        key = f"{self.PREFIX_PREFERENCIAS}{usuario_id}"

        data = await r.get(key)
        if data:
            return json.loads(data)

        # Preferências padrão
        return {
            "personalidade": "amigavel",  # formal, amigavel, divertido
            "alertar_vencimentos": True,
            "alertar_gastos_anomalos": True,
            "resumo_diario": False,
            "resumo_semanal": True,
            "auto_confirmar_confianca": 0.90  # Auto-confirma se confiança >= 90%
        }

    # ==================== UTILITÁRIOS ====================

    def _normalizar(self, texto: str) -> str:
        """Normaliza texto para comparação"""
        import unicodedata
        # Remove acentos
        texto = unicodedata.normalize('NFKD', texto)
        texto = texto.encode('ASCII', 'ignore').decode('ASCII')
        # Lowercase e remove espaços extras
        return ' '.join(texto.lower().split())


# Singleton
memory_service = MemoryService()
