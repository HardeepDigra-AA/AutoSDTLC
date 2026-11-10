import hashlib
import secrets

# In-memory session token store: token -> dict(username, role)
SESSIONS: dict[str, dict[str, str]] = {}


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_session(username: str, role: str) -> str:
    token = secrets.token_hex(24)
    SESSIONS[token] = {"username": username, "role": role}
    return token


def get_session(token: str | None) -> dict[str, str] | None:
    if not token:
        return None
    return SESSIONS.get(token)


def delete_session(token: str | None) -> None:
    if token and token in SESSIONS:
        del SESSIONS[token]
