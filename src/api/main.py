"""
Main FastAPI application for Newsletter Podcast Generator.

This module creates and configures the FastAPI application with all routes,
middleware, and error handling.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from src.lib.config import get_config
from src.lib.logging import get_logger, setup_logging
from src.lib.database import init_database
from src.lib.exceptions import ValidationError, ProcessingError, LLMError, TTSError
from src.api.routes import newsletters


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Newsletter Podcast Generator API")
    
    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Newsletter Podcast Generator API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    config = get_config()
    
    # Setup logging
    setup_logging(config)
    
    # Create FastAPI app
    app = FastAPI(
        title="Newsletter Podcast Generator",
        description="Convert newsletters into podcast episodes using AI",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if config.api.enable_docs else None,
        redoc_url="/redoc" if config.api.enable_docs else None
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(newsletters.router, prefix="/api/v1")
    
    # Add error handlers
    add_error_handlers(app)
    
    # Add middleware
    add_middleware(app)
    
    return app


def add_error_handlers(app: FastAPI):
    """Add custom error handlers."""
    
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Validation Error",
                "message": str(exc),
                "type": "validation_error"
            }
        )
    
    @app.exception_handler(ProcessingError)
    async def processing_error_handler(request: Request, exc: ProcessingError):
        logger.error(f"Processing error: {exc}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "Processing Error",
                "message": str(exc),
                "type": "processing_error"
            }
        )
    
    @app.exception_handler(LLMError)
    async def llm_error_handler(request: Request, exc: LLMError):
        logger.error(f"LLM error: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "LLM Service Error",
                "message": "Language model service is currently unavailable",
                "type": "llm_error"
            }
        )
    
    @app.exception_handler(TTSError)
    async def tts_error_handler(request: Request, exc: TTSError):
        logger.error(f"TTS error: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "TTS Service Error", 
                "message": "Text-to-speech service is currently unavailable",
                "type": "tts_error"
            }
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTP Error",
                "message": exc.detail,
                "type": "http_error"
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred",
                "type": "internal_error"
            }
        )


def add_middleware(app: FastAPI):
    """Add custom middleware."""
    
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """Log requests and responses."""
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url}")
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info(
                f"Response: {response.status_code} "
                f"({process_time:.3f}s) {request.method} {request.url}"
            )
            
            # Add timing header
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url} "
                f"({process_time:.3f}s) - {e}"
            )
            raise


# Create the app instance
app = create_app()


# Health check endpoint
@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "service": "newsletter-podcast-generator",
        "version": "1.0.0",
        "timestamp": "2024-01-01T00:00:00Z"  # Will be replaced with actual timestamp
    }


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Newsletter Podcast Generator API",
        "version": "1.0.0",
        "description": "Convert newsletters into podcast episodes using AI",
        "docs_url": "/docs",
        "health_url": "/health"
    }


def run_server():
    """Run the development server."""
    config = get_config()
    
    uvicorn.run(
        "src.api.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
        log_level="info" if not config.api.debug else "debug"
    )


if __name__ == "__main__":
    run_server()


# Add missing import
import time