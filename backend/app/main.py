"""FastAPI entrypoint.

The OpenAPI description is written for a third party, not for us: a Digital
Public Good has to be adoptable by a state IT team that has never spoken to the
authors. The generated /openapi.json is the machine-readable half of that.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db
from app.routers import (
    districts,
    funds,
    health,
    hotspots,
    intake,
    ivr,
    official,
    recommendations,
    requests,
    sms,
    track,
)

settings = get_settings()
logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create tables before the first request. Idempotent, so a container that
    already has a seeded SQLite file baked in boots without touching it.

    The token backfill runs here rather than inside `init_db` to keep the `db`
    package from importing the `services` package — the layering this project is
    careful about. It is a no-op after the first boot.
    """
    init_db()

    from app.db.database import SessionLocal
    from app.services.tracking import backfill

    with SessionLocal() as db:
        issued = backfill(db)
    if issued:
        logging.getLogger(__name__).info("Backfilled %s tracking tokens", issued)

    yield


app = FastAPI(
    title="JanSetu API",
    version="0.1.0",
    description=(
        "Open API for aggregating citizen development requests across Indian "
        "languages and channels, and ranking high-priority public projects "
        "against demographic, infrastructure and budget data.\n\n"
        "Licensed MIT. Request taxonomy, language list and scoring weights are "
        "configuration, not code — see /capabilities."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(districts.router)
app.include_router(funds.router)
app.include_router(intake.router)
app.include_router(track.router)
app.include_router(ivr.router)
app.include_router(ivr.router, prefix="/api/v1")
app.include_router(sms.router)
app.include_router(official.router)
app.include_router(requests.router)
app.include_router(hotspots.router)
app.include_router(recommendations.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "JanSetu",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "capabilities": "/capabilities",
    }
