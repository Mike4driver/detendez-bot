import pytest
from types import SimpleNamespace

import cogs.scheduler as scheduler_mod
from cogs.scheduler import SchedulerCog


def test_scheduler_ai_setup_without_key(monkeypatch):
    # Ensure Config.GEMINI_API_KEY is treated as missing for this test
    monkeypatch.setattr(scheduler_mod.Config, "GEMINI_API_KEY", None, raising=False)

    bot = SimpleNamespace()
    cog = SchedulerCog.__new__(SchedulerCog)
    cog.bot = bot

    # Force setup_ai to run
    SchedulerCog.setup_ai(cog)

    assert cog.ai_enabled is False
    assert cog.model is None


