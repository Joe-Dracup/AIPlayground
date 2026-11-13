from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE)

    cors_origins: list[str]
    database_url: str
    # Optional: without a key the app uses FakeLLM. SecretStr keeps it out of logs and error messages.
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5-5"


settings = Settings()
