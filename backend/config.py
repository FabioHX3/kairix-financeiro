import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8014))
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    SYSTEM_API_KEY: str = os.getenv("SYSTEM_API_KEY", "")

    # LLM
    LLM_OPCAO: int = int(os.getenv("LLM_OPCAO", 2))

    # Ollama
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "openchat:7b")

    # OpenRouter
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openai/gpt-3.5-turbo")

    # OpenAI (Whisper)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Evolution API (WhatsApp)
    EVOLUTION_URL: str = os.getenv("EVOLUTION_URL", "http://localhost:8055")
    EVOLUTION_API_KEY: str = os.getenv("EVOLUTION_API_KEY", "")
    EVOLUTION_INSTANCE: str = os.getenv("EVOLUTION_INSTANCE", "")


settings = Settings()
