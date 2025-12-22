# Auditoria Backend - Kairix Financeiro

**Data:** 2025-12-16
**Versão:** 1.0

---

## Resumo

| Severidade | Quantidade |
|------------|------------|
| Crítico | 2 |
| Importante | 5 |
| Melhoria | 3 |

---

## CRÍTICO

### 1. Endpoint WhatsApp sem autenticação

**Arquivo:** `backend/routes/whatsapp.py:941`

**Problema:** O endpoint `/api/whatsapp/enviar` permite enviar mensagens para qualquer número **SEM autenticação**. Pode ser abusado para spam ou phishing.

```python
# ATUAL (vulnerável)
@router.post("/enviar")
async def enviar_mensagem_manual(numero: str, mensagem: str):
    resultado = await whatsapp_service.enviar_mensagem(numero, mensagem)
    return resultado
```

**Correção:**
```python
@router.post("/enviar")
async def enviar_mensagem_manual(
    numero: str,
    mensagem: str,
    usuario: Usuario = Depends(obter_usuario_atual)  # Adicionar autenticação
):
    resultado = await whatsapp_service.enviar_mensagem(numero, mensagem)
    return resultado
```

---

### 2. Dados de agendamentos em memória

**Arquivo:** `backend/routes/agendamentos.py:32`

**Problema:** Os agendamentos são armazenados em um dicionário Python (`agendamentos_memoria = {}`). Quando o servidor reinicia, todos os dados são perdidos.

```python
# ATUAL (dados perdidos ao reiniciar)
agendamentos_memoria = {}
```

**Correção:** Criar modelo no banco de dados e migrar para PostgreSQL.

---

## IMPORTANTE

### 3. HTTP síncrono em código async

**Arquivos:**
- `backend/services/llm.py`
- `backend/routes/whatsapp.py`

**Problema:** Usa biblioteca `requests` (síncrona) dentro de funções async. Isso bloqueia o event loop e prejudica a performance.

```python
# ATUAL (bloqueia event loop)
import requests
response = requests.post(url, headers=headers, json=payload, timeout=30)
```

**Correção:**
```python
# CORRETO (async)
import httpx

async with httpx.AsyncClient() as client:
    response = await client.post(url, headers=headers, json=payload, timeout=30)
```

---

### 4. Inconsistência de datetime

**Arquivos afetados:**
- `datetime.utcnow()`: 10 arquivos
- `datetime.now()`: 9 arquivos

**Problema:** Mistura de `utcnow()` e `now()` pode causar bugs de timezone, especialmente em comparações de datas.

**Correção:** Padronizar para usar timezone-aware:
```python
from datetime import datetime, timezone

# Sempre usar:
datetime.now(timezone.utc)
```

---

### 5. Print em vez de Logger

**Arquivos afetados:**
- `backend/main.py`: 5 prints
- `backend/routes/whatsapp.py`: 24 prints
- `backend/services/llm.py`: 26 prints
- `backend/services/whatsapp.py`: 8 prints
- Outros: 6 prints

**Total:** 69 `print()` vs 30 `logger`

**Problema:** `print()` não é estruturado, não tem níveis de severidade, e não pode ser facilmente filtrado ou redirecionado.

**Correção:**
```python
import logging
logger = logging.getLogger(__name__)

# Em vez de:
print("[Audio] Baixando áudio...")

# Usar:
logger.info("[Audio] Baixando áudio...")
```

---

### 6. Código duplicado - fmt_valor()

**Arquivos:**
- `backend/services/agents/consultant_agent.py:308`
- `backend/services/agents/proactive_agent.py:158`
- `backend/services/agents/proactive_agent.py:324`
- `backend/services/agents/proactive_agent.py:506`

**Problema:** A mesma função está definida 4 vezes em diferentes arquivos.

```python
def fmt_valor(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
```

**Correção:** Centralizar em um arquivo de utilitários:
```python
# backend/utils/formatters.py
def fmt_valor(v: float) -> str:
    """Formata valor monetário para padrão brasileiro."""
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
```

---

### 7. Import não utilizado

**Arquivo:** `backend/services/memory_service.py:14`

```python
from dataclasses import asdict  # Nunca usado no arquivo
```

**Correção:** Remover o import.

---

## MELHORIAS

### 8. Endpoints de teste expostos

**Arquivo:** `backend/routes/whatsapp.py`

**Endpoints sem autenticação:**
- `GET /api/whatsapp/status`
- `POST /api/whatsapp/teste`

**Recomendação:** Adicionar autenticação ou remover em produção.

---

### 9. Falta de type hints

**Problema:** Alguns métodos não têm tipagem de retorno definida.

**Exemplo:**
```python
# Atual
def _extracao_basica(self, texto: str, categorias_disponiveis: list):

# Melhor
def _extracao_basica(self, texto: str, categorias_disponiveis: list) -> Dict[str, Any]:
```

---

### 10. Try/except genérico

**Arquivo:** `backend/services/llm.py`

**Problema:** Uso de `except:` sem tipo específico esconde erros.

```python
# Atual (esconde erros)
try:
    return datetime.strptime(data_relativa, "%Y-%m-%d")
except:
    return datetime.now()
```

**Correção:**
```python
try:
    return datetime.strptime(data_relativa, "%Y-%m-%d")
except ValueError:
    return datetime.now()
```

---

## Pontos Positivos

| Item | Descrição |
|------|-----------|
| Estrutura de pastas | Organização clara: routes, services, models, core |
| Separação de concerns | Agentes bem separados por responsabilidade |
| Autenticação JWT | Implementada corretamente nas rotas protegidas |
| Soft delete | Membros de família usam soft delete corretamente |
| Schemas Pydantic | Validação de entrada bem definida |
| Worker arq | Migração bem feita, 100% async nativo |
| Padrões de código | Nomenclatura consistente em português |

---

## Prioridade de Correção

1. **Imediato:** Proteger endpoint `/api/whatsapp/enviar`
2. **Curto prazo:** Migrar agendamentos para banco
3. **Médio prazo:** Substituir `requests` por `httpx`
4. **Contínuo:** Padronizar logging e datetime

---

## Arquivos que precisam de atenção

```
backend/
├── routes/
│   ├── whatsapp.py      # Endpoints sem auth, prints
│   └── agendamentos.py  # Dados em memória
├── services/
│   ├── llm.py           # requests sync, prints
│   ├── memory_service.py # Import não usado
│   └── agents/
│       ├── consultant_agent.py  # fmt_valor duplicado
│       └── proactive_agent.py   # fmt_valor duplicado (3x)
└── models/
    └── models.py        # datetime.utcnow misturado
```
