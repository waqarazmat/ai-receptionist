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
    key = derive_org_key(org_id)
    return Fernet(key).encrypt(plaintext.encode()).decode()


def decrypt_api_key(org_id: str, ciphertext: str) -> str:
    key = derive_org_key(org_id)
    return Fernet(key).decrypt(ciphertext.encode()).decode()
