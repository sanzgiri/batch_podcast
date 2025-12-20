"""
CLI Commands for Newsletter Podcast Generator.

This module provides command-line interface for newsletter processing,
status monitoring, and service management.
"""

import asyncio
import sys
from typing import Optional, List
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

from src.lib.config import get_config
from src.lib.logging import get_logger
from src.services import NewsletterProcessor


logger = get_logger(__name__)
console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="batch-podcast")
def cli():
    """Newsletter Podcast Generator CLI - Convert newsletters to podcast episodes."""
    pass


@cli.command()
@click.argument("url")
@click.option("--newsletter", "newsletter_profile_id", help="Newsletter profile ID (e.g., 'the-batch')")
@click.option("--user-id", help="User ID for tracking")
@click.option("--style", default=None,
              type=click.Choice(["conversational", "formal", "casual"]),
              help="Summary style (overrides profile setting)")
@click.option("--length", "target_length", default=None,
              type=click.Choice(["short", "medium", "long"]),
              help="Target summary length (overrides profile setting)")
@click.option("--voice", help="TTS voice (provider-specific)")
@click.option("--speed", default=1.0, type=float, help="Speech speed (0.5-2.0)")
@click.option("--pitch", default=1.0, type=float, help="Speech pitch (0.5-2.0)")
@click.option("--format", "output_format", default="mp3",
              type=click.Choice(["mp3", "wav"]),
              help="Audio output format")
@click.option("--quality", default="standard",
              type=click.Choice(["standard", "high"]),
              help="Audio quality")
@click.option("--focus", "focus_areas", multiple=True,
              help="Topics to emphasize (can be used multiple times)")
@click.option("--wait", is_flag=True, help="Wait for processing to complete")
def process_url(
    url: str,
    newsletter_profile_id: Optional[str],
    user_id: Optional[str],
    style: Optional[str],
    target_length: Optional[str],
    voice: Optional[str],
    speed: float,
    pitch: float,
    output_format: str,
    quality: str,
    focus_areas: tuple,
    wait: bool
):
    """Process a newsletter from URL."""
    console.print(f"[bold blue]Processing newsletter from URL:[/bold blue] {url}")
    
    # Validate parameters
    if not (0.5 <= speed <= 2.0):
        console.print("[red]Error: Speed must be between 0.5 and 2.0[/red]")
        sys.exit(1)
    
    if not (0.5 <= pitch <= 2.0):
        console.print("[red]Error: Pitch must be between 0.5 and 2.0[/red]")
        sys.exit(1)
    
    # Prepare processing options (only include explicitly set values)
    processing_options = {
        "voice": voice,
        "speed": speed,
        "pitch": pitch,
        "output_format": output_format,
        "quality": quality,
    }

    # Only add style and length if explicitly set (don't override profile defaults)
    if style is not None:
        processing_options["style"] = style
    if target_length is not None:
        processing_options["target_length"] = target_length
    if focus_areas:
        processing_options["focus_areas"] = list(focus_areas)

    # Run processing
    try:
        newsletter = asyncio.run(_process_newsletter_url_async(
            url, user_id, newsletter_profile_id, processing_options, wait
        ))
        
        if newsletter:
            _display_newsletter_result(newsletter)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        console.print("[red]" + traceback.format_exc() + "[/red]")
        sys.exit(1)


@cli.command()
@click.argument("content_file", type=click.Path(exists=True, path_type=Path))
@click.option("--title", help="Newsletter title")
@click.option("--content-type", default="text",
              type=click.Choice(["text", "html", "markdown"]),
              help="Content type")
@click.option("--user-id", help="User ID for tracking")
@click.option("--style", default="conversational",
              type=click.Choice(["conversational", "formal", "casual"]),
              help="Summary style")
@click.option("--length", "target_length", default="medium",
              type=click.Choice(["short", "medium", "long"]),
              help="Target summary length")
@click.option("--voice", help="TTS voice (provider-specific)")
@click.option("--speed", default=1.0, type=float, help="Speech speed (0.5-2.0)")
@click.option("--pitch", default=1.0, type=float, help="Speech pitch (0.5-2.0)")
@click.option("--format", "output_format", default="mp3",
              type=click.Choice(["mp3", "wav"]),
              help="Audio output format")
@click.option("--quality", default="standard",
              type=click.Choice(["standard", "high"]),
              help="Audio quality")
@click.option("--focus", "focus_areas", multiple=True,
              help="Topics to emphasize (can be used multiple times)")
