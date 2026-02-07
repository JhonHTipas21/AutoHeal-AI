"""
AutoHeal AI - AutoHeal Agent Main Application
===============================================

FastAPI application for autonomous healing.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.api.routes import router as api_router

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

setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_output=settings.log_json
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    logger.info(
        f"Starting {settings.service_name} v{settings.service_version}",
        extra={
            "version": settings.service_version,
            "healing_mode": settings.healing_mode.value
        }
    )
    
    # Initialize OODA engine
    from src.core.ooda_engine import OODAEngine
    engine = OODAEngine()
    app.state.ooda_engine = engine
    
    logger.info(f"OODA Engine initialized in {settings.healing_mode.value} mode")
    
    yield
    
    logger.info("Shutting down AutoHeal Agent...")


app = FastAPI(
    title="AutoHeal AI - AutoHeal Agent",
    description="Autonomous healing with OODA reasoning loop",
    version=settings.service_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID")
    if not correlation_id:
        correlation_id = str(uuid.uuid4())
    
    set_correlation_id(correlation_id)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": str(exc) if settings.debug else "An error occurred"}
    )


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version
    }


@app.get("/ready", tags=["health"])
async def readiness_check(request: Request):
    engine = request.app.state.ooda_engine
    return {
        "status": "ready",
        "service": settings.service_name,
        "mode": settings.healing_mode.value,
        "active_healings": engine.get_active_count()
    }


app.include_router(api_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.host, port=settings.port, reload=settings.debug)
