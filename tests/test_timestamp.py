import pytest
import aiosqlite
from types import SimpleNamespace
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytz

from cogs.timestamp import TimestampCog
from database import Database


@pytest.mark.asyncio
async def test_database_timezone_operations(tmp_path):
    """Test database timezone CRUD operations"""
    db_path = tmp_path / "timezone.db"
    db = Database(str(db_path))
    await db.init_database()

    user_id = 12345
    timezone = "America/New_York"

    # Test setting timezone
    await db.set_user_timezone(user_id, timezone)

    # Test getting timezone
    retrieved = await db.get_user_timezone(user_id)
    assert retrieved == timezone

    # Test updating timezone
    new_timezone = "Europe/London"
    await db.set_user_timezone(user_id, new_timezone)
    retrieved = await db.get_user_timezone(user_id)
    assert retrieved == new_timezone

    # Test getting non-existent timezone
    assert await db.get_user_timezone(99999) is None


@pytest.mark.asyncio
async def test_database_timezone_table_exists(tmp_path):
    """Test that user_timezones table is created"""
    db_path = tmp_path / "timezone.db"
    db = Database(str(db_path))
    await db.init_database()

    async with aiosqlite.connect(db.db_file) as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
            ("user_timezones",)
        ) as cur:
            row = await cur.fetchone()
            assert row is not None, "user_timezones table should exist"


@pytest.fixture
def timestamp_cog(tmp_path):
    """Create a TimestampCog instance with a temporary database"""
    db_path = tmp_path / "test.db"
    db = Database(str(db_path))
    
    bot = SimpleNamespace(db=db)
    cog = TimestampCog.__new__(TimestampCog)
    cog.bot = bot
    return cog


@pytest.mark.asyncio
async def test_detect_patterns_time_only(timestamp_cog):
    """Test detection of time-only patterns"""
    patterns = timestamp_cog._detect_patterns("Let's meet at 10pm")
    assert len(patterns) > 0
    assert any(p[0] == 'time' for p in patterns)

    patterns = timestamp_cog._detect_patterns("The meeting is at 3:30pm")
    assert len(patterns) > 0
    assert any(p[0] == 'time' for p in patterns)

    patterns = timestamp_cog._detect_patterns("See you at 15:00")
    assert len(patterns) > 0
    assert any(p[0] == 'time' for p in patterns)


@pytest.mark.asyncio
async def test_detect_patterns_date_only(timestamp_cog):
    """Test detection of date-only patterns"""
    patterns = timestamp_cog._detect_patterns("My birthday is Dec 5")
    assert len(patterns) > 0
    assert any(p[0] == 'date' for p in patterns)

    patterns = timestamp_cog._detect_patterns("The event is on 12/25")
    assert len(patterns) > 0
    assert any(p[0] == 'date' for p in patterns)

    patterns = timestamp_cog._detect_patterns("December 5th is the date")
    assert len(patterns) > 0
    assert any(p[0] == 'date' for p in patterns)


@pytest.mark.asyncio
async def test_detect_patterns_combined(timestamp_cog):
    """Test detection of combined date/time patterns"""
    patterns = timestamp_cog._detect_patterns("Meeting is Dec 5 at 3pm")
    assert len(patterns) > 0
    assert any(p[0] == 'combined' for p in patterns)

    patterns = timestamp_cog._detect_patterns("Tomorrow at 10am we start")
    assert len(patterns) > 0
    assert any(p[0] == 'combined' for p in patterns)

    patterns = timestamp_cog._detect_patterns("12/25 at 3:30pm")
    assert len(patterns) > 0
    assert any(p[0] == 'combined' for p in patterns)


@pytest.mark.asyncio
async def test_detect_patterns_no_match(timestamp_cog):
    """Test that non-matching text returns empty list"""
    patterns = timestamp_cog._detect_patterns("This is just regular text")
    assert len(patterns) == 0


@pytest.mark.asyncio
async def test_parse_time_12hour_format(timestamp_cog):
    """Test parsing 12-hour time formats"""
    timezone = "America/New_York"
    tz = pytz.timezone(timezone)
    
    # Test 10pm
    pattern = timestamp_cog._compile_patterns()['time'][0]
    match = pattern.search("10pm")
    assert match is not None
    timestamp = timestamp_cog._parse_time(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)
    
    # Verify the timestamp is in the future
    now = datetime.now(tz)
    parsed_time = datetime.fromtimestamp(timestamp, tz)
    assert parsed_time >= now


