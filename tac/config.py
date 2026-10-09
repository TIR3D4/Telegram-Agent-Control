from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TAC_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./data/tac.sqlite"
    bot_token: SecretStr = SecretStr("")
    owner_key: SecretStr = SecretStr("")
    owner_username: str = "owner"
    owner_password_hash: SecretStr = SecretStr("")
    oauth_admin_client_id: str = "tac-console"
    oauth_admin_client_secret: SecretStr = SecretStr("")
    agent_key: SecretStr = SecretStr("")
    legacy_agent_keys_enabled: bool = True
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

    approval_ttl_seconds: int = 3600
    approval_max_days: int = 30
    owner_oauth_subject: str = ""
    oauth_issuer: str = ""
    oauth_jwks_url: str = ""
    oauth_audience: str = ""
    oauth_max_lifetime: int = 3600
    retention_days: int = 90
    worker_stale_seconds: int = 90
    max_retries: int = 5
    otel_enabled: bool = False

    def check(self):
        keys = [self.owner_key.get_secret_value(), self.agent_key.get_secret_value()]
        if len(keys[0]) < 32 or (
            self.legacy_agent_keys_enabled and (len(keys[1]) < 32 or keys[0] == keys[1])
        ):
            raise RuntimeError(
                "Set different TAC_OWNER_KEY and TAC_AGENT_KEY (at least 32 characters). Run scripts/tacctl install."
            )

        if self.oauth_issuer:
            if not all(
                x.startswith("https://")
                for x in [self.oauth_issuer, self.oauth_jwks_url, self.oauth_audience, self.public_url]
            ):
                raise RuntimeError("OAuth issuer, JWKS, audience and public URL require HTTPS")
            if self.oauth_audience != self.public_url.rstrip("/") + "/mcp":
                raise RuntimeError("OAuth audience must be the canonical public /mcp resource URL")

    @property
    def chats(self):
        return {x.strip().lower() for x in self.allowed_chats.split(",") if x.strip()}


@lru_cache
def settings():
    return Settings()
