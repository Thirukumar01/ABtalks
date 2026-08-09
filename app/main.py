import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.config import settings
from db.database import init_db, get_session
from api.routes_agent import router as agent_router
from core.scheduler import start_scheduler, stop_scheduler
from services.agent_service import get_active_config

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autonomous_creator.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager:
    1. Initializes SQLite DB & WAL mode.
    2. If an active persona exists in DB, automatically arms APScheduler.
    3. Handles clean scheduler teardown on shutdown.
    """
    logger.info("Starting Autonomous AI Creator engine...")
    init_db()
    
    # Auto-resume scheduler if active persona exists in SQLite
    with get_session() as session:
        active_config = get_active_config(session)
        if active_config:
            logger.info(f"Active persona '{active_config.persona_name}' found. Starting autonomous background scheduler.")
            start_scheduler(interval_minutes=active_config.posting_interval_minutes)
        else:
            logger.info("No active agent persona yet. Waiting for /api/agent/init call.")
            
    yield
    
    logger.info("Shutting down background scheduler...")
    stop_scheduler()


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    app = FastAPI(
        title="Autonomous AI Creator",
        description="Autonomous AI Agent that discovers real-world news, applies editorial judgment, synthesizes persona-grounded posts, and runs on an unattended schedule.",
        version="1.0.0",
        lifespan=lifespan
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    app.include_router(agent_router)

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "ok",
            "env": settings.ENV,
            "version": "1.0.0"
        }

    # Mount static assets & dashboard
    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def serve_dashboard():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"status": "ok", "message": "Autonomous AI Creator API is running. Visit /docs for OpenAPI specs."}

    app.add_api_route("/", serve_dashboard, methods=["GET"], include_in_schema=False, name="dashboard")

    return app


app = create_app()
