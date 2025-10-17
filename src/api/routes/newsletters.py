"""
Newsletter API routes for Newsletter Podcast Generator.

This module provides FastAPI routes for newsletter submission,
status monitoring, and processing management.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, HttpUrl, Field

from src.lib.config import get_config
from src.lib.logging import get_logger
from src.lib.exceptions import ProcessingError, ValidationError
from src.services import NewsletterProcessor


logger = get_logger(__name__)
router = APIRouter(prefix="/newsletters", tags=["newsletters"])


# Request/Response models
class NewsletterURLRequest(BaseModel):
    """Request model for newsletter URL submission."""
    url: HttpUrl = Field(..., description="Newsletter URL to process")
    user_id: Optional[str] = Field(None, description="Optional user ID for tracking")
    style: str = Field("conversational", description="Summary style: conversational, formal, casual")
    target_length: str = Field("medium", description="Target length: short, medium, long")
    voice: Optional[str] = Field(None, description="TTS voice (provider-specific)")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed (0.5-2.0)")
    pitch: float = Field(1.0, ge=0.5, le=2.0, description="Speech pitch (0.5-2.0)")
    output_format: str = Field("mp3", description="Audio format: mp3, wav")
    quality: str = Field("standard", description="Audio quality: standard, high")
    focus_areas: Optional[list[str]] = Field(None, description="Topics to emphasize")


class NewsletterTextRequest(BaseModel):
    """Request model for newsletter text submission."""
    content: str = Field(..., min_length=1, description="Newsletter content")
    title: Optional[str] = Field(None, description="Newsletter title")
    content_type: str = Field("text", description="Content type: text, html, markdown")
    user_id: Optional[str] = Field(None, description="Optional user ID for tracking")
    style: str = Field("conversational", description="Summary style: conversational, formal, casual")
    target_length: str = Field("medium", description="Target length: short, medium, long")
    voice: Optional[str] = Field(None, description="TTS voice (provider-specific)")
    speed: float = Field(1.0, ge=0.5, le=2.0, description="Speech speed (0.5-2.0)")
    pitch: float = Field(1.0, ge=0.5, le=2.0, description="Speech pitch (0.5-2.0)")
    output_format: str = Field("mp3", description="Audio format: mp3, wav")
    quality: str = Field("standard", description="Audio quality: standard, high")
    focus_areas: Optional[list[str]] = Field(None, description="Topics to emphasize")


class NewsletterResponse(BaseModel):
    """Response model for newsletter operations."""
    newsletter_id: str
    status: str
    message: str
    estimated_completion_time: Optional[str] = None


class ProcessingStatusResponse(BaseModel):
    """Response model for processing status."""
    newsletter_id: str
    status: str
    title: Optional[str]
    created_at: str
    updated_at: str
    word_count: Optional[int]
    error_message: Optional[str]
    episode: Optional[Dict[str, Any]]


async def get_newsletter_processor():
    """Dependency to get newsletter processor instance."""
    config = get_config()
    async with NewsletterProcessor(config) as processor:
        yield processor


@router.post("/from-url", response_model=NewsletterResponse)
async def submit_newsletter_from_url(
    request: NewsletterURLRequest,
    background_tasks: BackgroundTasks,
    processor: NewsletterProcessor = Depends(get_newsletter_processor)
):
    """
    Submit a newsletter URL for processing.
    
    This endpoint accepts a newsletter URL and starts the processing pipeline
    asynchronously. The processing includes content extraction, LLM summarization,
    and TTS generation.
    
    Returns immediately with a newsletter ID that can be used to track progress.
    """
    try:
        logger.info(f"Received newsletter URL submission: {request.url}")
        
        # Prepare processing options
        processing_options = {
            "style": request.style,
            "target_length": request.target_length,
            "voice": request.voice,
            "speed": request.speed,
            "pitch": request.pitch,
            "output_format": request.output_format,
            "quality": request.quality,
            "focus_areas": request.focus_areas
        }
        
        # Start processing in background
        background_tasks.add_task(
            _process_newsletter_url,
            str(request.url),
            request.user_id,
            processing_options
        )
        
        # Return immediately with tracking info
        return NewsletterResponse(
            newsletter_id="processing",  # Will be generated in background
            status="submitted",
            message="Newsletter submitted for processing",
            estimated_completion_time="2-5 minutes"
        )
        
    except ValidationError as e:
        logger.error(f"Validation error in URL submission: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in URL submission: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/from-text", response_model=NewsletterResponse)
async def submit_newsletter_from_text(
    request: NewsletterTextRequest,
    background_tasks: BackgroundTasks,
    processor: NewsletterProcessor = Depends(get_newsletter_processor)
):
    """
    Submit newsletter text content for processing.
    
    This endpoint accepts raw newsletter content (text, HTML, or Markdown)
    and starts the processing pipeline asynchronously.
    
    Returns immediately with a newsletter ID that can be used to track progress.
    """
    try:
        logger.info(f"Received newsletter text submission: {len(request.content)} chars")
        
        # Prepare processing options
        processing_options = {
            "style": request.style,
            "target_length": request.target_length,
            "voice": request.voice,
            "speed": request.speed,
            "pitch": request.pitch,
            "output_format": request.output_format,
            "quality": request.quality,
            "focus_areas": request.focus_areas
        }
        
        # Start processing in background
        background_tasks.add_task(
            _process_newsletter_text,
            request.content,
            request.title,
            request.content_type,
            request.user_id,
            processing_options
        )
        
        # Return immediately with tracking info
        return NewsletterResponse(
            newsletter_id="processing",  # Will be generated in background
            status="submitted",
            message="Newsletter submitted for processing",
            estimated_completion_time="2-5 minutes"
        )
        
    except ValidationError as e:
        logger.error(f"Validation error in text submission: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in text submission: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{newsletter_id}/status", response_model=ProcessingStatusResponse)
async def get_newsletter_status(
    newsletter_id: str,
    processor: NewsletterProcessor = Depends(get_newsletter_processor)
):
    """
    Get processing status for a newsletter.
    
    Returns detailed information about the newsletter processing status,
    including current stage, completion percentage, and any error messages.
    """
    try:
        logger.info(f"Status request for newsletter: {newsletter_id}")
        
        status_info = await processor.get_processing_status(newsletter_id)
        
        return ProcessingStatusResponse(**status_info)
        
    except ValidationError as e:
        logger.error(f"Newsletter not found: {newsletter_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting newsletter status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{newsletter_id}/retry", response_model=NewsletterResponse)
async def retry_newsletter_processing(
    newsletter_id: str,
    background_tasks: BackgroundTasks,
    processor: NewsletterProcessor = Depends(get_newsletter_processor)
):
    """
    Retry processing for a failed newsletter.
    
    This endpoint allows retrying the processing pipeline for newsletters
    that failed during processing.
    """
    try:
        logger.info(f"Retry request for newsletter: {newsletter_id}")
        
        # Start retry in background
        background_tasks.add_task(_retry_newsletter_processing, newsletter_id)
        
        return NewsletterResponse(
            newsletter_id=newsletter_id,
            status="retrying",
            message="Newsletter processing retry started",
            estimated_completion_time="2-5 minutes"
        )
        
    except ValidationError as e:
        logger.error(f"Cannot retry newsletter {newsletter_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrying newsletter processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/health")
async def health_check(processor: NewsletterProcessor = Depends(get_newsletter_processor)):
    """
    Health check endpoint for newsletter processing services.
    
    Returns the health status of all processing services (content extraction,
    LLM summarization, TTS generation).
    """
    try:
        health_status = await processor.health_check()
        
        overall_healthy = all(health_status.values())
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "services": health_status,
            "timestamp": "2024-01-01T00:00:00Z"  # Will be replaced with actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@router.get("/service-info")
async def get_service_info(processor: NewsletterProcessor = Depends(get_newsletter_processor)):
    """
    Get information about configured processing services.
    
    Returns details about the current LLM and TTS providers,
    available voices, and service configuration.
    """
    try:
        service_info = processor.get_service_info()
        
        return {
            "services": service_info,
            "timestamp": "2024-01-01T00:00:00Z"  # Will be replaced with actual timestamp
        }
        
    except Exception as e:
        logger.error(f"Error getting service info: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Background task functions

async def _process_newsletter_url(
    url: str,
    user_id: Optional[str],
    processing_options: Dict[str, Any]
):
    """Background task to process newsletter from URL."""
    try:
        config = get_config()
        async with NewsletterProcessor(config) as processor:
            newsletter = await processor.process_newsletter_from_url(
                url=url,
                user_id=user_id,
                processing_options=processing_options
            )
            logger.info(f"Background processing completed for newsletter: {newsletter.id}")
            
    except Exception as e:
        logger.error(f"Background processing failed for URL {url}: {e}")


async def _process_newsletter_text(
    content: str,
    title: Optional[str],
    content_type: str,
    user_id: Optional[str],
    processing_options: Dict[str, Any]
):
    """Background task to process newsletter from text."""
    try:
        config = get_config()
        async with NewsletterProcessor(config) as processor:
            newsletter = await processor.process_newsletter_from_text(
                content=content,
                title=title,
                content_type=content_type,
                user_id=user_id,
                processing_options=processing_options
            )
            logger.info(f"Background processing completed for newsletter: {newsletter.id}")
            
    except Exception as e:
        logger.error(f"Background processing failed for text content: {e}")


async def _retry_newsletter_processing(newsletter_id: str):
    """Background task to retry newsletter processing."""
    try:
        config = get_config()
        async with NewsletterProcessor(config) as processor:
            newsletter = await processor.retry_failed_processing(newsletter_id)
            logger.info(f"Background retry completed for newsletter: {newsletter.id}")
            
    except Exception as e:
        logger.error(f"Background retry failed for newsletter {newsletter_id}: {e}")