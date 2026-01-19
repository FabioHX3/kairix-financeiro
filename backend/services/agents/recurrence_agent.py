"""
Recurrence Agent - Detecta e gerencia transacoes recorrentes.

Responsabilidades:
- Detectar padroes de recorrencia no historico
- Prever proximas ocorrencias
- Sugerir criacao de recorrencia
- Gerar contas agendadas
"""

import unicodedata
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import ClassVar

from sqlalchemy.orm import Session

from backend.services.agents.base_agent import AgentContext, AgentResponse, BaseAgent


class RecurrenceAgent(BaseAgent):
    """
    Agente de recorrencias - detecta e gerencia transacoes recorrentes.

    Algoritmo de deteccao:
    1. Agrupa transacoes por descricao similar
    2. Analisa intervalos entre ocorrencias
    3. Detecta frequencia (mensal, semanal, etc)
    4. Calcula confianca baseada em regularidade
    """

    name = "recurrence"
    description = "Detecta transacoes recorrentes"

    # Minimo de ocorrencias para considerar recorrencia
    MIN_OCORRENCIAS = 2

    # Tolerancia de dias para considerar "mesmo dia do mes"
    TOLERANCIA_DIAS = 3

    # Tolerancia de valor (%) para considerar "mesmo valor"
    TOLERANCIA_VALOR = 0.15  # 15%

    # Intervalos de frequencia em dias
    FREQUENCIAS: ClassVar[dict[str, tuple[int, int]]] = {
        "diaria": (1, 1),
        "semanal": (6, 8),
        "quinzenal": (13, 17),
        "mensal": (28, 33),
        "bimestral": (58, 65),
        "trimestral": (88, 95),
        "semestral": (175, 190),
        "anual": (360, 370)
    }

    def can_handle(self, context: AgentContext) -> bool:
        """Recurrence Agent e chamado internamente"""
        return False

    async def process(self, context: AgentContext) -> AgentResponse:
        """Nao processa diretamente"""
        return AgentResponse(
            sucesso=False,
            mensagem="Recurrence Agent nao processa mensagens diretamente"
        )

    def normalizar_descricao(self, texto: str) -> str:
        """Normaliza descricao para comparacao"""
        texto = unicodedata.normalize('NFKD', texto)
        texto = texto.encode('ASCII', 'ignore').decode('ASCII')
        return ' '.join(texto.lower().split())

    async def analisar_historico(
        self,
        db: Session,
        usuario_id: int,
        dias: int = 180
    ) -> list[dict]:
        """
        Analisa historico de transacoes e detecta possiveis recorrencias.

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            dias: Quantidade de dias para analisar

        Returns:
            Lista de recorrencias detectadas
        """
        from backend.models import Transacao

        data_inicio = datetime.now(UTC) - timedelta(days=dias)

        # Busca transacoes do periodo
        transacoes = db.query(Transacao).filter(
            Transacao.usuario_id == usuario_id,
            Transacao.data_transacao >= data_inicio,
            Transacao.status != 'cancelada'
        ).order_by(Transacao.data_transacao).all()

        if len(transacoes) < self.MIN_OCORRENCIAS:
            return []

        # Agrupa por descricao normalizada
        grupos = defaultdict(list)
        for t in transacoes:
            desc_norm = self.normalizar_descricao(t.descricao or "")
            if desc_norm:
                grupos[desc_norm].append(t)

        recorrencias_detectadas = []

        for desc_norm, trans_lista in grupos.items():
            if len(trans_lista) < self.MIN_OCORRENCIAS:
                continue

            # Analisa padrao
            padrao = self._analisar_padrao(trans_lista)

            if padrao and padrao["confianca"] >= 0.5:
                recorrencias_detectadas.append({
                    "descricao_padrao": trans_lista[0].descricao,
                    "descricao_normalizada": desc_norm,
                    "tipo": trans_lista[0].tipo.value,
                    "categoria_id": trans_lista[0].categoria_id,
                    **padrao
                })

        # Ordena por confianca
        recorrencias_detectadas.sort(key=lambda x: x["confianca"], reverse=True)

        return recorrencias_detectadas

    def _analisar_padrao(self, transacoes: list) -> dict | None:
        """
        Analisa lista de transacoes e detecta padrao de recorrencia.

        Returns:
            Dict com frequencia, valor_medio, dia_mes, confianca, etc.
        """
        if len(transacoes) < self.MIN_OCORRENCIAS:
            return None

        # Calcula valores
        valores = [t.valor for t in transacoes]
        valor_medio = sum(valores) / len(valores)
        valor_min = min(valores)
        valor_max = max(valores)

        # Verifica variacao de valor
        variacao_valor = (valor_max - valor_min) / valor_medio if valor_medio > 0 else 0

        # Calcula intervalos entre transacoes
        datas = sorted([t.data_transacao for t in transacoes])
        intervalos = []
        for i in range(1, len(datas)):
            delta = (datas[i] - datas[i-1]).days
            if delta > 0:
                intervalos.append(delta)

        if not intervalos:
            return None

        intervalo_medio = sum(intervalos) / len(intervalos)

        # Detecta frequencia
        frequencia = self._detectar_frequencia(intervalo_medio)

        if not frequencia:
            return None

        # Analisa dia do mes (para mensais)
        dias_mes = [t.data_transacao.day for t in transacoes]
        dia_mais_comum = max(set(dias_mes), key=dias_mes.count)
        dias_no_comum = dias_mes.count(dia_mais_comum)
        regularidade_dia = dias_no_comum / len(dias_mes)

        # Analisa dia da semana (para semanais)
        dias_semana = [t.data_transacao.weekday() for t in transacoes]
        dia_semana_comum = max(set(dias_semana), key=dias_semana.count)

        # Calcula confianca
        confianca = self._calcular_confianca(
            ocorrencias=len(transacoes),
            variacao_valor=variacao_valor,
            regularidade_dia=regularidade_dia,
            intervalos=intervalos,
            intervalo_esperado=self._intervalo_esperado(frequencia)
        )

        # Calcula proxima esperada
        ultima_data = max(datas)
        proxima = self._calcular_proxima_ocorrencia(
            ultima_data, frequencia, dia_mais_comum
        )

        return {
            "frequencia": frequencia,
            "valor_medio": round(valor_medio, 2),
            "valor_minimo": round(valor_min, 2),
            "valor_maximo": round(valor_max, 2),
            "dia_mes": dia_mais_comum if frequencia == "mensal" else None,
            "dia_semana": dia_semana_comum if frequencia == "semanal" else None,
            "ocorrencias": len(transacoes),
            "ultima_ocorrencia": ultima_data,
            "proxima_esperada": proxima,
            "confianca": round(confianca, 2),
            "regularidade_dia": round(regularidade_dia, 2)
        }

    def _detectar_frequencia(self, intervalo_medio: float) -> str | None:
        """Detecta frequencia baseada no intervalo medio"""
        for freq, (min_dias, max_dias) in self.FREQUENCIAS.items():
            if min_dias <= intervalo_medio <= max_dias:
                return freq
        return None

    def _intervalo_esperado(self, frequencia: str) -> int:
        """Retorna intervalo esperado para frequencia"""
        intervalos = {
            "diaria": 1,
            "semanal": 7,
            "quinzenal": 15,
            "mensal": 30,
            "bimestral": 60,
            "trimestral": 90,
            "semestral": 180,
            "anual": 365
        }
        return intervalos.get(frequencia, 30)

    def _calcular_confianca(
        self,
        ocorrencias: int,
        variacao_valor: float,
        regularidade_dia: float,
        intervalos: list[int],
        intervalo_esperado: int
    ) -> float:
        """
        Calcula confianca da deteccao de recorrencia.

        Fatores:
        - Numero de ocorrencias
        - Variacao de valor
        - Regularidade do dia
        - Regularidade do intervalo
        """
        # Base: quanto mais ocorrencias, mais confiavel
        conf_ocorrencias = min(ocorrencias / 5, 1.0) * 0.3

        # Variacao de valor: quanto menor, mais confiavel
        conf_valor = max(0, 1 - variacao_valor) * 0.2

        # Regularidade do dia
        conf_dia = regularidade_dia * 0.25

        # Regularidade do intervalo
        if intervalos:
            desvios = [abs(i - intervalo_esperado) for i in intervalos]
            desvio_medio = sum(desvios) / len(desvios)
            conf_intervalo = max(0, 1 - (desvio_medio / intervalo_esperado)) * 0.25
        else:
            conf_intervalo = 0

        return conf_ocorrencias + conf_valor + conf_dia + conf_intervalo

    def _calcular_proxima_ocorrencia(
        self,
        ultima: datetime,
        frequencia: str,
        dia_mes: int | None = None
    ) -> datetime:
        """Calcula proxima data esperada"""
        if frequencia == "diaria":
            return ultima + timedelta(days=1)
        elif frequencia == "semanal":
            return ultima + timedelta(days=7)
        elif frequencia == "quinzenal":
            return ultima + timedelta(days=15)
        elif frequencia == "mensal":
            # Proximo mes, mesmo dia
            proximo_mes = ultima.month + 1
            ano = ultima.year
            if proximo_mes > 12:
                proximo_mes = 1
                ano += 1
            dia = min(dia_mes or ultima.day, 28)  # Evita problemas com meses curtos
            return datetime(ano, proximo_mes, dia)
        elif frequencia == "bimestral":
            proximo_mes = ultima.month + 2
            ano = ultima.year
            while proximo_mes > 12:
                proximo_mes -= 12
                ano += 1
            return datetime(ano, proximo_mes, min(dia_mes or ultima.day, 28))
        elif frequencia == "trimestral":
            return ultima + timedelta(days=90)
        elif frequencia == "semestral":
            return ultima + timedelta(days=180)
        elif frequencia == "anual":
            return datetime(ultima.year + 1, ultima.month, ultima.day)
        else:
            return ultima + timedelta(days=30)

    async def registrar_recorrencia(
        self,
        db: Session,
        usuario_id: int,
        dados: dict
    ) -> dict:
        """
        Registra uma recorrencia detectada no banco.

        Args:
            db: Sessao do banco
            usuario_id: ID do usuario
            dados: Dados da recorrencia

        Returns:
            Dict com recorrencia criada
        """
        from backend.models import FrequenciaRecorrencia, RecurringTransaction, TipoTransacao

        # Verifica se ja existe
        existente = db.query(RecurringTransaction).filter(
            RecurringTransaction.usuario_id == usuario_id,
            RecurringTransaction.descricao_padrao == dados["descricao_padrao"]
        ).first()

        if existente:
            # Atualiza existente
            existente.valor_medio = dados["valor_medio"]
            existente.valor_minimo = dados.get("valor_minimo")
            existente.valor_maximo = dados.get("valor_maximo")
            existente.ocorrencias = dados["ocorrencias"]
            existente.ultima_ocorrencia = dados.get("ultima_ocorrencia")
            existente.proxima_esperada = dados.get("proxima_esperada")
            existente.confianca_deteccao = dados["confianca"]
            existente.atualizado_em = datetime.now(UTC)

            db.commit()

            return {
                "id": existente.id,
                "acao": "atualizada",
                "descricao": existente.descricao_padrao
            }

        # Cria nova
        tipo = TipoTransacao.DESPESA if dados["tipo"] == "despesa" else TipoTransacao.RECEITA
        freq = FrequenciaRecorrencia(dados["frequencia"])

        recorrencia = RecurringTransaction(
            usuario_id=usuario_id,
            categoria_id=dados.get("categoria_id"),
            descricao_padrao=dados["descricao_padrao"],
            tipo=tipo,
            valor_medio=dados["valor_medio"],
            valor_minimo=dados.get("valor_minimo"),
            valor_maximo=dados.get("valor_maximo"),
            frequencia=freq,
            dia_mes=dados.get("dia_mes"),
            dia_semana=dados.get("dia_semana"),
            ocorrencias=dados["ocorrencias"],
            ultima_ocorrencia=dados.get("ultima_ocorrencia"),
            proxima_esperada=dados.get("proxima_esperada"),
            confianca_deteccao=dados["confianca"],
            detectada_automaticamente=True
        )

        db.add(recorrencia)
        db.commit()
        db.refresh(recorrencia)

        self.log(f"Recorrencia criada: {recorrencia.descricao_padrao}")

        return {
            "id": recorrencia.id,
            "acao": "criada",
            "descricao": recorrencia.descricao_padrao
        }

    async def listar_recorrencias(
        self,
        db: Session,
        usuario_id: int,
        apenas_ativas: bool = True
    ) -> list[dict]:
        """Lista recorrencias do usuario"""
        from backend.models import Categoria, RecurringTransaction, StatusRecorrencia

        query = db.query(RecurringTransaction).filter(
            RecurringTransaction.usuario_id == usuario_id
        )

        if apenas_ativas:
            query = query.filter(RecurringTransaction.status == StatusRecorrencia.ATIVA)

        recorrencias = query.order_by(RecurringTransaction.proxima_esperada).all()

        resultado = []
        for r in recorrencias:
            categoria = db.query(Categoria).filter(Categoria.id == r.categoria_id).first()

            resultado.append({
                "id": r.id,
                "descricao": r.descricao_padrao,
                "tipo": r.tipo.value,
                "valor_medio": r.valor_medio,
                "frequencia": r.frequencia.value,
                "dia_mes": r.dia_mes,
                "categoria_nome": categoria.nome if categoria else None,
                "status": r.status.value,
                "ocorrencias": r.ocorrencias,
                "ultima_ocorrencia": r.ultima_ocorrencia.isoformat() if r.ultima_ocorrencia else None,
                "proxima_esperada": r.proxima_esperada.isoformat() if r.proxima_esperada else None,
                "confianca": r.confianca_deteccao,
                "auto_confirmar": r.auto_confirmar
            })

        return resultado

    async def obter_previsao_mes(
        self,
        db: Session,
        usuario_id: int,
        mes: int | None = None,
        ano: int | None = None
    ) -> dict:
        """
        Obtem previsao de gastos/receitas para o mes baseado em recorrencias.

        Returns:
            Dict com total_despesas, total_receitas, lista de itens
        """
        from backend.models import RecurringTransaction, StatusRecorrencia, TipoTransacao

        if mes is None:
            mes = datetime.now(UTC).month
        if ano is None:
            ano = datetime.now(UTC).year

        # Busca recorrencias ativas
        recorrencias = db.query(RecurringTransaction).filter(
            RecurringTransaction.usuario_id == usuario_id,
            RecurringTransaction.status == StatusRecorrencia.ATIVA
        ).all()

        previsoes = []
        total_despesas = 0
        total_receitas = 0

        for r in recorrencias:
            # Verifica se ocorre neste mes
            if self._ocorre_no_mes(r, mes, ano):
                previsoes.append({
                    "descricao": r.descricao_padrao,
                    "tipo": r.tipo.value,
                    "valor": r.valor_medio,
                    "dia": r.dia_mes or 15,  # Default dia 15
                    "frequencia": r.frequencia.value
                })

                if r.tipo == TipoTransacao.DESPESA:
                    total_despesas += r.valor_medio
                else:
                    total_receitas += r.valor_medio

        return {
            "mes": mes,
            "ano": ano,
            "total_despesas": round(total_despesas, 2),
            "total_receitas": round(total_receitas, 2),
            "saldo_previsto": round(total_receitas - total_despesas, 2),
            "itens": sorted(previsoes, key=lambda x: x["dia"])
        }

    def _ocorre_no_mes(self, recorrencia, mes: int, ano: int) -> bool:
        """Verifica se recorrencia ocorre no mes especificado"""
        freq = recorrencia.frequencia.value

        if freq in ["diaria", "semanal", "quinzenal", "mensal"]:
            return True

        if freq == "bimestral":
            # Verifica se mes e par/impar igual ao mes inicial
            if recorrencia.ultima_ocorrencia:
                return (mes - recorrencia.ultima_ocorrencia.month) % 2 == 0
            return True

        if freq == "trimestral":
            if recorrencia.ultima_ocorrencia:
                return (mes - recorrencia.ultima_ocorrencia.month) % 3 == 0
            return mes in [1, 4, 7, 10]

        if freq == "semestral":
            if recorrencia.ultima_ocorrencia:
                return (mes - recorrencia.ultima_ocorrencia.month) % 6 == 0
            return mes in [1, 7]

        if freq == "anual":
            if recorrencia.ultima_ocorrencia:
                return mes == recorrencia.ultima_ocorrencia.month
            return False

        return False

    async def verificar_nova_transacao(
        self,
        db: Session,
        usuario_id: int,
        descricao: str,
        valor: float,
        tipo: str
    ) -> dict | None:
        """
        Verifica se nova transacao corresponde a uma recorrencia existente.

        Returns:
            Dict com recorrencia correspondente ou None
        """
        from backend.models import RecurringTransaction, StatusRecorrencia, TipoTransacao

        desc_norm = self.normalizar_descricao(descricao)
        tipo_enum = TipoTransacao.DESPESA if tipo == "despesa" else TipoTransacao.RECEITA

        # Busca recorrencias ativas
        recorrencias = db.query(RecurringTransaction).filter(
            RecurringTransaction.usuario_id == usuario_id,
            RecurringTransaction.tipo == tipo_enum,
            RecurringTransaction.status == StatusRecorrencia.ATIVA
        ).all()

        for r in recorrencias:
            r_desc_norm = self.normalizar_descricao(r.descricao_padrao)

            # Verifica similaridade de descricao
            if r_desc_norm in desc_norm or desc_norm in r_desc_norm:
                # Verifica se valor esta dentro da tolerancia
                diff = abs(valor - r.valor_medio) / r.valor_medio if r.valor_medio > 0 else 0

                if diff <= self.TOLERANCIA_VALOR:
                    return {
                        "recorrencia_id": r.id,
                        "descricao": r.descricao_padrao,
                        "valor_esperado": r.valor_medio,
                        "frequencia": r.frequencia.value,
                        "auto_confirmar": r.auto_confirmar
                    }

        return None


# Instancia global
recurrence_agent = RecurrenceAgent()
