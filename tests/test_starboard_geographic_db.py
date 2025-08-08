import pytest
import aiosqlite

from database import Database


@pytest.mark.asyncio
async def test_starboard_crud(tmp_path):
    db_path = tmp_path / "sb.db"
    db = Database(str(db_path))
    await db.init_database()

    guild_id = 1
    orig_id = 111
    star_id = 222

    await db.add_starboard_message(orig_id, star_id, guild_id, star_count=5)
    data = await db.get_starboard_message(orig_id, guild_id)
    assert data is not None
    assert data["starboard_message_id"] == star_id
    assert data["star_count"] == 5

    await db.update_starboard_count(orig_id, guild_id, 9)
    data = await db.get_starboard_message(orig_id, guild_id)
    assert data["star_count"] == 9

    await db.remove_starboard_message(orig_id, guild_id)
    data = await db.get_starboard_message(orig_id, guild_id)
    assert data is None


@pytest.mark.asyncio
async def test_geographic_poll_and_results(tmp_path):
    db_path = tmp_path / "geo.db"
    db = Database(str(db_path))
    await db.init_database()

    guild_id = 42
    message_id = 999
    channel_id = 333
    title = "Region Poll"

    await db.add_geographic_poll(message_id, guild_id, title, channel_id)
    assert await db.is_geographic_poll(message_id, guild_id) is True

    poll = await db.get_geographic_poll(message_id, guild_id)
    assert poll["title"] == title
    assert poll["channel_id"] == channel_id

    # Add selections
    await db.add_geographic_selection(user_id=1, message_id=message_id, guild_id=guild_id, region="West Coast")
    await db.add_geographic_selection(user_id=2, message_id=message_id, guild_id=guild_id, region="West Coast")
    await db.add_geographic_selection(user_id=3, message_id=message_id, guild_id=guild_id, region="East Coast")

    results = await db.get_geographic_results(message_id, guild_id)
    assert results.get("West Coast") == 2
    assert results.get("East Coast") == 1

    # Remove one selection
    await db.remove_geographic_selection(user_id=2, message_id=message_id, guild_id=guild_id, region="West Coast")
    results = await db.get_geographic_results(message_id, guild_id)
    assert results.get("West Coast", 0) == 1


