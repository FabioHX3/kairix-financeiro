# ============================================
# Kairix Financeiro - Backend
# ============================================
FROM python:3.13-slim

# Variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Diretório de trabalho
WORKDIR /app

# Copia arquivos de dependências
COPY pyproject.toml uv.lock* ./

# Instala dependências
RUN uv sync --frozen --no-dev

# Copia código fonte
COPY . .

# Expõe porta
EXPOSE 8014

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8014/health || exit 1

# Comando de inicialização (usa python do venv diretamente)
CMD [".venv/bin/python", "run.py"]
