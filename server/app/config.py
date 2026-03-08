from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/retailsutra"
    SECRET_KEY: str = "change-me-to-a-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@bharatselleros.com"

    FRONTEND_URL: str = "http://localhost:5173"

    # Amazon SP-API
    SP_API_APP_ID: str = ""  # Application ID from Seller Central Developer Console
    SP_API_REDIRECT_URI: str = "http://localhost:8000/api/v1/amazon/callback"
    SP_API_REFRESH_TOKEN: str = ""
    SP_API_LWA_APP_ID: str = ""
    SP_API_LWA_CLIENT_SECRET: str = ""
    SP_API_AWS_ACCESS_KEY: str = ""
    SP_API_AWS_SECRET_KEY: str = ""
    SP_API_ROLE_ARN: str = ""
    SP_API_MARKETPLACE_ID: str = "A21TJRUUN4KGV"  # Amazon.in
    SP_API_REGION: str = "EU"  # India falls under EU region

    # Sync settings
    SYNC_INTERVAL_HOURS: int = 6
    RAW_DUMP_DIR: str = "./raw_dumps"
    USE_MOCK_DATA: bool = True

    # AWS Bedrock (AI Assistant)
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BEARER_TOKEN_BEDROCK: str = ""  # Bedrock API Key (bearer token auth)
    BEDROCK_MODEL_ID: str = "amazon.nova-lite-v1:0"
    BEDROCK_SUMMARIZER_MODEL_ID: str = ""  # Override model for summarization (e.g. nova-pro)
    BEDROCK_MAX_TOKENS: int = 2048
    AI_RATE_LIMIT_PER_MINUTE: int = 20
    AI_DAILY_LIMIT: int = 200
    TAVILY_API_KEY: str = ""  # Free tier: 1000 searches/month

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
