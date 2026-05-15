from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from ..config import get_settings


class AuthError(Exception):
    pass


def create_access_token(device_id: str, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict = {
        "sub": device_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
        "typ": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    except JWTError as e:
        raise AuthError(f"invalid token: {e}") from e
    if payload.get("typ") != "access":
        raise AuthError("wrong token type")
    return payload