@pytest.mark.asyncio
async def test_parse_time_24hour_format(timestamp_cog):
    """Test parsing 24-hour time formats"""
    timezone = "America/New_York"
    
    # Test 15:00
    pattern = timestamp_cog._compile_patterns()['time'][1]
    match = pattern.search("15:00")
    assert match is not None
    timestamp = timestamp_cog._parse_time(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)


@pytest.mark.asyncio
async def test_parse_time_with_minutes(timestamp_cog):
    """Test parsing time with minutes"""
    timezone = "America/New_York"
    
    # Test 3:30pm
    pattern = timestamp_cog._compile_patterns()['time'][1]
    match = pattern.search("3:30pm")
    assert match is not None
    timestamp = timestamp_cog._parse_time(match, timezone)
    assert timestamp is not None


@pytest.mark.asyncio
async def test_parse_date_month_name(timestamp_cog):
    """Test parsing date with month name"""
    timezone = "America/New_York"
    
    # Test Dec 5
    pattern = timestamp_cog._compile_patterns()['date'][0]
    match = pattern.search("Dec 5")
    assert match is not None
    timestamp = timestamp_cog._parse_date(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)


@pytest.mark.asyncio
async def test_parse_date_numeric_format(timestamp_cog):
    """Test parsing numeric date format"""
    timezone = "America/New_York"
    
    # Test 12/25
    pattern = timestamp_cog._compile_patterns()['date'][1]
    match = pattern.search("12/25")
    assert match is not None
    timestamp = timestamp_cog._parse_date(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)


@pytest.mark.asyncio
async def test_parse_combined_month_at_time(timestamp_cog):
    """Test parsing combined date/time with month name"""
    timezone = "America/New_York"
    
    # Test Dec 5 at 3pm
    pattern = timestamp_cog._compile_patterns()['combined'][0]
    match = pattern.search("Dec 5 at 3pm")
    assert match is not None
    timestamp = timestamp_cog._parse_combined(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)


@pytest.mark.asyncio
async def test_parse_combined_tomorrow(timestamp_cog):
    """Test parsing 'tomorrow at' patterns"""
    timezone = "America/New_York"
    
    # Test tomorrow at 10am
    pattern = timestamp_cog._compile_patterns()['combined'][2]
    match = pattern.search("tomorrow at 10am")
    assert match is not None
    timestamp = timestamp_cog._parse_combined(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)
    
    # Verify it's in the future (tomorrow)
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    parsed_time = datetime.fromtimestamp(timestamp, tz)
    time_diff = parsed_time - now
    # Should be between 0 and 48 hours in the future (depending on current time)
    assert timedelta(hours=0) < time_diff < timedelta(hours=48)


@pytest.mark.asyncio
async def test_parse_combined_today(timestamp_cog):
    """Test parsing 'today at' patterns"""
    timezone = "America/New_York"
    
    # Test today at 10am
    pattern = timestamp_cog._compile_patterns()['combined'][2]
    match = pattern.search("today at 10am")
    assert match is not None
    timestamp = timestamp_cog._parse_combined(match, timezone)
    assert timestamp is not None
    assert isinstance(timestamp, int)


@pytest.mark.asyncio
async def test_convert_patterns(timestamp_cog):
    """Test converting patterns to Discord timestamps"""
    timezone = "America/New_York"
    
    # Test time conversion
    results = await timestamp_cog._convert_patterns("Let's meet at 10pm", timezone)
    assert len(results) > 0
    assert results[0][0] == 'time'
    assert results[0][1] is not None  # timestamp
    assert results[0][2] == "10pm"  # matched text
    
    # Test date conversion
    results = await timestamp_cog._convert_patterns("My birthday is Dec 5", timezone)
    assert len(results) > 0
    assert results[0][0] == 'date'
    assert results[0][1] is not None
    
    # Test combined conversion
    results = await timestamp_cog._convert_patterns("Meeting is Dec 5 at 3pm", timezone)
    assert len(results) > 0
    assert results[0][0] == 'combined'
    assert results[0][1] is not None


