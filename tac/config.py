from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TAC_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/tac.sqlite"
    bot_token: SecretStr = SecretStr("")
    owner_key: SecretStr = SecretStr("")
    agent_key: SecretStr = SecretStr("")
    reader_key: SecretStr = SecretStr("")
    webhook_secret: SecretStr = SecretStr("")
    allowed_chats: str = ""
    storage_dir: Path = Path("data/media")
    public_url: str = "http://127.0.0.1:8787"
    telegram_base: str = "https://api.telegram.org"
    timezone: str = "Asia/Tehran"
    upload_limit_mb: int = 50
    lease_seconds: int = 180
    log_level: str = "INFO"
    poll_interval: float = 1.0

    def check(self):
        keys = [self.owner_key.get_secret_value(), self.agent_key.get_secret_value()]
        if any(len(x) < 32 for x in keys) or keys[0] == keys[1]:
            raise RuntimeError(
                "Set different TAC_OWNER_KEY and TAC_AGENT_KEY (at least 32 characters). Run scripts/tacctl install."
            )

    @property
    def chats(self):
        return {x.strip().lower() for x in self.allowed_chats.split(",") if x.strip()}


@lru_cache
def settings():
    return Settings()
