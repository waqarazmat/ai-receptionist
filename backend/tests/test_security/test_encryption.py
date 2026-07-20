import uuid

import pytest
from cryptography.fernet import InvalidToken

from app.security.encryption import decrypt_api_key, derive_org_key, encrypt_api_key


def test_encrypt_then_decrypt_returns_original():
    org_id = str(uuid.uuid4())
    plaintext = "sk-super-secret-api-key"

    ciphertext = encrypt_api_key(org_id, plaintext)

    assert ciphertext != plaintext
    assert decrypt_api_key(org_id, ciphertext) == plaintext


def test_different_org_ids_produce_different_ciphertexts_for_same_plaintext():
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    plaintext = "sk-super-secret-api-key"

    assert derive_org_key(org_a) != derive_org_key(org_b)
    assert encrypt_api_key(org_a, plaintext) != encrypt_api_key(org_b, plaintext)


def test_wrong_org_id_fails_to_decrypt():
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    plaintext = "sk-super-secret-api-key"

    ciphertext = encrypt_api_key(org_a, plaintext)

    with pytest.raises(InvalidToken):
        decrypt_api_key(org_b, ciphertext)
