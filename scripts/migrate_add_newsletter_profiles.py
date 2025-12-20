"""
Database migration to add newsletter profile support.

Adds columns: newsletter_profile_id, issue_number, slug to newsletters table.
"""

import asyncio
import sqlite3
from pathlib import Path


async def migrate():
    """Run migration to add newsletter profile columns."""
    # Find database file
    db_path = Path("data/newsletter_podcast_local.db")

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Looking for dev database...")
        db_path = Path("data/newsletter_podcast_dev.db")

    if not db_path.exists():
        print("No database found. Please run the application first to create the database.")
        return

    print(f"Migrating database: {db_path}")

    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(newsletters)")
    columns = [col[1] for col in cursor.fetchall()]

    migrations_needed = []

    if "newsletter_profile_id" not in columns:
        migrations_needed.append(
            "ALTER TABLE newsletters ADD COLUMN newsletter_profile_id VARCHAR(100)"
        )

    if "issue_number" not in columns:
        migrations_needed.append(
            "ALTER TABLE newsletters ADD COLUMN issue_number VARCHAR(50)"
        )

    if "slug" not in columns:
        migrations_needed.append(
            "ALTER TABLE newsletters ADD COLUMN slug VARCHAR(100)"
        )

    if not migrations_needed:
        print("✓ Database already up to date!")
        conn.close()
        return

    # Run migrations
    print(f"Running {len(migrations_needed)} migrations...")

    for i, migration in enumerate(migrations_needed, 1):
        print(f"  [{i}/{len(migrations_needed)}] {migration}")
        cursor.execute(migration)

    # Create indexes for new columns
    try:
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ix_newsletters_newsletter_profile_id ON newsletters (newsletter_profile_id)"
        )
        print("  ✓ Created index on newsletter_profile_id")
    except sqlite3.OperationalError:
        pass  # Index might already exist

    conn.commit()
    conn.close()

    print("✓ Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(migrate())
