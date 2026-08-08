import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import settings

PBKDF2_ITERATIONS = 100_000


def derive_org_key(org_id: str) -> bytes:
    """Derive a per-org Fernet key from the master key + org_id salt.

    Per-org derivation means a leaked key for one org can't decrypt another
    org's secrets, and the master key alone (without the org_id) is useless.
    """
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        settings.MASTER_ENCRYPTION_KEY.encode(),
        org_id.encode(),
        PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(dk)


def encrypt_api_key(org_id: str, plaintext: str) -> str:
    # Trim surrounding whitespace: API keys / tokens never legitimately have it,
    # but copy-paste (from a terminal, a docs table, an indented block) routinely
    # prepends a tab/space or appends a newline. A stray leading tab silently
    # corrupts an auth header (e.g. Anthropic's x-api-key) and the provider rejects
    # the call — hard to spot because the ciphertext looks fine. Strip on the way in.
    key = derive_org_key(org_id)
    return Fernet(key).encrypt(plaintext.strip().encode()).decode()


def decrypt_api_key(org_id: str, ciphertext: str) -> str:
    # Also strip on the way out so keys stored BEFORE the encrypt-time strip above
    # (already-saved dirty keys) are usable without a data migration. Safe for
    # every secret we store — none may carry meaningful surrounding whitespace.
    key = derive_org_key(org_id)
    return Fernet(key).decrypt(ciphertext.encode()).decode().strip()
