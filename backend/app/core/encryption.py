"""AES-256-GCM encryption for provider API keys.

Provider keys are encrypted at rest in the database. The master key
is loaded from ``ENCRYPTION_KEY`` (base64-encoded 32 bytes) which
should come from Azure Key Vault in production.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings

settings = get_settings()

# Decode the base64 master key
_MASTER_KEY: bytes = base64.b64decode(settings.ENCRYPTION_KEY)


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string with AES-256-GCM.

    Returns a base64-encoded string of ``nonce + ciphertext + tag``.
    """
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(_MASTER_KEY)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Concatenate nonce + ciphertext (tag is appended by GCM)
    return base64.b64encode(nonce + ciphertext).decode("utf-8")


def decrypt(encrypted: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext.

    Expects the format produced by ``encrypt()``: ``nonce (12 bytes) + ciphertext + tag``.
    """
    raw = base64.b64decode(encrypted)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(_MASTER_KEY)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")
