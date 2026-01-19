"""
Configurações do sistema usando Pydantic Settings.
Validação rigorosa de variáveis de ambiente para produção.
"""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação com validação."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Server
    HOST: str = "0.0.0.0"  # noqa: S104 - Binding to all interfaces is intentional for Docker
    PORT: int = 8014
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # CORS - origens permitidas (separadas por vírgula)
    CORS_ORIGINS: str = "http://localhost:3000"

    # Database
    DATABASE_URL: str = Field(
        ...,
        description="URL de conexão com o PostgreSQL",
        json_schema_extra={"example": "postgresql://user:pass@localhost:5432/dbname"},
    )

    # Security
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="Chave secreta para JWT (mínimo 32 caracteres)",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SYSTEM_API_KEY: str = ""

    # Webhook Security
    WEBHOOK_SECRET: str = Field(
        default="",
        description="Secret para validação HMAC de webhooks",
    )

    # LLM (OpenRouter)
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "google/gemini-2.5-flash"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # WhatsApp API (UAZAPI)
    WHATSAPP_API_URL: str = ""
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_INSTANCE: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str, info) -> str:
        """Valida que SECRET_KEY não é o valor padrão em produção."""
        if v == "change-me-in-production":
            # Em desenvolvimento, permite o valor padrão
            import os

            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError("SECRET_KEY deve ser alterada em produção")
        return v

    @property
    def cors_origins_list(self) -> list[str]:
        """Retorna lista de origens CORS permitidas."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
