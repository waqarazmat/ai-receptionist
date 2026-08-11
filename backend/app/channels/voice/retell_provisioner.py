"""Auto-provisioning of Retell voice agents via Retell's management REST API.

When a super admin saves a Retell Agent ID in the setup wizard, we push this
backend's Custom LLM WebSocket URL and call-events webhook URL into that agent's
config in Retell — so the super admin never has to touch Retell's dashboard by
hand. See app/channels/voice/retell_handler.py for the endpoints we point Retell
at.

Uses the platform-level ``settings.RETELL_API_KEY`` (the Retell account owns the
agents), NOT each org's per-org Retell key (that one only verifies inbound call
webhook signatures).

Retell API (verified against docs.retellai.com):
    POST  https://api.retellai.com/create-agent
    PATCH https://api.retellai.com/update-agent/{agent_id}
    GET   https://api.retellai.com/get-agent/{agent_id}
    Auth: Authorization: Bearer {api_key}
    Custom LLM lives at response_engine = {type: "custom-llm", llm_websocket_url},
    the webhook is the top-level webhook_url field.
"""

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()

RETELL_API_BASE = "https://api.retellai.com"
_REQUEST_TIMEOUT_SECONDS = 15.0

# Default voice for freshly-created agents: a native Retell professional English
# voice (no ElevenLabs/Cartesia/Minimax third-party voice billing). This is the
# same voice the account's existing agents already use. The super admin can
# change it later in Retell's dashboard if they want a different one.
DEFAULT_VOICE_ID = "retell-Cimo"


class RetellProvisioningError(Exception):
    """Raised when provisioning an agent against Retell's API fails (missing
    API key, network error, or a non-2xx response). The agent id is still saved
    to our DB regardless — this only signals the auto-configuration step failed."""


def _public_base() -> str:
    return settings.APP_PUBLIC_URL.rstrip("/")


def _to_ws_scheme(base: str) -> str:
    if base.startswith("https://"):
        return "wss://" + base[len("https://") :]
    if base.startswith("http://"):
        return "ws://" + base[len("http://") :]
    return base


def build_llm_websocket_url(org_id: str) -> str:
    """The Custom LLM WebSocket URL we register for an org's agent.

    Retell appends ``/{call_id}`` to whatever base URL is configured, which
    lands on the ``/llm/{org_id}/{call_id}`` route in retell_handler.py — so the
    base we register ends at ``/{org_id}`` (NOT the agent id: that trailing
    segment is Retell's dynamically-inserted call id, not something we set)."""
    return f"{_to_ws_scheme(_public_base())}/api/public/retell/llm/{org_id}"


def build_webhook_url() -> str:
    """The call-lifecycle webhook URL — mounted alongside WhatsApp's under
    /api/public/webhooks/retell (see app/api/public/webhooks.py)."""
    return f"{_public_base()}/api/public/webhooks/retell"


def is_provisioned_for_org(org_id: str, current_llm_url: str | None) -> bool:
    """True if Retell's stored Custom LLM URL for an agent already points at
    this backend for this org, i.e. re-provisioning would be a no-op."""
    if not current_llm_url:
        return False
    return current_llm_url.rstrip("/") == build_llm_websocket_url(org_id).rstrip("/")


def _auth_headers(api_key: str | None = None) -> dict[str, str]:
    # Prefer the org's OWN Retell key (its agent lives in that account); fall back
    # to the platform key only when the org has none. Passing the platform key for
    # an agent that lives in a different (per-org) Retell account is exactly what
    # made "provision"/"create"/"test" fail with 404s.
    return {"Authorization": f"Bearer {api_key or settings.RETELL_API_KEY}"}


