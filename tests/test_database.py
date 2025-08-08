import asyncio
import os
import aiosqlite
import pytest

from database import Database


@pytest.mark.asyncio
async def test_init_database_creates_tables(tmp_path):
    db_path = tmp_path / "bot.db"
    db = Database(str(db_path))
    await db.init_database()

    async with aiosqlite.connect(db.db_file) as conn:
        # Verify core tables exist
        for table in [
            "user_levels",
            "starboard_messages",
            "user_birthdays",
            "guild_config",
            "recent_content",
            "music_queue",
            "geographic_polls",
            "geographic_selections",
        ]:
            async with conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)) as cur:
                row = await cur.fetchone()
                assert row is not None, f"Missing table: {table}"


@pytest.mark.asyncio
async def test_migration_adds_birthday_permanent_columns(tmp_path):
    db_path = tmp_path / "old.db"

    # Create a minimal old schema without the new columns
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("CREATE TABLE guild_config (guild_id INTEGER PRIMARY KEY, birthday_channel INTEGER)")
        await conn.commit()

    db = Database(str(db_path))
    await db.init_database()

    # Columns should now exist
    async with aiosqlite.connect(db.db_file) as conn:
        async with conn.execute("PRAGMA table_info(guild_config)") as cur:
            columns = await cur.fetchall()
            names = [c[1] for c in columns]
            assert "birthday_permanent_channel" in names
            assert "birthday_permanent_message" in names


@pytest.mark.asyncio
async def test_guild_config_update_and_fetch(tmp_path):
    db_path = tmp_path / "config.db"
    db = Database(str(db_path))
    await db.init_database()

    guild_id = 12345
    await db.create_default_guild_config(guild_id)
    await db.update_guild_config(guild_id, question_channel=111, question_time="10:30")

    cfg = await db.get_guild_config(guild_id)
    assert cfg["guild_id"] == guild_id
    assert cfg["question_channel"] == 111
    assert cfg["question_time"] == "10:30"