@click.option("--wait", is_flag=True, help="Wait for processing to complete")
def process_file(
    content_file: Path,
    title: Optional[str],
    content_type: str,
    user_id: Optional[str],
    style: str,
    target_length: str,
    voice: Optional[str],
    speed: float,
    pitch: float,
    output_format: str,
    quality: str,
    focus_areas: tuple,
    wait: bool
):
    """Process a newsletter from text file."""
    console.print(f"[bold blue]Processing newsletter from file:[/bold blue] {content_file}")
    
    # Read file content
    try:
        content = content_file.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[red]Error reading file: {e}[/red]")
        sys.exit(1)
    
    # Validate parameters
    if not (0.5 <= speed <= 2.0):
        console.print("[red]Error: Speed must be between 0.5 and 2.0[/red]")
        sys.exit(1)
    
    if not (0.5 <= pitch <= 2.0):
        console.print("[red]Error: Pitch must be between 0.5 and 2.0[/red]")
        sys.exit(1)
    
    # Prepare processing options
    processing_options = {
        "style": style,
        "target_length": target_length,
        "voice": voice,
        "speed": speed,
        "pitch": pitch,
        "output_format": output_format,
        "quality": quality,
        "focus_areas": list(focus_areas) if focus_areas else None
    }
    
    # Run processing
    try:
        newsletter = asyncio.run(_process_newsletter_text_async(
            content, title, content_type, user_id, processing_options, wait
        ))
        
        if newsletter:
            _display_newsletter_result(newsletter)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("newsletter_id")
def status(newsletter_id: str):
    """Check processing status of a newsletter."""
    console.print(f"[bold blue]Checking status for newsletter:[/bold blue] {newsletter_id}")
    
    try:
        status_info = asyncio.run(_get_newsletter_status_async(newsletter_id))
        _display_newsletter_status(status_info)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("newsletter_id")
@click.option("--wait", is_flag=True, help="Wait for retry to complete")
def retry(newsletter_id: str, wait: bool):
    """Retry processing for a failed newsletter."""
    console.print(f"[bold blue]Retrying newsletter processing:[/bold blue] {newsletter_id}")
    
    try:
        newsletter = asyncio.run(_retry_newsletter_async(newsletter_id, wait))
        
        if newsletter:
            _display_newsletter_result(newsletter)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
def health():
    """Check health of processing services."""
    console.print("[bold blue]Checking service health...[/bold blue]")
    
    try:
        health_status = asyncio.run(_check_health_async())
        _display_health_status(health_status)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
def service_info():
    """Display information about configured services."""
    console.print("[bold blue]Service Configuration:[/bold blue]")
    
    try:
        service_info = asyncio.run(_get_service_info_async())
        _display_service_info(service_info)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
def voices():
    """List available TTS voices."""
    console.print("[bold blue]Available TTS Voices:[/bold blue]")
    
    try:
        voices = asyncio.run(_get_available_voices_async())
        _display_available_voices(voices)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


# Async helper functions

async def _process_newsletter_url_async(
    url: str,
    user_id: Optional[str],
    newsletter_profile_id: Optional[str],
    processing_options: dict,
    wait: bool
):
    """Process newsletter from URL asynchronously."""
    config = get_config()

    async with NewsletterProcessor(config) as processor:
        if wait:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Processing newsletter...", total=None)

                newsletter = await processor.process_newsletter_from_url(
                    url=url,
                    user_id=user_id,
                    newsletter_profile_id=newsletter_profile_id,
                    processing_options=processing_options
                )

                progress.update(task, description="Processing completed!")
                return newsletter
        else:
            # Start processing (non-blocking in real implementation)
            newsletter = await processor.process_newsletter_from_url(
                url=url,
                user_id=user_id,
                newsletter_profile_id=newsletter_profile_id,
                processing_options=processing_options
            )

            console.print(f"[green]Newsletter submitted for processing: {newsletter.id}[/green]")
            console.print("Use 'batch-podcast status <id>' to check progress")
            return None


async def _process_newsletter_text_async(
    content: str,
    title: Optional[str],
    content_type: str,
    user_id: Optional[str],
    processing_options: dict,
    wait: bool
):
    """Process newsletter from text asynchronously."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        if wait:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Processing newsletter...", total=None)
                
                newsletter = await processor.process_newsletter_from_text(
                    content=content,
                    title=title,
                    content_type=content_type,
                    user_id=user_id,
                    processing_options=processing_options
                )
                
                progress.update(task, description="Processing completed!")
                return newsletter
        else:
            newsletter = await processor.process_newsletter_from_text(
                content=content,
                title=title,
                content_type=content_type,
                user_id=user_id,
                processing_options=processing_options
            )
            
            console.print(f"[green]Newsletter submitted for processing: {newsletter.id}[/green]")
            console.print("Use 'batch-podcast status <id>' to check progress")
            return None


async def _get_newsletter_status_async(newsletter_id: str):
    """Get newsletter status asynchronously."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        return await processor.get_processing_status(newsletter_id)


