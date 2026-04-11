from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    JWT_SECRET: str
    OPENAI_API_KEY: str
    APP_ENV: str = "dev"

    # LLM
    LLM_PROVIDER: str = "openai"
    # Director (의사결정, 저비용)
    # Agent (발화 생성 — 품질 부족 시 gpt-4o로 교체)
    DIRECTOR_MODEL: str = "gpt-4o-mini"
    AGENT_MODEL: str = "gpt-4o-mini"


settings = Settings()
