"""
Learning Agent - Agente que aprende padrões do usuário.

Responsabilidades:
- Salvar padrões após transações confirmadas
- Sugerir categorias baseado em histórico
- Aumentar confiança conforme uso repetido
- Determinar se deve auto-confirmar
"""

import unicodedata
from typing import Optional, Dict, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.services.agents.base_agent import (
    BaseAgent,
    AgentContext,
    AgentResponse,
    IntentType
)


class LearningAgent(BaseAgent):
    """
    Agente de aprendizado - aprende padrões do usuário ao longo do tempo.

    Funcionalidades:
    - Aprende mapeamento descrição -> categoria
    - Calcula confiança baseada em ocorrências
    - Sugere categorias para novas transações
    """

    name = "learning"
    description = "Aprende padrões do usuário"

    # Incremento de confiança por ocorrência
    CONFIANCA_INICIAL = 0.5
    CONFIANCA_INCREMENT = 0.1
    CONFIANCA_MAX = 0.95

    # Mínimo de ocorrências para alta confiança
    MIN_OCORRENCIAS_ALTA_CONFIANCA = 3

    def can_handle(self, context: AgentContext) -> bool:
        """Learning Agent é chamado internamente, não diretamente"""
        return False

    async def process(self, context: AgentContext) -> AgentResponse:
        """Não processa diretamente - usa métodos específicos"""
        return AgentResponse(
            sucesso=False,
            mensagem="Learning Agent não processa mensagens diretamente"
        )

    def normalizar_texto(self, texto: str) -> str:
        """
        Normaliza texto para comparação.
        Remove acentos, converte para lowercase, remove espaços extras.
        """
        # Remove acentos
        texto = unicodedata.normalize('NFKD', texto)
        texto = texto.encode('ASCII', 'ignore').decode('ASCII')
        # Lowercase e remove espaços extras
        return ' '.join(texto.lower().split())

    def extrair_palavras_chave(self, descricao: str) -> str:
        """
        Extrai palavras-chave significativas da descrição.
        Remove stopwords e mantém palavras relevantes.
        """
        stopwords = {
            'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
            'um', 'uma', 'uns', 'umas', 'o', 'a', 'os', 'as', 'e', 'ou',
            'para', 'por', 'com', 'sem', 'que', 'se', 'ao', 'aos',
            'pagamento', 'paguei', 'gastei', 'comprei', 'recebi'
        }

        texto_norm = self.normalizar_texto(descricao)
        palavras = texto_norm.split()

        # Filtra stopwords e palavras muito curtas
        palavras_chave = [p for p in palavras if p not in stopwords and len(p) > 2]

        # Retorna as primeiras 3 palavras significativas
        return ' '.join(palavras_chave[:3])

    async def registrar_padrao(
        self,
        db: Session,
        usuario_id: int,
        descricao: str,
        categoria_id: int,
        tipo: str
    ) -> Dict:
        """
        Registra ou atualiza padrão após transação confirmada.

        Args:
            db: Sessão do banco
            usuario_id: ID do usuário
            descricao: Descrição da transação
            categoria_id: ID da categoria usada
            tipo: 'receita' ou 'despesa'

        Returns:
            Dict com info do padrão (novo ou atualizado)
        """
        from backend.models import UserPattern, TipoTransacao

        palavras_chave = self.extrair_palavras_chave(descricao)

        if not palavras_chave:
            return {"sucesso": False, "motivo": "Sem palavras-chave significativas"}

        tipo_enum = TipoTransacao.DESPESA if tipo == "despesa" else TipoTransacao.RECEITA

        # Busca padrão existente
        padrao_existente = db.query(UserPattern).filter(
            UserPattern.usuario_id == usuario_id,
            UserPattern.palavras_chave == palavras_chave,
            UserPattern.tipo == tipo_enum
        ).first()

        if padrao_existente:
            # Atualiza padrão existente
            padrao_existente.ocorrencias += 1
            padrao_existente.categoria_id = categoria_id  # Atualiza categoria se mudou

            # Aumenta confiança
            nova_confianca = min(
                padrao_existente.confianca + self.CONFIANCA_INCREMENT,
                self.CONFIANCA_MAX
            )
            padrao_existente.confianca = nova_confianca
            padrao_existente.atualizado_em = datetime.now(timezone.utc)

            db.commit()

            self.log(f"Padrão atualizado: '{palavras_chave}' -> confiança {nova_confianca:.2f}")

            return {
                "sucesso": True,
                "acao": "atualizado",
                "palavras_chave": palavras_chave,
                "ocorrencias": padrao_existente.ocorrencias,
                "confianca": nova_confianca
            }
        else:
            # Cria novo padrão
            novo_padrao = UserPattern(
                usuario_id=usuario_id,
                categoria_id=categoria_id,
                palavras_chave=palavras_chave,
                tipo=tipo_enum,
                ocorrencias=1,
                confianca=self.CONFIANCA_INICIAL
            )

            db.add(novo_padrao)
            db.commit()

            self.log(f"Novo padrão: '{palavras_chave}' -> categoria {categoria_id}")

            return {
                "sucesso": True,
                "acao": "criado",
                "palavras_chave": palavras_chave,
                "ocorrencias": 1,
                "confianca": self.CONFIANCA_INICIAL
            }

    async def buscar_padrao(
        self,
        db: Session,
        usuario_id: int,
        descricao: str,
        tipo: str
    ) -> Optional[Dict]:
        """
        Busca padrão correspondente à descrição.

        Args:
            db: Sessão do banco
            usuario_id: ID do usuário
            descricao: Descrição a buscar
            tipo: 'receita' ou 'despesa'

        Returns:
            Dict com dados do padrão ou None
        """
        from backend.models import UserPattern, TipoTransacao, Categoria

        palavras_chave = self.extrair_palavras_chave(descricao)

        if not palavras_chave:
            return None

        tipo_enum = TipoTransacao.DESPESA if tipo == "despesa" else TipoTransacao.RECEITA

        # Busca match exato primeiro
        padrao = db.query(UserPattern).filter(
            UserPattern.usuario_id == usuario_id,
            UserPattern.palavras_chave == palavras_chave,
            UserPattern.tipo == tipo_enum
        ).first()

        if padrao:
            categoria = db.query(Categoria).filter(Categoria.id == padrao.categoria_id).first()

            return {
                "encontrado": True,
                "categoria_id": padrao.categoria_id,
                "categoria_nome": categoria.nome if categoria else "Outros",
                "confianca": padrao.confianca,
                "ocorrencias": padrao.ocorrencias,
                "palavras_chave": padrao.palavras_chave
            }

        # Busca parcial (se alguma palavra-chave corresponde)
        palavras = palavras_chave.split()
        for palavra in palavras:
            padrao = db.query(UserPattern).filter(
                UserPattern.usuario_id == usuario_id,
                UserPattern.palavras_chave.ilike(f"%{palavra}%"),
                UserPattern.tipo == tipo_enum
            ).order_by(UserPattern.confianca.desc()).first()

            if padrao and padrao.confianca >= 0.6:
                categoria = db.query(Categoria).filter(Categoria.id == padrao.categoria_id).first()

                return {
                    "encontrado": True,
                    "match_parcial": True,
                    "categoria_id": padrao.categoria_id,
                    "categoria_nome": categoria.nome if categoria else "Outros",
                    "confianca": padrao.confianca * 0.8,  # Reduz confiança para match parcial
                    "ocorrencias": padrao.ocorrencias,
                    "palavras_chave": padrao.palavras_chave
                }

        return None

    async def obter_preferencias(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Obtém preferências do usuário do banco.

        Args:
            db: Sessão do banco
            usuario_id: ID do usuário

        Returns:
            Dict com preferências (usa defaults se não existir)
        """
        from backend.models import UserPreferences, PersonalidadeIA

        prefs = db.query(UserPreferences).filter(
            UserPreferences.usuario_id == usuario_id
        ).first()

        if prefs:
            return {
                "personalidade": prefs.personalidade.value,
                "alertar_vencimentos": prefs.alertar_vencimentos,
                "dias_antes_vencimento": prefs.dias_antes_vencimento,
                "alertar_gastos_anomalos": prefs.alertar_gastos_anomalos,
                "limite_anomalia_percentual": prefs.limite_anomalia_percentual,
                "resumo_diario": prefs.resumo_diario,
                "resumo_semanal": prefs.resumo_semanal,
                "resumo_mensal": prefs.resumo_mensal,
                "horario_resumo": prefs.horario_resumo,
                "auto_confirmar_confianca": prefs.auto_confirmar_confianca
            }

        # Retorna defaults
        return {
            "personalidade": PersonalidadeIA.AMIGAVEL.value,
            "alertar_vencimentos": True,
            "dias_antes_vencimento": 3,
            "alertar_gastos_anomalos": True,
            "limite_anomalia_percentual": 30,
            "resumo_diario": False,
            "resumo_semanal": True,
            "resumo_mensal": True,
            "horario_resumo": "09:00",
            "auto_confirmar_confianca": 0.90
        }

    async def criar_preferencias_padrao(
        self,
        db: Session,
        usuario_id: int
    ) -> Dict:
        """
        Cria preferências padrão para um usuário.

        Args:
            db: Sessão do banco
            usuario_id: ID do usuário

        Returns:
            Dict com preferências criadas
        """
        from backend.models import UserPreferences

        # Verifica se já existe
        existente = db.query(UserPreferences).filter(
            UserPreferences.usuario_id == usuario_id
        ).first()

        if existente:
            return await self.obter_preferencias(db, usuario_id)

        # Cria novo
        prefs = UserPreferences(usuario_id=usuario_id)
        db.add(prefs)
        db.commit()

        self.log(f"Preferências criadas para usuário {usuario_id}")

        return await self.obter_preferencias(db, usuario_id)

    async def atualizar_preferencias(
        self,
        db: Session,
        usuario_id: int,
        dados: Dict
    ) -> Dict:
        """
        Atualiza preferências do usuário.

        Args:
            db: Sessão do banco
            usuario_id: ID do usuário
            dados: Dict com campos a atualizar

        Returns:
            Dict com preferências atualizadas
        """
        from backend.models import UserPreferences, PersonalidadeIA

        prefs = db.query(UserPreferences).filter(
            UserPreferences.usuario_id == usuario_id
        ).first()

        if not prefs:
            # Cria se não existir
            prefs = UserPreferences(usuario_id=usuario_id)
            db.add(prefs)

        # Atualiza campos
        campos_permitidos = [
            'personalidade', 'alertar_vencimentos', 'dias_antes_vencimento',
            'alertar_gastos_anomalos', 'limite_anomalia_percentual',
            'resumo_diario', 'resumo_semanal', 'resumo_mensal',
            'horario_resumo', 'auto_confirmar_confianca'
        ]

        for campo in campos_permitidos:
            if campo in dados:
                valor = dados[campo]

                # Converte personalidade para enum
                if campo == 'personalidade':
                    valor = PersonalidadeIA(valor)

                setattr(prefs, campo, valor)

        prefs.atualizado_em = datetime.now(timezone.utc)
        db.commit()

        self.log(f"Preferências atualizadas para usuário {usuario_id}")

        return await self.obter_preferencias(db, usuario_id)

    def deve_auto_confirmar(
        self,
        confianca: float,
        limite_confianca: float = 0.90
    ) -> bool:
        """
        Determina se transação deve ser auto-confirmada.

        Args:
            confianca: Confiança calculada
            limite_confianca: Limite mínimo para auto-confirmar

        Returns:
            True se deve auto-confirmar
        """
        return confianca >= limite_confianca

    async def listar_padroes_usuario(
        self,
        db: Session,
        usuario_id: int,
        limite: int = 20
    ) -> List[Dict]:
        """
        Lista padrões aprendidos do usuário.

        Args:
            db: Sessão do banco
            usuario_id: ID do usuário
            limite: Máximo de registros

        Returns:
            Lista de padrões
        """
        from backend.models import UserPattern, Categoria

        padroes = db.query(UserPattern).filter(
            UserPattern.usuario_id == usuario_id
        ).order_by(UserPattern.ocorrencias.desc()).limit(limite).all()

        resultado = []
        for p in padroes:
            categoria = db.query(Categoria).filter(Categoria.id == p.categoria_id).first()

            resultado.append({
                "id": p.id,
                "palavras_chave": p.palavras_chave,
                "tipo": p.tipo.value,
                "categoria_id": p.categoria_id,
                "categoria_nome": categoria.nome if categoria else "Outros",
                "ocorrencias": p.ocorrencias,
                "confianca": p.confianca,
                "criado_em": p.criado_em.isoformat(),
                "atualizado_em": p.atualizado_em.isoformat()
            })

        return resultado


# Instância global
learning_agent = LearningAgent()
