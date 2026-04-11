from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    JWT_SECRET: str
    OPENAI_API_KEY: str
    APP_ENV: str = "dev"

    # LLM 모델 분리
    # Director (의사결정, 저비용): claude-haiku-4-5-20251001
    # Agent (발화 생성, 고품질): claude-sonnet-4-6
    DIRECTOR_MODEL: str = "claude-haiku-4-5-20251001"
    AGENT_MODEL: str = "claude-sonnet-4-6"


settings = Settings()