async def create_agent(
    org_id: str, org_name: str, boosted_keywords: list[str] | None = None, api_key: str | None = None
) -> dict:
    """Create a brand-new Retell agent wired to this backend from scratch, so we
    control the full config instead of relying on a hand-made agent.

    The agent is created already pointing at this org's Custom LLM WebSocket +
    webhook, so it's provisioned the moment it exists. Returns the new
    ``agent_id`` (which the caller should save to the org's voice config) plus
    the full agent config and the URLs we set. Raises RetellProvisioningError on
    any failure.

    NOTE: response_engine.type is "custom-llm" (NOT "retell-llm") — our backend
    IS the LLM, served over a WebSocket. "retell-llm" would reference a
    Retell-hosted LLM by llm_id and ignore our llm_websocket_url entirely.
    """
    if not (api_key or settings.RETELL_API_KEY):
        raise RetellProvisioningError(
            "RETELL_API_KEY is not configured on the backend, so a Retell agent "
            "can't be created automatically."
        )

    llm_websocket_url = build_llm_websocket_url(org_id)
    webhook_url = build_webhook_url()
    payload = {
        "agent_name": f"{org_name} - AI Receptionist",
        "response_engine": {"type": "custom-llm", "llm_websocket_url": llm_websocket_url},
        "voice_id": DEFAULT_VOICE_ID,
        "webhook_url": webhook_url,
    }
    if boosted_keywords:
        # ASR keyword boost — helps Retell's transcriber recognize the org's
        # brand/client/product names (see knowledge_base_service.build_boosted_keywords).
        payload["boosted_keywords"] = boosted_keywords
    url = f"{RETELL_API_BASE}/create-agent"

    logger.info("retell_create_request", org_id=org_id, url=url, payload=payload)

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload, headers=_auth_headers(api_key))
    except httpx.HTTPError as exc:
        logger.warning("retell_create_network_error", org_id=org_id, error=str(exc))
        raise RetellProvisioningError(f"Could not reach Retell's API: {exc}") from exc

    logger.info(
        "retell_create_response",
        org_id=org_id,
        status_code=response.status_code,
        body=response.text,
    )

    if response.status_code >= 400:
        raise RetellProvisioningError(f"Retell's API returned {response.status_code}: {response.text}")

    try:
        agent = response.json()
    except ValueError:
        agent = {}

    agent_id = agent.get("agent_id")
    if not agent_id:
        raise RetellProvisioningError("Retell created an agent but returned no agent_id.")

    return {
        "agent": agent,
        "agent_id": agent_id,
        "llm_websocket_url": llm_websocket_url,
        "webhook_url": webhook_url,
    }


async def provision_agent(
    org_id: str, retell_agent_id: str, boosted_keywords: list[str] | None = None, api_key: str | None = None
) -> dict:
    """Point a Retell agent's Custom LLM URL and webhook URL at this backend.

    Returns the updated agent config plus the URLs we set. Raises
    RetellProvisioningError on any failure so the caller can save the agent id
    anyway and surface a warning."""
    if not (api_key or settings.RETELL_API_KEY):
        raise RetellProvisioningError(
            "RETELL_API_KEY is not configured on the backend, so the agent's "
            "Custom LLM URL can't be set automatically."
        )

    llm_websocket_url = build_llm_websocket_url(org_id)
    webhook_url = build_webhook_url()
    payload = {
        "response_engine": {"type": "custom-llm", "llm_websocket_url": llm_websocket_url},
        "webhook_url": webhook_url,
    }
    if boosted_keywords:
        # ASR keyword boost (see knowledge_base_service.build_boosted_keywords).
        payload["boosted_keywords"] = boosted_keywords
    url = f"{RETELL_API_BASE}/update-agent/{retell_agent_id}"

    logger.info(
        "retell_provision_request",
        org_id=org_id,
        agent_id=retell_agent_id,
        url=url,
        payload=payload,
    )

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.patch(url, json=payload, headers=_auth_headers(api_key))
    except httpx.HTTPError as exc:
        logger.warning("retell_provision_network_error", org_id=org_id, agent_id=retell_agent_id, error=str(exc))
        raise RetellProvisioningError(f"Could not reach Retell's API: {exc}") from exc

    logger.info(
        "retell_provision_response",
        org_id=org_id,
        agent_id=retell_agent_id,
        status_code=response.status_code,
        body=response.text,
    )

    if response.status_code >= 400:
        raise RetellProvisioningError(
            f"Retell's API returned {response.status_code}: {response.text}"
        )

    try:
        agent = response.json()
    except ValueError:
        agent = {}

    return {
        "agent": agent,
        "llm_websocket_url": llm_websocket_url,
        "webhook_url": webhook_url,
    }


async def verify_agent(retell_agent_id: str, api_key: str | None = None) -> dict:
    """Read an agent's current config from Retell to check it exists and where
    its Custom LLM URL / webhook currently point.

    Returns {exists, current_llm_url, current_webhook_url} (plus an optional
    `error`). Never raises — this backs a status display, so any failure just
    reports the agent as unverifiable rather than breaking the page."""
    unknown = {"exists": False, "current_llm_url": None, "current_webhook_url": None}

    if not (api_key or settings.RETELL_API_KEY):
        return {**unknown, "error": "RETELL_API_KEY is not configured"}

    url = f"{RETELL_API_BASE}/get-agent/{retell_agent_id}"
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=_auth_headers(api_key))
    except httpx.HTTPError as exc:
        logger.warning("retell_verify_network_error", agent_id=retell_agent_id, error=str(exc))
        return {**unknown, "error": str(exc)}

    if response.status_code == 404:
        return unknown
    if response.status_code >= 400:
        logger.warning(
            "retell_verify_error",
            agent_id=retell_agent_id,
            status_code=response.status_code,
            body=response.text,
        )
        return {**unknown, "error": response.text}

    try:
        agent = response.json()
    except ValueError:
        return {**unknown, "error": "Retell returned a non-JSON response"}

    engine = agent.get("response_engine") or {}
    return {
        "exists": True,
        "current_llm_url": engine.get("llm_websocket_url"),
        "current_webhook_url": agent.get("webhook_url"),
    }
