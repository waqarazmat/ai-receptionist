import hashlib
import hmac
import re
import time


def verify_whatsapp_signature(payload: bytes, signature: str, app_secret: str) -> bool:
    """Meta sends `X-Hub-Signature-256: sha256=<hex digest>`."""
    expected = hmac.new(app_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


_RETELL_SIGNATURE_RE = re.compile(r"^v=(\d+),d=(.+)$")


def verify_retell_signature(payload: bytes, signature: str, api_key: str, max_age_seconds: int = 300) -> bool:
    """Retell sends `X-Retell-Signature: v={timestamp_ms},d={hex_digest}`. Unlike
    WhatsApp's, the timestamp is embedded IN the signed string itself (raw body
    + timestamp, concatenated with no separator) rather than sitting elsewhere
    in the payload — so the digest and the replay check both key off the same
    `v` value parsed from this one header, not a separate timestamp field.
    """
    match = _RETELL_SIGNATURE_RE.match(signature)
    if not match:
        return False
    timestamp, digest = match.groups()

    if abs(time.time() * 1000 - int(timestamp)) > max_age_seconds * 1000:
        return False

    expected = hmac.new(api_key.encode(), payload + timestamp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def verify_timestamp(timestamp: str, max_age_seconds: int = 300) -> bool:
    """Replay protection: reject webhooks whose timestamp is too old (or malformed)."""
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    return abs(time.time() - ts) <= max_age_seconds
