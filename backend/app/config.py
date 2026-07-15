import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str
    anthropic_api_key: str | None = None


settings = Settings()

# La clé Anthropic est fournie dans backend/.env (comme les vars Supabase). On la
# recopie dans os.environ pour que le SDK anthropic et app.analyse.llm.analyser()
# (qui lisent os.environ) la voient. setdefault : une var déjà exportée l'emporte,
# et les tests qui monkeypatch os.environ restent maîtres.
if settings.anthropic_api_key:
    os.environ.setdefault("ANTHROPIC_API_KEY", settings.anthropic_api_key)