@pytest.mark.asyncio
async def test_convert_patterns_multiple(timestamp_cog):
    """Test converting multiple patterns in one message"""
    timezone = "America/New_York"
    
    results = await timestamp_cog._convert_patterns(
        "Meeting at 10am and then lunch at 12:30pm", 
        timezone
    )
    assert len(results) >= 2  # Should detect both times


@pytest.mark.asyncio
async def test_on_message_ignores_bot_messages(timestamp_cog):
    """Test that bot messages are ignored"""
    message = MagicMock()
    message.author.bot = True
    message.channel.name = "general"
    message.content = "Let's meet at 10pm"
    message.reply = AsyncMock()
    
    # Should return early without processing
    await timestamp_cog.on_message(message)
    
    # Verify no reply was made
    message.reply.assert_not_called()


@pytest.mark.asyncio
async def test_on_message_ignores_non_general_channels(timestamp_cog):
    """Test that non-general channels are ignored"""
    message = MagicMock()
    message.author.bot = False
    message.channel.name = "random"
    message.content = "Let's meet at 10pm"
    
    await timestamp_cog.on_message(message)
    
    # Should not process
    assert not hasattr(message, 'reply') or not message.reply.called


@pytest.mark.asyncio
async def test_on_message_prompts_for_timezone_when_not_set(timestamp_cog):
    """Test that user is prompted to set timezone when not configured"""
    await timestamp_cog.bot.db.init_database()
    
    message = MagicMock()
    message.author.bot = False
    message.author.id = 12345
    message.channel.name = "general"
    message.content = "Let's meet at 10pm"
    message.reply = AsyncMock()
    
    # User has no timezone set
    assert await timestamp_cog.bot.db.get_user_timezone(12345) is None
    
    await timestamp_cog.on_message(message)
    
    # Should prompt user to set timezone
    message.reply.assert_called_once()
    call_args = message.reply.call_args
    assert "set-timezone" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_on_message_converts_when_timezone_set(timestamp_cog):
    """Test that timestamps are converted when timezone is set"""
    await timestamp_cog.bot.db.init_database()
    
    user_id = 12345
    timezone = "America/New_York"
    await timestamp_cog.bot.db.set_user_timezone(user_id, timezone)
    
    message = MagicMock()
    message.author.bot = False
    message.author.id = user_id
    message.author.mention = "<@12345>"
    message.channel.name = "general"
    message.content = "Let's meet at 10pm"
    message.reply = AsyncMock()
    
    await timestamp_cog.on_message(message)
    
    # Should convert and reply
    message.reply.assert_called_once()
    call_args = message.reply.call_args
    reply_text = call_args[0][0]
    assert "<t:" in reply_text  # Should contain Discord timestamp
    assert "10pm" in reply_text


@pytest.mark.asyncio
async def test_set_timezone_command_valid_timezone(timestamp_cog):
    """Test /set-timezone command with valid timezone"""
    await timestamp_cog.bot.db.init_database()
    
    interaction = AsyncMock()
    interaction.user.id = 12345
    interaction.response.send_message = AsyncMock()
    
    # Access the callback directly since it's decorated with @app_commands.command
    await timestamp_cog.set_timezone.callback(timestamp_cog, interaction, "America/New_York")
    
    # Should save timezone
    timezone = await timestamp_cog.bot.db.get_user_timezone(12345)
    assert timezone == "America/New_York"
    
    # Should send success message
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    embed = call_args[1]['embed']
    assert "✅" in embed.title or "Set" in embed.title


@pytest.mark.asyncio
async def test_set_timezone_command_invalid_timezone(timestamp_cog):
    """Test /set-timezone command with invalid timezone"""
    await timestamp_cog.bot.db.init_database()
    
    interaction = AsyncMock()
    interaction.user.id = 12345
    interaction.response.send_message = AsyncMock()
    
    # Access the callback directly since it's decorated with @app_commands.command
    await timestamp_cog.set_timezone.callback(timestamp_cog, interaction, "Invalid/Timezone")
    
    # Should not save timezone
    timezone = await timestamp_cog.bot.db.get_user_timezone(12345)
    assert timezone is None
    
    # Should send error message
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    assert "❌" in call_args[0][0] or "Invalid" in call_args[0][0]