async def _retry_newsletter_async(newsletter_id: str, wait: bool):
    """Retry newsletter processing asynchronously."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        if wait:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Retrying newsletter processing...", total=None)
                
                newsletter = await processor.retry_failed_processing(newsletter_id)
                
                progress.update(task, description="Retry completed!")
                return newsletter
        else:
            newsletter = await processor.retry_failed_processing(newsletter_id)
            console.print(f"[green]Newsletter retry started: {newsletter.id}[/green]")
            return None


async def _check_health_async():
    """Check service health asynchronously."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        return await processor.health_check()


async def _get_service_info_async():
    """Get service info asynchronously."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        return processor.get_service_info()


async def _get_available_voices_async():
    """Get available voices asynchronously."""
    config = get_config()
    
    async with NewsletterProcessor(config) as processor:
        return processor.tts_generator.get_available_voices()


# Display helper functions

def _display_newsletter_result(newsletter):
    """Display newsletter processing result."""
    # Create a panel with newsletter info
    info_text = f"""
[bold]Newsletter ID:[/bold] {newsletter.id}
[bold]Title:[/bold] {newsletter.title or 'Untitled'}
[bold]Status:[/bold] {newsletter.status}
[bold]Word Count:[/bold] {newsletter.word_count or 'N/A'}
[bold]Created:[/bold] {newsletter.created_at.strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    if hasattr(newsletter, 'episode') and newsletter.episode:
        episode = newsletter.episode
        info_text += f"""
[bold]Episode ID:[/bold] {episode.id}
[bold]Duration:[/bold] {episode.formatted_duration or 'N/A'}
[bold]Audio File:[/bold] {episode.audio_file_path or 'N/A'}
"""
    
    console.print(Panel(info_text, title="Newsletter Processing Result", expand=False))


def _display_newsletter_status(status_info):
    """Display newsletter status information."""
    info_text = f"""
[bold]Newsletter ID:[/bold] {status_info['newsletter_id']}
[bold]Title:[/bold] {status_info['title'] or 'Untitled'}
[bold]Status:[/bold] {status_info['status']}
[bold]Word Count:[/bold] {status_info['word_count'] or 'N/A'}
[bold]Created:[/bold] {status_info['created_at']}
[bold]Updated:[/bold] {status_info['updated_at']}
"""
    
    if status_info.get('error_message'):
        info_text += f"\n[bold red]Error:[/bold red] {status_info['error_message']}"
    
    if status_info.get('episode'):
        episode = status_info['episode']
        info_text += f"""

[bold]Episode Information:[/bold]
[bold]Episode ID:[/bold] {episode['id']}
[bold]Status:[/bold] {episode['status']}
[bold]Duration:[/bold] {episode['duration'] or 'N/A'}
[bold]File Size:[/bold] {episode['file_size'] or 'N/A'}
[bold]LLM Provider:[/bold] {episode['llm_provider'] or 'N/A'}
[bold]TTS Provider:[/bold] {episode['tts_provider'] or 'N/A'}
"""
    
    console.print(Panel(info_text, title="Newsletter Status", expand=False))


def _display_health_status(health_status):
    """Display service health status."""
    table = Table(title="Service Health Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="magenta")
    
    for service, is_healthy in health_status.items():
        status = "[green]Healthy[/green]" if is_healthy else "[red]Unhealthy[/red]"
        table.add_row(service.replace("_", " ").title(), status)
    
    console.print(table)


def _display_service_info(service_info):
    """Display service configuration information."""
    for service_name, info in service_info.items():
        service_title = service_name.replace("_", " ").title()
        
        if isinstance(info, dict):
            info_text = ""
            for key, value in info.items():
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value)
                info_text += f"[bold]{key.replace('_', ' ').title()}:[/bold] {value}\n"
            
            console.print(Panel(info_text.strip(), title=service_title, expand=False))
        else:
            console.print(f"[bold]{service_title}:[/bold] {info}")


def _display_available_voices(voices):
    """Display available TTS voices."""
    if voices:
        table = Table(title="Available TTS Voices")
        table.add_column("Voice", style="cyan")
        
        for voice in voices:
            table.add_row(voice)
        
        console.print(table)
    else:
        console.print("[yellow]No voices available[/yellow]")


# Add cost commands subgroup
from src.cli.cost_commands import costs
cli.add_command(costs)


if __name__ == "__main__":
    cli()