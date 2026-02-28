"""Gradio UI for browsing and playing podcast episodes."""

import sqlite3
from pathlib import Path
from typing import Optional

import gradio as gr

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "newsletter_podcast_dev.db"
AUDIO_BASE_DIR = PROJECT_ROOT / "data" / "audio"


def get_db_path() -> Path:
    """Get the database path, checking common locations."""
    if DEFAULT_DB_PATH.exists():
        return DEFAULT_DB_PATH
    # Also check for alternate name
    alt = PROJECT_ROOT / "data" / "newsletter_podcast_local.db"
    if alt.exists():
        return alt
    return DEFAULT_DB_PATH


def get_episodes() -> list[dict]:
    """Fetch all completed episodes from the database."""
    db_path = get_db_path()
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT e.id, e.title, e.description, e.summary_text,
                   e.audio_file_path, e.duration_seconds, e.file_size_bytes,
                   e.status, e.llm_provider, e.llm_model,
                   e.tts_provider, e.tts_voice,
                   e.llm_input_tokens, e.llm_output_tokens, e.llm_cost,
                   e.tts_characters, e.tts_cost, e.total_cost,
                   e.created_at,
                   n.title as newsletter_title, n.url as newsletter_url,
                   n.newsletter_profile_id, n.issue_number
            FROM episodes e
            LEFT JOIN newsletters n ON e.newsletter_id = n.id
            ORDER BY e.created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def format_duration(seconds: Optional[int]) -> str:
    """Format seconds as MM:SS or HH:MM:SS."""
    if seconds is None:
        return "--:--"
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def format_size(size_bytes: Optional[int]) -> str:
    """Format bytes as human-readable size."""
    if size_bytes is None:
        return "--"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_cost(cost: Optional[float]) -> str:
    """Format cost as dollar amount."""
    if cost is None or cost == 0:
        return "free"
    return f"${cost:.4f}"


def resolve_audio_path(audio_file_path: Optional[str]) -> Optional[str]:
    """Resolve an audio file path to an absolute path."""
    if not audio_file_path:
        return None

    path = Path(audio_file_path)

    # Already absolute and exists
    if path.is_absolute() and path.exists():
        return str(path)

    # Relative to project root
    resolved = PROJECT_ROOT / path
    if resolved.exists():
        return str(resolved)

    # Relative to audio dir
    resolved = AUDIO_BASE_DIR / path
    if resolved.exists():
        return str(resolved)

    # Try with data/audio prefix
    resolved = PROJECT_ROOT / "data" / "audio" / path
    if resolved.exists():
        return str(resolved)

    return None


def build_episodes_table(episodes: list[dict]) -> list[list[str]]:
    """Build table data from episodes."""
    rows = []
    for ep in episodes:
        rows.append([
            ep.get("title", "Untitled"),
            ep.get("status", "unknown"),
            format_duration(ep.get("duration_seconds")),
            (ep.get("created_at") or "")[:10],
            format_cost(ep.get("total_cost")),
        ])
    return rows


def get_episode_details(episodes: list[dict], index: int) -> tuple:
    """Get details for a selected episode. Returns (details_md, audio_path, summary)."""
    if not episodes or index < 0 or index >= len(episodes):
        return "No episode selected.", None, ""

    ep = episodes[index]

    llm_info = f"{ep.get('llm_provider', '?')}/{ep.get('llm_model', '?')}"
    tts_info = f"{ep.get('tts_provider', '?')}"
    if ep.get("tts_voice"):
        tts_info += f" ({ep['tts_voice']})"

    details = f"""### {ep.get('title', 'Untitled')}

| | |
|---|---|
| **Status** | {ep.get('status', 'unknown')} |
| **Duration** | {format_duration(ep.get('duration_seconds'))} |
| **File Size** | {format_size(ep.get('file_size_bytes'))} |
| **LLM** | {llm_info} |
| **TTS** | {tts_info} |
| **LLM Tokens** | {ep.get('llm_input_tokens', 0) or 0} in / {ep.get('llm_output_tokens', 0) or 0} out |
| **LLM Cost** | {format_cost(ep.get('llm_cost'))} |
| **TTS Cost** | {format_cost(ep.get('tts_cost'))} |
| **Total Cost** | {format_cost(ep.get('total_cost'))} |
| **Created** | {ep.get('created_at', '')} |
"""

    if ep.get("newsletter_url"):
        details += f"| **Source** | [{ep['newsletter_url']}]({ep['newsletter_url']}) |\n"
    if ep.get("newsletter_profile_id"):
        profile = ep["newsletter_profile_id"]
        if ep.get("issue_number"):
            profile += f" #{ep['issue_number']}"
        details += f"| **Newsletter** | {profile} |\n"

    audio_path = resolve_audio_path(ep.get("audio_file_path"))
    summary = ep.get("summary_text", "")

    return details, audio_path, summary


def create_app() -> gr.Blocks:
    """Create the Gradio app."""

    # Load episodes once at startup; refresh button reloads
    episodes_state: list[dict] = []

    def refresh_episodes():
        nonlocal episodes_state
        episodes_state = get_episodes()
        table_data = build_episodes_table(episodes_state)
        if not table_data:
            table_data = [["No episodes found", "", "", "", ""]]
        return table_data

    def on_select(evt: gr.SelectData):
        row_index = evt.index[0]
        details, audio, summary = get_episode_details(episodes_state, row_index)
        return details, audio, summary

    with gr.Blocks(title="Newsletter Podcast Generator") as app:
        gr.Markdown("# Newsletter Podcast Generator")

        with gr.Row():
            refresh_btn = gr.Button("Refresh Episodes", variant="secondary", scale=0)

        episodes_table = gr.Dataframe(
            headers=["Title", "Status", "Duration", "Date", "Cost"],
            datatype=["str", "str", "str", "str", "str"],
            interactive=False,
            label="Episodes",
        )

        with gr.Row():
            with gr.Column(scale=1):
                details_md = gr.Markdown("Select an episode from the table above.")
                audio_player = gr.Audio(
                    label="Episode Audio",
                    type="filepath",
                    interactive=False,
                )
            with gr.Column(scale=1):
                summary_text = gr.Textbox(
                    label="Podcast Script",
                    lines=20,
                    interactive=False,
                )

        # Wire up events
        refresh_btn.click(fn=refresh_episodes, outputs=[episodes_table])
        episodes_table.select(
            fn=on_select,
            outputs=[details_md, audio_player, summary_text],
        )

        # Load episodes on startup
        app.load(fn=refresh_episodes, outputs=[episodes_table])

    return app


if __name__ == "__main__":
    app = create_app()
    app.launch(server_name="0.0.0.0", server_port=7860)
