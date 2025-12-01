# Kairix Financeiro

Agente financeiro inteligente integrado ao WhatsApp com dashboard web.

## O que faz

- Registra receitas e despesas via WhatsApp (texto, áudio ou foto)
- IA categoriza automaticamente as transações
- Dashboard web com gráficos e relatórios
- Gestão familiar compartilhada

## Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy, LangChain
- **Banco**: PostgreSQL
- **IA**: OpenRouter / Ollama
- **WhatsApp**: Evolution API

## Instalação

```bash
# 1. Ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 2. Dependências
pip install -r requirements.txt

# 3. Banco de dados (PostgreSQL)
CREATE DATABASE kairix_financeiro;

# 4. Configurar .env (copiar de .env.example)

# 5. Rodar
python run.py
```

## Configuração (.env)

```env
# Banco
DATABASE_URL=postgresql://user:pass@localhost:5432/kairix_financeiro

# Segurança
SECRET_KEY=sua_chave_secreta

# IA (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MODEL=openai/gpt-3.5-turbo

# WhatsApp (Evolution API)
EVOLUTION_URL=http://localhost:8055
EVOLUTION_API_KEY=sua_key
EVOLUTION_INSTANCE=sua_instancia

# Whisper (áudio)
OPENAI_API_KEY=sk-xxx
```

## URLs

- **Web**: http://localhost:8014
- **API Docs**: http://localhost:8014/docs
- **Webhook**: http://localhost:8014/api/whatsapp/webhook

## Estrutura

```
kairix_financeiro/
├── backend/
│   ├── main.py           # FastAPI app
│   ├── database.py       # Modelos
│   ├── llm_service.py    # IA
│   ├── rotas_*.py        # Endpoints
│   └── schemas.py        # Validação
├── frontend/
│   ├── templates/        # HTML
│   └── static/           # CSS, JS, assets
├── .env
├── requirements.txt
└── run.py
```

## Uso via WhatsApp

```
"Gastei 50 no almoço"
"Recebi 1500 de salário"
[Enviar foto de nota fiscal]
[Enviar áudio descrevendo gasto]
```

---

Kairix © 2025
