import logging
import os
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)
DEFAULT_SESSION_SECRET = "dev-session-secret-change-me"


class Settings(BaseSettings):
    port: int = 3000
    public_base_url: str = "http://localhost:3000"
    data_dir: str = Field("./.skillshelf-data", validation_alias="SKILLSHELF_DATA_DIR")
    node_env: str = "development"
    session_secret: str = Field(DEFAULT_SESSION_SECRET, validation_alias="SKILLSHELF_SESSION_SECRET")
    log_level: str = Field("INFO", validation_alias="SKILLSHELF_LOG_LEVEL")
    encryption_key_path: str | None = Field(None, validation_alias="SKILLSHELF_ENCRYPTION_KEY_PATH")

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def marketplaces_dir(self) -> str:
        return os.path.join(self.data_dir, "marketplaces")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "skillshelf.db")

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    @property
    def is_development(self) -> bool:
        return self.node_env == "development"

    @property
    def public_origin(self) -> str:
        parsed = urlsplit(self.public_base_url)
        if not parsed.scheme or not parsed.netloc:
            return self.public_base_url.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def cors_allow_origins(self) -> list[str]:
        if self.is_development:
            return ["*"]
        return [self.public_origin]

    @property
    def secure_cookies(self) -> bool:
        return self.public_base_url.lower().startswith("https://")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def log_startup_config() -> None:
    s = get_settings()
    logger.info("PUBLIC_BASE_URL = %s", s.public_base_url)
    if not s.is_development and s.session_secret == DEFAULT_SESSION_SECRET:
        logger.warning(
            "SKILLSHELF_SESSION_SECRET is using the development default while NODE_ENV=%s. "
            "Set a strong secret before exposing this deployment.",
            s.node_env,
        )
    if not s.is_development and not s.public_base_url.lower().startswith("https://"):
        logger.warning(
            "PUBLIC_BASE_URL is not HTTPS while NODE_ENV=%s. "
            "Use HTTPS for production login callbacks, cookies, and agent URLs.",
            s.node_env,
        )
    if "localhost" in s.public_base_url and not s.is_development:
        logger.warning(
            "PUBLIC_BASE_URL contains 'localhost' but NODE_ENV=%s — "
            "every source.url in every marketplace.json will be unreachable from other machines",
            s.node_env,
        )
