"""
Database migration to add cost tracking fields.

Adds cost tracking columns to episodes table.
"""

import sqlite3
from pathlib import Path


def migrate():
    """Run migration to add cost tracking columns."""
    # Find database file
    db_path = Path("data/newsletter_podcast_local.db")

    if not db_path.exists():
        print("Looking for dev database...")
        db_path = Path("data/newsletter_podcast_dev.db")

    if not db_path.exists():
        print("No database found.")
        return

    print(f"Migrating database: {db_path}")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(episodes)")
    columns = [col[1] for col in cursor.fetchall()]

    migrations = []

    if "llm_input_tokens" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN llm_input_tokens INTEGER")

    if "llm_output_tokens" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN llm_output_tokens INTEGER")

    if "llm_total_tokens" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN llm_total_tokens INTEGER")

    if "llm_cost" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN llm_cost REAL")

    if "tts_characters" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN tts_characters INTEGER")

    if "tts_cost" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN tts_cost REAL")

    if "total_cost" not in columns:
        migrations.append("ALTER TABLE episodes ADD COLUMN total_cost REAL")

    if not migrations:
        print("✓ Database already up to date!")
        conn.close()
        return

    print(f"Running {len(migrations)} migrations...")

    for i, migration in enumerate(migrations, 1):
        print(f"  [{i}/{len(migrations)}] {migration}")
        cursor.execute(migration)

    conn.commit()
    conn.close()

    print("✓ Migration completed successfully!")


if __name__ == "__main__":
    migrate()
