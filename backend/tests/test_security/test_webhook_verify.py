import hashlib
import hmac
import time

from app.security.webhook_verify import (
    verify_retell_signature,
    verify_timestamp,
    verify_whatsapp_signature,
)


def _sign(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestWhatsappSignature:
    def test_valid_signature_passes(self):
        secret = "app-secret"
        payload = b'{"entry": []}'
        signature = f"sha256={_sign(secret, payload)}"

        assert verify_whatsapp_signature(payload, signature, secret) is True

    def test_tampered_payload_fails(self):
        secret = "app-secret"
        payload = b'{"entry": []}'
        signature = f"sha256={_sign(secret, payload)}"

        tampered_payload = b'{"entry": ["injected"]}'

        assert verify_whatsapp_signature(tampered_payload, signature, secret) is False

    def test_wrong_secret_fails(self):
        payload = b'{"entry": []}'
        signature = f"sha256={_sign('app-secret', payload)}"

        assert verify_whatsapp_signature(payload, signature, "wrong-secret") is False


def _retell_sign(api_key: str, payload: bytes) -> str:
    """Build a Retell-format signature: `v={timestamp_ms},d={hex_digest}`.
    The digest covers raw_body + timestamp (no separator), matching the
    implementation in webhook_verify.verify_retell_signature."""
    timestamp = str(int(time.time() * 1000))
    digest = hmac.new(api_key.encode(), payload + timestamp.encode(), hashlib.sha256).hexdigest()
    return f"v={timestamp},d={digest}"


class TestRetellSignature:
    def test_valid_signature_passes(self):
        api_key = "retell-key"
        payload = b'{"transcript": "hello"}'
        signature = _retell_sign(api_key, payload)

        assert verify_retell_signature(payload, signature, api_key) is True

    def test_tampered_payload_fails(self):
        api_key = "retell-key"
        payload = b'{"transcript": "hello"}'
        signature = _retell_sign(api_key, payload)

        tampered_payload = b'{"transcript": "goodbye"}'

        assert verify_retell_signature(tampered_payload, signature, api_key) is False


class TestVerifyTimestamp:
    def test_recent_timestamp_passes(self):
        assert verify_timestamp(str(int(time.time()))) is True

    def test_old_timestamp_fails(self):
        old_timestamp = str(int(time.time()) - 600)
        assert verify_timestamp(old_timestamp, max_age_seconds=300) is False

    def test_malformed_timestamp_fails(self):
        assert verify_timestamp("not-a-number") is False
