import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure project root is on sys.path so core, db, services, discovery, editorial, generation, memory are available
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.db.base import init_db
from app.api.router import api_router
from app.utils.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager:
    1. Initializes SQLite WAL database and tables on startup.
    2. Auto-arms APScheduler if an active persona exists in database.
    3. Performs clean background scheduler teardown on shutdown.
    """
    logger.info("Initializing ABTalks SQLite WAL Database & Schema...")
    init_db()

    # Auto-resume scheduler if active persona exists in SQLite
    try:
        from core.scheduler import start_scheduler, stop_scheduler
        from services.agent_service import get_active_config
        from db.database import get_session
        with get_session() as session:
            active_config = get_active_config(session)
            if active_config:
                logger.info(f"Active persona '{active_config.persona_name}' found. Starting autonomous background scheduler (Interval: {active_config.posting_interval_minutes}m).")
                start_scheduler(interval_minutes=active_config.posting_interval_minutes)
            else:
                logger.info("No active agent persona configured yet.")
    except Exception as exc:
        logger.warning(f"Scheduler initialization note: {exc}")

    logger.info("Database and services initialized successfully.")
    yield
    logger.info("Shutting down ABTalks backend service and scheduler...")
    try:
        from core.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Factory creating and configuring the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        description="Autonomous AI Agent Backend — Milestone 1 Foundation.",
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom Exception Handlers
    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": str(detail), "detail": detail}
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "validation_error", "detail": exc.errors()}
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_server_error", "detail": "An unexpected error occurred."}
        )

    # Mount API Router
    app.include_router(api_router)

    # Serve the existing Autonomous AI Creator dashboard and its assets from
    # the project-level static directory.  The frontend calls the API using
    # same-origin /api/agent URLs, so it must be served by this API process.
    static_dir = PROJECT_ROOT / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    def serve_dashboard():
        index_file = static_dir / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Dashboard index not found")

    app.add_api_route("/", serve_dashboard, methods=["GET"], include_in_schema=False, name="dashboard")

    # Health Check
    @app.get("/health", tags=["Health"])
    def health_check():
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "env": settings.ENV
        }

    return app


app = create_app()
