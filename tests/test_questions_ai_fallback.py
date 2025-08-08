import pytest
from types import SimpleNamespace
from cogs.questions import QuestionsCog


@pytest.mark.asyncio
async def test_questions_fallback_when_ai_disabled(monkeypatch):
    # Create a bot stub with minimal db
    bot = SimpleNamespace(db=SimpleNamespace(db_file=":memory:"))
    cog = QuestionsCog.__new__(QuestionsCog)
    cog.bot = bot
    cog.model = None
    cog.ai_enabled = False

    q = await QuestionsCog._generate_question(cog)
    assert isinstance(q, str) and len(q) > 0


