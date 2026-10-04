"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import analysis, meta, projects, vendors
from app.api.error_handlers import register_error_handlers
from app.config import DEFAULT_SCORING_CONFIG, PROJECT_ROOT, ScoringConfig, Settings
from app.data.database import Database
from app.services.scoring.engine import SemanticScorer
from app.services.scoring.text import SemanticCriterionScorer
from app.services.semantic.embedder import SentenceTransformerEmbedder

STATIC_DIR = PROJECT_ROOT / "static"


class RevalidatingStaticFiles(StaticFiles):
    """Static files that browsers must revalidate (cheap 304s via ETag) so a redeploy is never
    shadowed by an old cached JavaScript module."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response
# uvicorn configures this logger, so start-up messages reach stdout / Cloud Run logs.
logger = logging.getLogger("uvicorn.error")


def create_app(
    settings: Settings | None = None,
    *,
    semantic_scorer: SemanticScorer | None = None,
    scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> FastAPI:
    """Build the app. Nothing touches the disk or loads the model until the app starts/uses it."""
    settings = settings or Settings.from_env()
    database = Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        database.init_schema()
        embedder = getattr(app.state.semantic_scorer, "embedder", None)
        if settings.preload_model and hasattr(embedder, "warm_up"):
            # One model per process, loaded before the first request is served. If it fails, the
            # app still starts: structured scoring works and text criteria return a clear 503.
            try:
                started = time.perf_counter()
                embedder.warm_up()
                logger.info("Semantic model preloaded in %.1fs.", time.perf_counter() - started)
            except Exception:
                logger.exception("Semantic model preload failed; it will be retried on first use.")
        yield

    app = FastAPI(
        title="VendorMatch AI",
        version="0.1.0",
        description="Transparent, explainable compatibility analysis of software vendor proposals. "
        "Decision support only; all processing runs locally.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.database = database
    app.state.scoring_config = scoring_config
    # The MiniLM model is loaded lazily on the first analysis that has a text criterion.
    app.state.semantic_scorer = semantic_scorer or SemanticCriterionScorer(
        SentenceTransformerEmbedder(scoring_config.semantic_model_name)
    )

    register_error_handlers(app)
    for module in (meta, projects, vendors, analysis):
        app.include_router(module.router)
    # The vanilla JS frontend. Mounted last so every /api route takes precedence.
    app.mount("/", RevalidatingStaticFiles(directory=STATIC_DIR, html=True), name="frontend")
    return app


app = create_app()
