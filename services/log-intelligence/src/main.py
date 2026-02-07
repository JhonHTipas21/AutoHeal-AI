"""
AutoHeal AI - Log Intelligence Service Main Application
========================================================

FastAPI application for log analysis with SLM integration.

Responsibilities:
- Ingest logs from various sources
- Analyze logs using Small Language Models
- Classify error types
- Infer probable root causes
- Correlate errors with recent commits
- Send analysis events to Incident Manager
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.api.routes import router as api_router

# Try to import shared logging
try:
    from shared.utils.logging import setup_logging, get_logger, set_correlation_id
except ImportError:
    import logging
    import sys
    
    def setup_logging(service_name: str, log_level: str = "INFO", json_output: bool = True):
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=f"%(asctime)s | {service_name} | %(levelname)s | %(name)s | %(message)s",
            stream=sys.stdout
        )
    
    def get_logger(name: str):
        return logging.getLogger(name)
    
    def set_correlation_id(cid: str):
        pass


settings = get_settings()

# Initialize logging
setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_output=settings.log_json
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    """
    logger.info(
        f"Starting {settings.service_name} v{settings.service_version}",
        extra={
            "version": settings.service_version,
            "slm_provider": settings.slm_provider.value
        }
    )
    
    # Initialize SLM analyzer
    from src.core.slm_analyzer import get_slm_analyzer
    analyzer = get_slm_analyzer()
    await analyzer.initialize()
    logger.info(f"SLM analyzer initialized: {settings.slm_provider.value}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down log intelligence service...")
    await analyzer.shutdown()
    logger.info("Log intelligence service shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AutoHeal AI - Log Intelligence Service",
    description="Log analysis with SLM for error classification and root cause inference",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Middleware to extract or generate correlation ID."""
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    set_correlation_id(correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(
        f"Unhandled exception: {exc}",
        extra={"path": request.url.path},
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.debug else None
        }
    )


# Health check
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version
    }


@app.get("/ready", tags=["health"])
async def readiness_check():
    """Readiness check endpoint."""
    from src.core.slm_analyzer import get_slm_analyzer
    analyzer = get_slm_analyzer()
    
    return {
        "status": "ready",
        "service": settings.service_name,
        "slm_provider": settings.slm_provider.value,
        "slm_ready": analyzer.is_ready()
    }


# Include API routes
app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
