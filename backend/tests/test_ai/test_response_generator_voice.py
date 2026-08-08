"""The WhatsApp voice-note answer path asks the LLM for a concise, TTS-friendly
reply so long informational answers are spoken (not dropped to text) and never
dictate markdown/bullets aloud. Text replies are unchanged."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai import response_generator


async def _build(reply_channel: str):
    org = MagicMock()
    org.name = "Acme Clinic"
    org.system_prompts = {"greeting": "Hi", "personality": "friendly and brief"}
    db = MagicMock()
    db.get = AsyncMock(return_value=org)
    with patch(
        "app.ai.response_generator.get_org_llm_clients",
        new_callable=AsyncMock,
        return_value=[MagicMock()],
    ):
        return await response_generator.build_generation_plan(
            db, uuid.uuid4(), "faq", [], [{"role": "customer", "content": "what services?"}],
            None, reply_channel,
        )


class TestVoiceStyleInstruction:
    @pytest.mark.asyncio
    async def test_voice_appends_concise_spoken_instruction(self):
        plan = await _build("voice")
        assert plan.system_prompt is not None
        assert "spoken aloud" in plan.system_prompt
        assert "2-3 sentences" in plan.system_prompt
        assert "markdown" in plan.system_prompt.lower()

    @pytest.mark.asyncio
    async def test_text_reply_has_no_voice_instruction(self):
        plan = await _build("text")
        assert plan.system_prompt is not None
        assert "spoken aloud" not in plan.system_prompt

    @pytest.mark.asyncio
    async def test_voice_instruction_is_appended_last(self):
        """The spoken-style rule must come after the base prompt so it wins."""
        plan = await _build("voice")
        assert plan.system_prompt.rstrip().endswith("in writing.")

    @pytest.mark.asyncio
    async def test_default_channel_is_text(self):
        org = MagicMock(name="o")
        org.name = "Acme"
        org.system_prompts = {}
        db = MagicMock()
        db.get = AsyncMock(return_value=org)
        with patch(
            "app.ai.response_generator.get_org_llm_clients",
            new_callable=AsyncMock,
            return_value=[MagicMock()],
        ):
            plan = await response_generator.build_generation_plan(
                db, uuid.uuid4(), "faq", [], [{"role": "customer", "content": "hi"}], None
            )
        assert "spoken aloud" not in plan.system_prompt
