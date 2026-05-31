"""
Configuracao central do JUNO Backend.

Todas as variaveis de ambiente sao lidas aqui usando pydantic-settings.
Falha rapido (fail-fast) se variaveis obrigatorias nao estiverem definidas
em producao.
"""

import secrets
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === Ambiente ===
    JUNO_ENV: str = Field(default="development", description="development | staging | production")
    APP_VERSION: str = Field(default="0.3.2", description="Versao funcional do JUNO")

    # === Seguranca ===
    SECRET_KEY: str = Field(default="", description="Chave para assinar JWTs")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=480)
    JUNO_DEV_AUTH_BYPASS: bool = Field(
        default=True,
        description="Permite usuario dev automatico sem token apenas em JUNO_ENV=development",
    )
    # Chave Fernet (32 bytes url-safe base64). Obrigatoria em producao.
    # Gerar com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = Field(default="", description="Fernet key para dados sensiveis")

    # === Banco de dados ===
    DATABASE_URL: str = Field(default="", description="postgresql://user:pass@host:port/db")
    REDIS_URL: str = Field(default="", description="redis://host:port/db para cache/filas")

    # === CORS ===
    ALLOWED_ORIGINS: str = Field(default="http://localhost:3000")

    # === OpenAI ===
    OPENAI_API_KEY: str = Field(default="")

    # === Rate limiting ===
    LOGIN_RATE_LIMIT: str = Field(default="5/minute")

    # === Logging ===
    LOG_LEVEL: str = Field(default="INFO")
    LOG_FORMAT: str = Field(default="auto", description="auto | text | json")

    # === Ontology Engine (v0.2.0-dev) ===
    # Feature flag — quando true, carrega definitions/ no startup e expoe
    # rotas /api/v1/ontology/*. Em dev pode ficar ligado; em prod, esperar
    # a Semana 6 do roadmap (lineage + metricas).
    ONTOLOGY_ENABLED: bool = Field(default=False)
    # Se true, validate_consistency falha o startup (apropriado em prod).
    # Em dev pode ficar false para o app subir mesmo com YAML inconsistente.
    ONTOLOGY_STRICT: bool = Field(default=False)

    @property
    def is_production(self) -> bool:
        return self.JUNO_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.JUNO_ENV.lower() == "development"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v, info):
        env = (info.data.get("JUNO_ENV") or "development").lower()
        if not v:
            if env == "production":
                raise ValueError(
                    "SECRET_KEY e obrigatoria em producao. Gere com "
                    'python -c "import secrets; print(secrets.token_urlsafe(64))"'
                )
            return secrets.token_urlsafe(64)
        if len(v) < 32:
            raise ValueError("SECRET_KEY precisa ter pelo menos 32 caracteres")
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def _validate_database_url(cls, v, info):
        env = (info.data.get("JUNO_ENV") or "development").lower()
        if not v:
            if env == "production":
                raise ValueError("DATABASE_URL e obrigatoria em producao.")
            return "sqlite:///./juno_dev.db"
        return v

    @field_validator("ENCRYPTION_KEY")
    @classmethod
    def _validate_encryption_key(cls, v, info):
        env = (info.data.get("JUNO_ENV") or "development").lower()
        if not v:
            if env == "production":
                raise ValueError(
                    "ENCRYPTION_KEY e obrigatoria em producao. Gere com "
                    'python -c "from cryptography.fernet import Fernet; '
                    'print(Fernet.generate_key().decode())"'
                )
            return v
        try:
            from cryptography.fernet import Fernet

            Fernet(v.encode("utf-8"))
        except Exception as exc:
            raise ValueError("ENCRYPTION_KEY invalida; use uma chave Fernet valida") from exc
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton de Settings."""
    return Settings()


settings = get_settings()
