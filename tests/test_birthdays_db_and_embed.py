import pytest
import aiosqlite
from types import SimpleNamespace

from cogs.birthday import BirthdayCog
from database import Database


@pytest.mark.asyncio
async def test_birthday_set_and_list(tmp_path, monkeypatch):
    db_path = tmp_path / "birth.db"
    db = Database(str(db_path))
    await db.init_database()

    # Minimal bot stub with db and methods used
    bot = SimpleNamespace(db=db, get_user=lambda uid: SimpleNamespace(display_name=f"User{uid}"))
    cog = BirthdayCog.__new__(BirthdayCog)
    cog.bot = bot

    guild_id = 77
    # Set birthdays
    await db.set_user_birthday(user_id=10, guild_id=guild_id, month=1, day=15)
    await db.set_user_birthday(user_id=20, guild_id=guild_id, month=1, day=3)

    # Verify month fetch order
    jan = await db.get_birthdays_for_month(guild_id, 1)
    assert [b["day"] for b in jan] == [3, 15]


@pytest.mark.asyncio
async def test_generate_permanent_birthday_embed(tmp_path, monkeypatch):
    db_path = tmp_path / "perm.db"
    db = Database(str(db_path))
    await db.init_database()

    # Prepare data
    guild_id = 1
    await db.set_user_birthday(user_id=1, guild_id=guild_id, month=5, day=10)
    await db.set_user_birthday(user_id=2, guild_id=guild_id, month=5, day=1)
    await db.set_user_birthday(user_id=3, guild_id=guild_id, month=12, day=25)

    # Stub bot with db and get_user
    def get_user(uid):
        return SimpleNamespace(display_name=f"User{uid}")

    bot = SimpleNamespace(db=db, get_user=get_user)
    cog = BirthdayCog.__new__(BirthdayCog)
    cog.bot = bot

    embed = await BirthdayCog._generate_permanent_birthday_embed(cog, guild_id)
    assert embed.title == "🎂 Server Birthdays"
    # Expect months May and December fields present
    field_names = [f.name for f in embed.fields]
    assert "May" in field_names
    assert "December" in field_names


