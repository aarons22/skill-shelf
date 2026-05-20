import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import log_startup_config
from app.db import run_migrations
from app.routes import api_access, api_marketplaces, api_plugins, auth_login, git_smart_http, marketplace_public

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    log_startup_config()
    yield


app = FastAPI(title="SkillShelf", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_marketplaces.router)
app.include_router(api_plugins.router)
app.include_router(api_access.router)
app.include_router(auth_login.router)
app.include_router(marketplace_public.router)
app.include_router(git_smart_http.router)


@app.get("/health")
def health():
    return {"ok": True}
