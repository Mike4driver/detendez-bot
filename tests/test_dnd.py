import pytest
from types import SimpleNamespace

from cogs.dnd import DnDCog


def test_roll_dice_basic(monkeypatch):
    # Create a minimal bot stub
    bot = SimpleNamespace()
    cog = DnDCog.__new__(DnDCog)
    cog.bot = bot
    # Bypass AI setup for pure dice tests
    cog.ai_enabled = False

    # Test valid rolls
    rolls, total, breakdown = DnDCog.roll_dice(cog, "2d6+3")
    assert len(rolls) == 2
    assert isinstance(total, int)
    assert "+3" in breakdown or "+3" in breakdown.replace(" ", "")

    # Single die no modifier
    rolls, total, breakdown = DnDCog.roll_dice(cog, "1d20")
    assert len(rolls) == 1 and 1 <= rolls[0] <= 20


@pytest.mark.parametrize("bad", ["d20", "0d6", "-1d8", "2d0", "2d6++2", "2x6"]) 
def test_roll_dice_invalid_inputs(bad):
    bot = SimpleNamespace()
    cog = DnDCog.__new__(DnDCog)
    cog.bot = bot
    cog.ai_enabled = False

    with pytest.raises(ValueError):
        DnDCog.roll_dice(cog, bad)


@pytest.mark.asyncio
async def test_parse_dnd_action_two_step(monkeypatch):
    """Test two-step parsing with mocked Gemini responses."""
    bot = SimpleNamespace()

    # Instantiate without calling __init__ to avoid real setup
    cog = DnDCog.__new__(DnDCog)
    cog.bot = bot
    cog.ai_enabled = True

    # Mock model with a simple object providing generate_content
    class DummyModel:
        calls = []
        def generate_content(self, prompt):
            DummyModel.calls.append(prompt)
            if "Analyze the following action" in prompt:
                return SimpleNamespace(text="Chromatic Orb is a 1st-level spell that deals 3d8 damage at base; at 4th level, add +3d8 (total 6d8).")
            return SimpleNamespace(text="6d8")

    cog.model = DummyModel()

    result = await DnDCog._parse_dnd_action(cog, "chromatic orb level 4")
    assert result == "6d8"


