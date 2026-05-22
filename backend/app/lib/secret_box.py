"""
At-rest symmetric encryption for sensitive DB columns (e.g. auth_providers.client_secret).

Key material is stored at <SKILLSHELF_DATA_DIR>/keys/secret_box.key (or the path
pointed to by SKILLSHELF_ENCRYPTION_KEY_PATH). On first start the key is generated
and written with 0600 permissions. Losing this file makes stored secrets unrecoverable.

Encrypted values are prefixed "enc:v1:" so the encoding is versioned and rows written
before encryption was introduced (no prefix) pass through decrypt() unchanged.
"""
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

from app.config import get_settings

logger = logging.getLogger(__name__)

_PREFIX = "enc:v1:"
_fernet: Fernet | None = None


def _key_path() -> Path:
    settings = get_settings()
    override = getattr(settings, "encryption_key_path", None)
    if override:
        return Path(override)
    return Path(settings.data_dir) / "keys" / "secret_box.key"


def _load_or_create_key() -> bytes:
    path = _key_path()
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_bytes(key)
    os.chmod(path, 0o600)
    logger.warning(
        "Generated encryption key at %s — back this up alongside %s. "
        "Losing this file makes stored OIDC client secrets unrecoverable.",
        path,
        get_settings().data_dir,
    )
    return key


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def ensure_key_exists() -> None:
    """Call at startup (before migrations) to guarantee the key file is present."""
    _get_fernet()


def encrypt(plaintext: str) -> str:
    """Encrypt plaintext. Empty strings are returned unchanged."""
    if not plaintext:
        return plaintext
    token = _get_fernet().encrypt(plaintext.encode()).decode()
    return _PREFIX + token


def decrypt(value: str) -> str:
    """Decrypt a stored value. Plaintext rows (no prefix) pass through unchanged."""
    if not value or not value.startswith(_PREFIX):
        return value
    token = value[len(_PREFIX):]
    return _get_fernet().decrypt(token.encode()).decode()


def is_encrypted(value: str) -> bool:
    return bool(value) and value.startswith(_PREFIX)
