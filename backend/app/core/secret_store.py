"""Secret storage helpers for provider credentials.

Local and test environments continue to use encrypted database values.
Production can opt into Azure Key Vault for shared provider secrets.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.encryption import decrypt


class SecretStoreError(RuntimeError):
    """Raised when a provider secret cannot be loaded or stored."""


def use_key_vault_for_global_provider_secrets() -> bool:
    """Return whether shared provider secrets should be stored in Key Vault."""
    settings = get_settings()
    backend_value = (settings.GLOBAL_PROVIDER_SECRET_BACKEND or "").strip().lower()
    return bool(
        (settings.GLOBAL_PROVIDER_SECRETS_IN_KEY_VAULT or backend_value == "azure_key_vault")
        and settings.AZURE_KEY_VAULT_URL
    )


async def resolve_stored_secret(
    secret_ref: str | None,
    encrypted_value: str | None,
) -> str:
    """Resolve a provider secret from Key Vault or the encrypted DB fallback."""
    if secret_ref and use_key_vault_for_global_provider_secrets():
        return await _load_key_vault_secret(secret_ref)

    if encrypted_value:
        return decrypt(encrypted_value)

    raise SecretStoreError("provider secret is not available")


async def store_global_provider_secret(secret_name: str, secret_value: str) -> None:
    """Persist a shared provider secret to Key Vault when enabled."""
    if not use_key_vault_for_global_provider_secrets():
        raise SecretStoreError("Azure Key Vault storage is not enabled")

    client = _build_secret_client()
    await asyncio.to_thread(client.set_secret, secret_name, secret_value)


async def delete_global_provider_secret(secret_name: str) -> None:
    """Delete a shared provider secret from Key Vault when enabled."""
    if not use_key_vault_for_global_provider_secrets():
        raise SecretStoreError("Azure Key Vault storage is not enabled")

    client = _build_secret_client()
    await asyncio.to_thread(client.begin_delete_secret, secret_name)


async def _load_key_vault_secret(secret_name: str) -> str:
    client = _build_secret_client()
    secret = await asyncio.to_thread(client.get_secret, secret_name)
    value = getattr(secret, "value", None)
    if not value:
        raise SecretStoreError(f"secret '{secret_name}' was empty")
    return value


def _build_secret_client():
    settings = get_settings()

    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise SecretStoreError(
            "azure-identity and azure-keyvault-secrets are required for Key Vault secret storage"
        ) from exc

    if not settings.AZURE_KEY_VAULT_URL:
        raise SecretStoreError("AZURE_KEY_VAULT_URL is not configured")

    credential = DefaultAzureCredential()
    return SecretClient(vault_url=settings.AZURE_KEY_VAULT_URL, credential=credential)