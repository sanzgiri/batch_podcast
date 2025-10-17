"""
Newsletter Processor Service for Newsletter Podcast Generator.

This service orchestrates the complete newsletter-to-podcast conversion pipeline,
coordinating content extraction, LLM summarization, TTS generation, and storage.
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.config import Config
from src.lib.database import get_db_session
from src.lib.logging import get_logger
from src.lib.exceptions import ProcessingError, ValidationError
from src.lib.metrics import record_processing_time, increment_counter
from src.models import Newsletter, Episode, NewsletterStatus, EpisodeStatus
from src.services import ContentExtractor, LLMSummarizer, TTSGenerator


logger = get_logger(__name__)


class NewsletterProcessor:
    """
    Main orchestration service for newsletter-to-podcast conversion.
    
    Handles the complete pipeline from content extraction through audio generation,
    with proper error handling, status tracking, and recovery mechanisms.
    """
    
    def __init__(self, config: Config):
        """Initialize Newsletter Processor with configuration."""
        self.config = config
        
        # Service instances will be created as context managers
        self.content_extractor: Optional[ContentExtractor] = None
        self.llm_summarizer: Optional[LLMSummarizer] = None
        self.tts_generator: Optional[TTSGenerator] = None
    
    async def __aenter__(self):
        """Async context manager entry - initialize all services."""
        try:
            # Initialize services as context managers
            self.content_extractor = ContentExtractor(self.config)
            await self.content_extractor.__aenter__()
            
            self.llm_summarizer = LLMSummarizer(self.config)
            await self.llm_summarizer.__aenter__()
            
            self.tts_generator = TTSGenerator(self.config)
            await self.tts_generator.__aenter__()
            
            logger.info("Newsletter processor initialized with all services")
            return self
            
        except Exception as e:
            logger.error(f"Failed to initialize newsletter processor: {e}")
            await self.__aexit__(type(e), e, e.__traceback__)
            raise ProcessingError(f"Service initialization failed: {e}")
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup all services."""
        try:
            if self.tts_generator:
                await self.tts_generator.__aexit__(exc_type, exc_val, exc_tb)
            if self.llm_summarizer:
                await self.llm_summarizer.__aexit__(exc_type, exc_val, exc_tb)
            if self.content_extractor:
                await self.content_extractor.__aexit__(exc_type, exc_val, exc_tb)
        except Exception as e:
            logger.error(f"Error during newsletter processor cleanup: {e}")
    
    async def process_newsletter_from_url(
        self,
        url: str,
        user_id: Optional[str] = None,
        processing_options: Optional[Dict[str, Any]] = None
    ) -> Newsletter:
        """
        Process newsletter from URL through complete pipeline.
        
        Args:
            url: Newsletter URL to process
            user_id: Optional user ID for tracking
            processing_options: Optional processing parameters
            
        Returns:
            Newsletter model with processing status
            
        Raises:
            ProcessingError: If processing fails
            ValidationError: If URL is invalid
        """
        start_time = asyncio.get_event_loop().time()
        
        async with get_db_session() as db:
            # Create newsletter record
            newsletter = Newsletter.from_url(url, user_id=user_id)
            db.add(newsletter)
            await db.commit()
            await db.refresh(newsletter)
            
            newsletter_id = newsletter.id  # Capture ID for error logging
            
            logger.info(f"Starting newsletter processing: {newsletter_id} from {url}")
            
            try:
                # Process through pipeline
                await self._process_newsletter_pipeline(newsletter, db, processing_options)
                
                processing_time = asyncio.get_event_loop().time() - start_time
                record_processing_time("newsletter_processing", processing_time)
                increment_counter("newsletters_processed_total")
                
                logger.info(
                    f"Newsletter processing completed: {newsletter_id}, "
                    f"status: {newsletter.status}, "
                    f"processed in {processing_time:.2f}s"
                )
                
                return newsletter
                
            except Exception as e:
                # Mark as failed and re-raise
                newsletter.update_status(NewsletterStatus.FAILED)
                newsletter.set_error(str(e))
                await db.commit()
                
                increment_counter("newsletters_failed_total")
                logger.error(f"Newsletter processing failed: {newsletter_id}, error: {e}")
                raise
    
    async def process_newsletter_from_text(
        self,
        content: str,
        title: Optional[str] = None,
        content_type: str = "text",
        user_id: Optional[str] = None,
        processing_options: Optional[Dict[str, Any]] = None
    ) -> Newsletter:
        """
        Process newsletter from raw text/HTML/markdown content.
        
        Args:
            content: Newsletter content
            title: Newsletter title
            content_type: Content type (text, html, markdown)
            user_id: Optional user ID for tracking
            processing_options: Optional processing parameters
            
        Returns:
            Newsletter model with processing status
            
        Raises:
            ProcessingError: If processing fails
            ValidationError: If content is invalid
        """
        start_time = asyncio.get_event_loop().time()
        
        async with get_db_session() as db:
            # Create newsletter record
            newsletter = Newsletter.from_text(
                content=content,
                title=title,
                content_type=content_type,
                user_id=user_id
            )
            db.add(newsletter)
            await db.commit()
            await db.refresh(newsletter)
            
            logger.info(f"Starting newsletter processing: {newsletter.id} from text content")
            
            try:
                # Process through pipeline
                await self._process_newsletter_pipeline(newsletter, db, processing_options)
                
                processing_time = asyncio.get_event_loop().time() - start_time
                record_processing_time("newsletter_processing", processing_time)
                increment_counter("newsletters_processed_total")
                
                logger.info(
                    f"Newsletter processing completed: {newsletter.id}, "
                    f"status: {newsletter.status}, "
                    f"processed in {processing_time:.2f}s"
                )
                
                return newsletter
                
            except Exception as e:
                # Mark as failed and re-raise
                newsletter.update_status(NewsletterStatus.FAILED)
                newsletter.set_error(str(e))
                await db.commit()
                
                increment_counter("newsletters_failed_total")
                logger.error(f"Newsletter processing failed: {newsletter.id}, error: {e}")
                raise
    
    async def retry_failed_processing(self, newsletter_id: str) -> Newsletter:
        """
        Retry processing for a failed newsletter.
        
        Args:
            newsletter_id: Newsletter ID to retry
            
        Returns:
            Newsletter model with updated status
            
        Raises:
            ProcessingError: If retry fails
            ValidationError: If newsletter not found or not retryable
        """
        async with get_db_session() as db:
            # Get newsletter
            newsletter = await db.get(Newsletter, newsletter_id)
            if not newsletter:
                raise ValidationError(f"Newsletter not found: {newsletter_id}")
            
            if newsletter.status != NewsletterStatus.FAILED.value:
                raise ValidationError(f"Newsletter {newsletter_id} is not in failed state")
            
            logger.info(f"Retrying failed newsletter processing: {newsletter.id}")
            
            # Reset status and clear error
            newsletter.update_status(NewsletterStatus.PENDING)
            newsletter.clear_error()
            await db.commit()
            
            try:
                # Process through pipeline
                await self._process_newsletter_pipeline(newsletter, db)
                
                increment_counter("newsletters_retried_total")
                logger.info(f"Newsletter retry completed: {newsletter.id}, status: {newsletter.status}")
                
                return newsletter
                
            except Exception as e:
                # Mark as failed again
                newsletter.update_status(NewsletterStatus.FAILED)
                newsletter.set_error(str(e))
                await db.commit()
                
                increment_counter("newsletters_retry_failed_total")
                logger.error(f"Newsletter retry failed: {newsletter.id}, error: {e}")
                raise
    
    async def _process_newsletter_pipeline(
        self,
        newsletter: Newsletter,
        db: AsyncSession,
        processing_options: Optional[Dict[str, Any]] = None
    ) -> None:
        """Internal method to run the complete processing pipeline."""
        options = processing_options or {}
        
        # Capture attributes to avoid lazy loading issues after commit
        newsletter_id = newsletter.id
        newsletter_url = newsletter.url
        newsletter_content = newsletter.content
        
        try:
            # Step 1: Content Extraction
            logger.info(f"Step 1: Extracting content for newsletter {newsletter_id}")
            newsletter.update_status(NewsletterStatus.EXTRACTING)
            await db.commit()
            await db.refresh(newsletter)  # Refresh to avoid detached instance issues
            
            if newsletter_url:
                extracted = await self.content_extractor.extract_from_url(newsletter_url)
            else:
                extracted = await self.content_extractor.extract_from_text(
                    newsletter_content,
                    content_type="text"
                )
            
            # Update newsletter with extracted content
            newsletter.set_extracted_content(extracted.content)
            if extracted.title and not newsletter.title:
                newsletter.title = extracted.title
            await db.commit()
            await db.refresh(newsletter)
            
            # Step 2: LLM Summarization
            logger.info(f"Step 2: Summarizing content for newsletter {newsletter_id}")
            newsletter.update_status(NewsletterStatus.SUMMARIZING)
            await db.commit()
            await db.refresh(newsletter)
            
            summary_response = await self.llm_summarizer.summarize_newsletter(
                content=extracted.content,
                title=extracted.title,
                style=options.get("style", "conversational"),
                target_length=options.get("target_length", "medium"),
                focus_areas=options.get("focus_areas")
            )
            
            # Create episode record
            episode = Episode.from_newsletter_summary(
                newsletter_id=newsletter.id,
                title=summary_response.title,
                summary_text=summary_response.summary,
                description=f"Podcast episode generated from newsletter: {newsletter.title}"
            )
            
            # Set AI provider info
            episode.set_ai_providers(
                llm_provider=summary_response.provider,
                llm_model=summary_response.model
            )
            
            db.add(episode)
            await db.commit()
            await db.refresh(episode)
            
            # Step 3: TTS Generation
            logger.info(f"Step 3: Generating audio for episode {episode.id}")
            newsletter.update_status(NewsletterStatus.GENERATING_AUDIO) 
            episode.update_status(EpisodeStatus.GENERATING)
            await db.commit()
            
            tts_response = await self.tts_generator.generate_speech(
                text=summary_response.summary,
                voice=options.get("voice"),
                speed=options.get("speed", 1.0),
                pitch=options.get("pitch", 1.0),
                output_format=options.get("output_format", "mp3"),
                quality=options.get("quality", "standard")
            )
            
            # Update episode with audio info
            episode.set_audio_info(
                audio_file_path=tts_response.audio_file_path,
                duration_seconds=tts_response.duration_seconds,
                file_size_bytes=tts_response.file_size_bytes
            )
            
            episode.set_ai_providers(
                tts_provider=tts_response.provider,
                tts_voice=tts_response.voice
            )
            
            episode.update_status(EpisodeStatus.COMPLETED)
            await db.commit()
            await db.refresh(episode)
            
            # Capture episode attributes before accessing newsletter
            episode_id_final = episode.id
            episode_duration = episode.formatted_duration
            
            # Step 4: Mark newsletter as completed
            logger.info(f"Step 4: Completing processing for newsletter {newsletter_id}")
            newsletter.update_status(NewsletterStatus.COMPLETED)
            newsletter.episode_id = episode_id_final
            await db.commit()
            await db.refresh(newsletter)
            
            increment_counter("episodes_generated_total")
            logger.info(
                f"Pipeline completed successfully: newsletter {newsletter_id}, "
                f"episode {episode_id_final}, audio duration {episode_duration}"
            )
            
        except Exception as e:
            logger.error(f"Pipeline step failed for newsletter {newsletter_id}: {e}")
            raise ProcessingError(f"Processing pipeline failed: {e}")
    
    async def get_processing_status(self, newsletter_id: str) -> Dict[str, Any]:
        """
        Get detailed processing status for a newsletter.
        
        Args:
            newsletter_id: Newsletter ID to check
            
        Returns:
            Dictionary with processing status and details
            
        Raises:
            ValidationError: If newsletter not found
        """
        async with get_db_session() as db:
            newsletter = await db.get(Newsletter, newsletter_id)
            if not newsletter:
                raise ValidationError(f"Newsletter not found: {newsletter_id}")
            
            status_info = {
                "newsletter_id": newsletter.id,
                "status": newsletter.status,
                "title": newsletter.title,
                "created_at": newsletter.created_at.isoformat(),
                "updated_at": newsletter.updated_at.isoformat(),
                "word_count": newsletter.word_count,
                "error_message": newsletter.error_message,
                "episode": None
            }
            
            # Add episode info if available
            if newsletter.episode_id:
                episode = await db.get(Episode, newsletter.episode_id)
                if episode:
                    status_info["episode"] = {
                        "id": episode.id,
                        "title": episode.title,
                        "status": episode.status,
                        "duration": episode.formatted_duration,
                        "file_size": episode.formatted_file_size,
                        "audio_file_path": episode.audio_file_path,
                        "llm_provider": episode.llm_provider,
                        "tts_provider": episode.tts_provider
                    }
            
            return status_info
    
    async def health_check(self) -> Dict[str, bool]:
        """
        Check health of all processing services.
        
        Returns:
            Dictionary with service health status
        """
        health_status = {
            "content_extractor": False,
            "llm_summarizer": False,
            "tts_generator": False
        }
        
        try:
            if self.content_extractor:
                # Content extractor doesn't have health check, assume healthy if initialized
                health_status["content_extractor"] = True
            
            if self.llm_summarizer:
                health_status["llm_summarizer"] = await self.llm_summarizer.health_check()
            
            if self.tts_generator:
                health_status["tts_generator"] = await self.tts_generator.health_check()
                
        except Exception as e:
            logger.error(f"Health check error: {e}")
        
        return health_status
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about configured services."""
        info = {
            "content_extractor": {
                "enabled": self.content_extractor is not None
            },
            "llm_summarizer": {},
            "tts_generator": {}
        }
        
        if self.llm_summarizer:
            info["llm_summarizer"] = self.llm_summarizer.get_provider_info()
        
        if self.tts_generator:
            info["tts_generator"] = self.tts_generator.get_provider_info()
        
        return info