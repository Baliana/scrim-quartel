import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

# IDs militares autorizados a criar contas administrativas.
# Adicione os IDs permitidos entre as chaves. A lista vazia bloqueia todos os
# novos administradores, sem afetar cadastros de usuários comuns.
IDS_MILITARES_ADMIN_AUTORIZADOS: frozenset[str] = frozenset({
    "021531957-5",
})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Banco de dados
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "materiais_db"

    # JWT
    JWT_SECRET_KEY: str = "troque-esta-chave-em-producao"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24h

    # Twilio WhatsApp
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"  # sandbox padrão da Twilio

    # CORS
    CORS_ORIGINS: str = "*"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
