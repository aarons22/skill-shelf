import contextvars
import logging
import secrets
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pythonjsonlogger import jsonlogger

from app.config import DEFAULT_SESSION_SECRET, get_settings, log_startup_config
from app.db import get_connection, run_migrations
from app.lib.secret_box import ensure_key_exists
from app.lib.setup_state import is_required
from app.routes import api_access, api_marketplaces, api_plugins, api_setup, auth_login, git_smart_http, marketplace_public

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def _configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    if settings.is_development:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s - %(message)s")
        )
    else:
        handler.setFormatter(
            jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
                rename_fields={"asctime": "timestamp", "levelname": "level"},
            )
        )
    handler.addFilter(_RequestIdFilter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    root.addHandler(handler)


_configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    ensure_key_exists()
    if not settings.is_development and settings.session_secret == DEFAULT_SESSION_SECRET:
        raise RuntimeError(
            "SKILLSHELF_SESSION_SECRET is set to the development default. "
            "Set a strong secret in SKILLSHELF_SESSION_SECRET before running in non-development mode."
        )
    run_migrations()
    log_startup_config()
    with get_connection() as conn:
        if is_required(conn):
            logging.getLogger(__name__).warning(
                "SkillShelf is not yet set up. Visit %s/setup to configure it. "
                "The first user to walk the wizard will become the org administrator.",
                settings.public_base_url.rstrip("/"),
            )
    yield


app = FastAPI(title="SkillShelf", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: Callable) -> Response:
    request_id = request.headers.get("X-Request-ID") or secrets.token_hex(8)
    token = _request_id.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        _request_id.reset(token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_marketplaces.router)
app.include_router(api_plugins.router)
app.include_router(api_access.router)
app.include_router(api_setup.router)
app.include_router(auth_login.router)
app.include_router(marketplace_public.router)
app.include_router(git_smart_http.router)


@app.get("/health")
def health():
    return {"ok": True}
