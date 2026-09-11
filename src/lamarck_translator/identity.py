from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CodexIdentity:
    auth_mode: str = ""
    email: str = ""
    name: str = ""
    account_id: str = ""

    @property
    def display_text(self) -> str:
        if self.email:
            return f"Signed in as {self.email}"
        if self.name:
            return f"Signed in as {self.name}"
        if self.auth_mode.lower() in {"apikey", "api_key"}:
            return "Signed in with an API key"
        if self.account_id:
            shortened = f"{self.account_id[:8]}…" if len(self.account_id) > 8 else self.account_id
            return f"Signed in to ChatGPT · {shortened}"
        return "Codex account unavailable"


def codex_auth_path() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    root = Path(codex_home).expanduser() if codex_home else Path.home() / ".codex"
    return root / "auth.json"


def load_codex_identity(path: Path | None = None) -> CodexIdentity:
    auth_path = path or codex_auth_path()
    try:
        auth = json.loads(auth_path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValueError):
        return CodexIdentity()

    if not isinstance(auth, dict):
        return CodexIdentity()

    auth_mode = _text(auth.get("auth_mode"))
    tokens = auth.get("tokens") if isinstance(auth.get("tokens"), dict) else {}
    claims = _decode_jwt_payload(_text(tokens.get("id_token")))

    return CodexIdentity(
        auth_mode=auth_mode,
        email=_text(claims.get("email")),
        name=_text(claims.get("name")),
        account_id=_text(tokens.get("account_id")),
    )


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    if not token:
        return {}
    parts = token.split(".")
    if len(parts) < 2:
        return {}

    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeError, ValueError):
        return {}
    return claims if isinstance(claims, dict) else {}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""
