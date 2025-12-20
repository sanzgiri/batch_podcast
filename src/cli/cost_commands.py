"""
Cost reporting CLI commands.

Provides commands to view and analyze processing costs.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.lib.config import get_config
from src.lib.database import get_db_session
from src.models import Episode, Newsletter

console = Console()


@click.group()
def costs():
    """View processing costs and usage statistics."""
    pass


@costs.command()
@click.option("--newsletter", help="Filter by newsletter profile ID")
@click.option("--from", "from_date", help="Start date (YYYY-MM-DD)")
@click.option("--to", "to_date", help="End date (YYYY-MM-DD)")
@click.option("--limit", default=10, help="Number of episodes to show")
def summary(newsletter, from_date, to_date, limit):
    """Show cost summary."""
    asyncio.run(_show_cost_summary(newsletter, from_date, to_date, limit))


@costs.command()
@click.argument("episode_id")
def episode(episode_id):
    """Show detailed cost breakdown for an episode."""
    asyncio.run(_show_episode_costs(episode_id))


@costs.command()
def totals():
    """Show total costs across all processing."""
    asyncio.run(_show_total_costs())


async def _show_cost_summary(
    newsletter_profile_id: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    limit: int
):
    """Show cost summary table."""
    async with get_db_session() as db:
        # Build query
        query = select(Episode).join(Newsletter)

        if newsletter_profile_id:
            query = query.where(Newsletter.newsletter_profile_id == newsletter_profile_id)

        if from_date:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.where(Episode.created_at >= start_dt)

        if to_date:
            end_dt = datetime.strptime(to_date, "%Y-%m-%d")
            query = query.where(Episode.created_at <= end_dt)

        query = query.order_by(Episode.created_at.desc()).limit(limit)

        result = await db.execute(query)
        episodes = result.scalars().all()

        if not episodes:
            console.print("[yellow]No episodes found matching criteria.[/yellow]")
            return

        # Create table
        table = Table(title="Processing Costs")
        table.add_column("Date", style="cyan")
        table.add_column("Title", style="white", max_width=40)
        table.add_column("LLM Tokens", justify="right", style="blue")
        table.add_column("LLM Cost", justify="right", style="green")
        table.add_column("TTS Chars", justify="right", style="blue")
        table.add_column("TTS Cost", justify="right", style="green")
        table.add_column("Total Cost", justify="right", style="bold green")

        total_llm_cost = 0.0
        total_tts_cost = 0.0
        total_cost = 0.0

        for ep in episodes:
            llm_cost = ep.llm_cost or 0.0
            tts_cost = ep.tts_cost or 0.0
            ep_total_cost = ep.total_cost or 0.0

            total_llm_cost += llm_cost
            total_tts_cost += tts_cost
            total_cost += ep_total_cost

            table.add_row(
                ep.created_at.strftime("%Y-%m-%d"),
                ep.title[:37] + "..." if len(ep.title) > 40 else ep.title,
                f"{ep.llm_total_tokens or 0:,}",
                f"${llm_cost:.4f}",
                f"{ep.tts_characters or 0:,}",
                f"${tts_cost:.4f}",
                f"${ep_total_cost:.4f}"
            )

        # Add totals row
        table.add_section()
        table.add_row(
            "",
            f"[bold]TOTAL ({len(episodes)} episodes)[/bold]",
            "",
            f"[bold]${total_llm_cost:.4f}[/bold]",
            "",
            f"[bold]${total_tts_cost:.4f}[/bold]",
            f"[bold]${total_cost:.4f}[/bold]"
        )

        console.print(table)


async def _show_episode_costs(episode_id: str):
    """Show detailed cost breakdown for an episode."""
    async with get_db_session() as db:
        episode = await db.get(Episode, episode_id)

        if not episode:
            console.print(f"[red]Episode not found: {episode_id}[/red]")
            return

        # Create details table
        table = Table(title=f"Cost Breakdown: {episode.title}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Episode ID", episode.id)
        table.add_row("Created", episode.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        table.add_row("", "")

        # LLM costs
        table.add_row("[bold]LLM Processing[/bold]", "")
        table.add_row("  Provider", episode.llm_provider or "N/A")
        table.add_row("  Model", episode.llm_model or "N/A")
        table.add_row("  Input Tokens", f"{episode.llm_input_tokens or 0:,}")
        table.add_row("  Output Tokens", f"{episode.llm_output_tokens or 0:,}")
        table.add_row("  Total Tokens", f"{episode.llm_total_tokens or 0:,}")
        table.add_row("  [green]LLM Cost[/green]", f"[green]${episode.llm_cost or 0.0:.4f}[/green]")
        table.add_row("", "")

        # TTS costs
        table.add_row("[bold]TTS Processing[/bold]", "")
        table.add_row("  Provider", episode.tts_provider or "N/A")
        table.add_row("  Voice", episode.tts_voice or "N/A")
        table.add_row("  Characters", f"{episode.tts_characters or 0:,}")
        table.add_row("  [green]TTS Cost[/green]", f"[green]${episode.tts_cost or 0.0:.4f}[/green]")
        table.add_row("", "")

        # Total
        table.add_row("[bold green]Total Cost[/bold green]", f"[bold green]${episode.total_cost or 0.0:.4f}[/bold green]")

        console.print(table)


async def _show_total_costs():
    """Show total costs across all processing."""
    async with get_db_session() as db:
        # Get total costs
        result = await db.execute(
            select(
                func.count(Episode.id).label("count"),
                func.sum(Episode.llm_cost).label("total_llm"),
                func.sum(Episode.tts_cost).label("total_tts"),
                func.sum(Episode.total_cost).label("total"),
                func.sum(Episode.llm_total_tokens).label("total_tokens"),
                func.sum(Episode.tts_characters).label("total_chars")
            ).where(Episode.status == "completed")
        )

        row = result.one()

        # Create summary
        table = Table(title="Overall Cost Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Total Episodes Processed", f"{row.count or 0:,}")
        table.add_row("", "")
        table.add_row("Total LLM Tokens", f"{int(row.total_tokens or 0):,}")
        table.add_row("Total LLM Cost", f"[green]${row.total_llm or 0.0:.4f}[/green]")
        table.add_row("", "")
        table.add_row("Total TTS Characters", f"{int(row.total_chars or 0):,}")
        table.add_row("Total TTS Cost", f"[green]${row.total_tts or 0.0:.4f}[/green]")
        table.add_row("", "")
        table.add_row("[bold]Total Cost[/bold]", f"[bold green]${row.total or 0.0:.4f}[/bold green]")

        # Calculate averages
        if row.count and row.count > 0:
            avg_cost = (row.total or 0.0) / row.count
            table.add_row("Average Cost per Episode", f"${avg_cost:.4f}")

        console.print(table)

        # Get costs by newsletter
        console.print("\n[bold]Costs by Newsletter:[/bold]")
        newsletter_result = await db.execute(
            select(
                Newsletter.newsletter_profile_id,
                func.count(Episode.id).label("count"),
                func.sum(Episode.total_cost).label("total")
            )
            .join(Episode, Newsletter.id == Episode.newsletter_id)
            .where(Episode.status == "completed")
            .group_by(Newsletter.newsletter_profile_id)
            .order_by(func.sum(Episode.total_cost).desc())
        )

        newsletter_table = Table()
        newsletter_table.add_column("Newsletter", style="cyan")
        newsletter_table.add_column("Episodes", justify="right", style="white")
        newsletter_table.add_column("Total Cost", justify="right", style="green")

        for row in newsletter_result:
            profile_id = row.newsletter_profile_id or "uncategorized"
            newsletter_table.add_row(
                profile_id,
                f"{row.count:,}",
                f"${row.total or 0.0:.4f}"
            )

        console.print(newsletter_table)
