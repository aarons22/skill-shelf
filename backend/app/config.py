import logging
import os
from functools import lru_cache

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    port: int = 3000
    public_base_url: str = "http://localhost:3000"
    data_dir: str = Field("./.skillshelf-data", validation_alias="SKILLSHELF_DATA_DIR")
    node_env: str = "development"
    session_secret: str = Field("dev-session-secret-change-me", validation_alias="SKILLSHELF_SESSION_SECRET")

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def marketplaces_dir(self) -> str:
        return os.path.join(self.data_dir, "marketplaces")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, "skillshelf.db")

    @property
    def db_url(self) -> str:
        return f"sqlite:///{self.db_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def log_startup_config() -> None:
    s = get_settings()
    logger.info("PUBLIC_BASE_URL = %s", s.public_base_url)
    if "localhost" in s.public_base_url and s.node_env != "development":
        logger.warning(
            "PUBLIC_BASE_URL contains 'localhost' but NODE_ENV=%s — "
            "every source.url in every marketplace.json will be unreachable from other machines",
            s.node_env,
        )
