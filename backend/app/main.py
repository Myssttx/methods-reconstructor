from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import routes_exports, routes_papers, routes_reconstructions
from app.config import get_settings
from app.llm.gemini_client import active_llm_provider, get_llm
from app.logging import configure_logging, get_logger
from app.search.elastic_client import close_es
from app.search.indexes import ensure_indexes
from app.storage.firestore_client import get_store
from app.storage.redis_client import get_cache

settings = get_settings()
configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Eagerly initialize all singletons before serving traffic.
    # This prevents double-init races under concurrent startup (C-2, H-3).
    get_llm()
    get_store()
    get_cache()
    await ensure_indexes()
    log.info("startup", env=settings.app_env, llm=active_llm_provider())
    yield
    await close_es()
    log.info("shutdown")


app = FastAPI(
    title="Methods Reconstructor",
    version=__version__,
    description="Agent that resolves shortcut citations in scientific methods sections.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": active_llm_provider(),
        "elastic_url": settings.elastic_url,
    }


app.include_router(routes_papers.router, prefix="/api/papers", tags=["papers"])
app.include_router(routes_reconstructions.router, prefix="/api/reconstructions", tags=["reconstructions"])
app.include_router(routes_exports.router, prefix="/api/reconstructions", tags=["exports"])
