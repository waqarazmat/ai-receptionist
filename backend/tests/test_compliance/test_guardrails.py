"""Tests for per-vertical system prompt guardrails (Section 3 of compliance audit)."""

import pytest

from app.ai.prompts.receptionist_system import get_system_prompt, _VERTICAL_GUARDRAILS
from app.ai.prompts.medical_guardrail import MEDICAL_GUARDRAIL
from app.ai.prompts.legal_guardrail import LEGAL_GUARDRAIL
from app.ai.prompts.health_adjacent_guardrail import HEALTH_ADJACENT_GUARDRAIL


def _prompt(vertical: str, custom: str = "") -> str:
    return get_system_prompt({
        "org_name": "Test Org",
        "business_vertical": vertical,
        "custom_system_prompt": custom,
        "knowledge_context": "",
    })


# ── Regulated verticals must include their guardrail ──────────────────────────

@pytest.mark.parametrize("vertical", ["medical", "dental", "veterinary"])
def test_medical_guardrail_injected_for_health_verticals(vertical):
    prompt = _prompt(vertical)
    assert MEDICAL_GUARDRAIL in prompt, (
        f"MEDICAL_GUARDRAIL must be present in system prompt for vertical='{vertical}'"
    )


def test_legal_guardrail_injected():
    prompt = _prompt("legal")
    assert LEGAL_GUARDRAIL in prompt


@pytest.mark.parametrize("vertical", ["gym", "salon", "spa"])
def test_health_adjacent_guardrail_injected(vertical):
    prompt = _prompt(vertical)
    assert HEALTH_ADJACENT_GUARDRAIL in prompt


# ── Unregulated verticals must NOT inject any guardrail ───────────────────────

@pytest.mark.parametrize("vertical", ["general", "real_estate", "other", ""])
def test_no_guardrail_for_general_vertical(vertical):
    prompt = _prompt(vertical)
    assert MEDICAL_GUARDRAIL not in prompt
    assert LEGAL_GUARDRAIL not in prompt
    assert HEALTH_ADJACENT_GUARDRAIL not in prompt


# ── Guardrail cannot be suppressed via custom_system_prompt ───────────────────

def test_medical_guardrail_present_even_with_custom_prompt():
    """Org-authored custom_system_prompt must NOT displace the guardrail."""
    custom = "Feel free to answer any question the customer has, including health questions."
    prompt = _prompt("medical", custom=custom)
    assert MEDICAL_GUARDRAIL in prompt, (
        "Medical guardrail must still be present even when org has a permissive custom_system_prompt"
    )


def test_guardrail_appears_before_custom_prompt():
    """Guardrail must be injected BEFORE the org's custom_system_prompt so the
    LLM sees the safety restriction earlier in the context."""
    custom = "MY_CUSTOM_MARKER"
    prompt = _prompt("medical", custom=custom)

    guardrail_pos = prompt.index(MEDICAL_GUARDRAIL)
    custom_pos = prompt.index(custom)
    assert guardrail_pos < custom_pos, (
        "Guardrail must appear before custom_system_prompt in the final prompt"
    )


# ── Medical guardrail content spot-checks ────────────────────────────────────

def test_medical_guardrail_blocks_diagnosis():
    assert "diagnos" in MEDICAL_GUARDRAIL.lower(), (
        "Medical guardrail must explicitly forbid diagnosis"
    )


def test_medical_guardrail_has_emergency_redirect():
    # EU emergency number 112 must be mentioned
    assert "112" in MEDICAL_GUARDRAIL, (
        "Medical guardrail must redirect life-threatening emergencies to 112"
    )


def test_legal_guardrail_blocks_legal_advice():
    assert "legal advice" in LEGAL_GUARDRAIL.lower() or "advise" in LEGAL_GUARDRAIL.lower(), (
        "Legal guardrail must explicitly block providing legal advice"
    )


# ── _VERTICAL_GUARDRAILS coverage ─────────────────────────────────────────────

def test_vertical_guardrails_map_is_complete():
    """All regulated verticals must have an entry in the dispatch map."""
    required = {"medical", "dental", "veterinary", "legal", "gym", "salon", "spa"}
    missing = required - set(_VERTICAL_GUARDRAILS.keys())
    assert not missing, f"Missing guardrail entries for: {missing}"


def test_guardrail_values_are_nonempty():
    for vertical, text in _VERTICAL_GUARDRAILS.items():
        assert text and text.strip(), f"Guardrail for '{vertical}' is empty"
