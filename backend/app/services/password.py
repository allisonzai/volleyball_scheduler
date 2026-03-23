from __future__ import annotations
import binascii
import hashlib
import os
import secrets


def hash_password(password: str) -> str:
    """Return a salted PBKDF2-SHA256 hash of the password."""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return binascii.hexlify(salt).decode() + ":" + binascii.hexlify(dk).decode()


def verify_password(password: str, stored_hash: str) -> bool:
    """Return True if password matches the stored hash."""
    try:
        salt_hex, dk_hex = stored_hash.split(":")
        salt = binascii.unhexlify(salt_hex)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return secrets.compare_digest(binascii.hexlify(dk).decode(), dk_hex)
    except Exception:
        return False
