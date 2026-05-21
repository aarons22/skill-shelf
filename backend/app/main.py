import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings, log_startup_config
from app.db import get_connection, run_migrations
from app.lib.setup_state import is_required
from app.routes import api_access, api_marketplaces, api_plugins, api_setup, auth_login, git_smart_http, marketplace_public

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    log_startup_config()
    with get_connection() as conn:
        if is_required(conn):
            logging.getLogger(__name__).warning(
                "SkillShelf is not yet set up. Visit %s/setup to configure it. "
                "The first user to walk the wizard will become the org administrator.",
                get_settings().public_base_url.rstrip("/"),
            )
    yield


app = FastAPI(title="SkillShelf", version="0.1.0", lifespan=lifespan)

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