@pytest.mark.asyncio
async def test_my_timezone_command_no_timezone_set(timestamp_cog):
    """Test /my-timezone command when no timezone is set"""
    await timestamp_cog.bot.db.init_database()
    
    interaction = AsyncMock()
    interaction.user.id = 12345
    interaction.response.send_message = AsyncMock()
    
    # Access the callback directly since it's decorated with @app_commands.command
    await timestamp_cog.my_timezone.callback(timestamp_cog, interaction)
    
    # Should send message indicating no timezone set
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    embed = call_args[1]['embed']
    assert "set" in embed.description.lower() or "haven't" in embed.description.lower()


@pytest.mark.asyncio
async def test_my_timezone_command_with_timezone_set(timestamp_cog):
    """Test /my-timezone command when timezone is set"""
    await timestamp_cog.bot.db.init_database()
    
    user_id = 12345
    timezone = "Europe/London"
    await timestamp_cog.bot.db.set_user_timezone(user_id, timezone)
    
    interaction = AsyncMock()
    interaction.user.id = user_id
    interaction.response.send_message = AsyncMock()
    
    # Access the callback directly since it's decorated with @app_commands.command
    await timestamp_cog.my_timezone.callback(timestamp_cog, interaction)
    
    # Should send message with timezone info
    interaction.response.send_message.assert_called_once()
    call_args = interaction.response.send_message.call_args
    embed = call_args[1]['embed']
    assert timezone in embed.description


@pytest.mark.asyncio
async def test_parse_time_handles_past_time(timestamp_cog):
    """Test that past times are assumed to be tomorrow"""
    timezone = "America/New_York"
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    # If current time is afternoon, 10am should be tomorrow
    if now.hour >= 10:
        pattern = timestamp_cog._compile_patterns()['time'][0]
        match = pattern.search("10am")
        assert match is not None
        timestamp = timestamp_cog._parse_time(match, timezone)
        assert timestamp is not None
        
        parsed_time = datetime.fromtimestamp(timestamp, tz)
        # Should be in the future
        assert parsed_time > now


@pytest.mark.asyncio
async def test_parse_date_handles_past_date(timestamp_cog):
    """Test that past dates are assumed to be next year"""
    timezone = "America/New_York"
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    # Use a date that's likely in the past (e.g., January 1st)
    pattern = timestamp_cog._compile_patterns()['date'][0]
    match = pattern.search("Jan 1")
    if match:
        timestamp = timestamp_cog._parse_date(match, timezone)
        if timestamp:
            parsed_time = datetime.fromtimestamp(timestamp, tz)
            # Should be in the future (next year if past)
            assert parsed_time >= now


@pytest.mark.asyncio
async def test_pattern_detection_case_insensitive(timestamp_cog):
    """Test that pattern detection is case-insensitive"""
    # Test various case combinations
    test_cases = [
        "10PM",
        "10pm",
        "10Pm",
        "DEC 5",
        "dec 5",
        "Dec 5",
        "TOMORROW AT 10AM",
        "tomorrow at 10am",
    ]
    
    for text in test_cases:
        patterns = timestamp_cog._detect_patterns(text)
        assert len(patterns) > 0, f"Should detect pattern in: {text}"


@pytest.mark.asyncio
async def test_on_message_handles_channel_without_name_attribute(timestamp_cog):
    """Test that message listener handles channels without name attribute gracefully"""
    message = MagicMock()
    message.author.bot = False
    message.channel = None  # No channel
    message.content = "Let's meet at 10pm"
    
    # Should not raise an error
    await timestamp_cog.on_message(message)


@pytest.mark.asyncio
async def test_on_message_no_patterns_detected(timestamp_cog):
    """Test that message listener doesn't reply when no patterns are detected"""
    await timestamp_cog.bot.db.init_database()
    
    user_id = 12345
    timezone = "America/New_York"
    await timestamp_cog.bot.db.set_user_timezone(user_id, timezone)
    
    message = MagicMock()
    message.author.bot = False
    message.author.id = user_id
    message.channel.name = "general"
    message.content = "This is just regular text with no times"
    message.reply = AsyncMock()
    
    await timestamp_cog.on_message(message)
    
    # Should not reply
    message.reply.assert_not_called()

