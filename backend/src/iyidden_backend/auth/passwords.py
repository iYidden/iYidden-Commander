"""Argon2id wrapper. Used for the mashpia PIN, the backup password, and any
other secret we hash and verify rather than encrypt."""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(secret: str) -> str:
    return _hasher.hash(secret)


def verify_password(hashed: str, secret: str) -> bool:
    try:
        _hasher.verify(hashed, secret)
        return True
    except VerifyMismatchError:
        return False
