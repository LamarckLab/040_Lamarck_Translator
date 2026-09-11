from __future__ import annotations

import base64
import json
from pathlib import Path

from lamarck_translator.identity import CodexIdentity, load_codex_identity


def _fake_jwt(payload: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"header.{encoded}.signature"


def test_load_codex_identity_reads_only_public_display_fields(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "id_token": _fake_jwt(
                        {"email": "reader@example.com", "name": "Researcher"}
                    ),
                    "access_token": "must-not-be-displayed",
                    "refresh_token": "must-not-be-displayed",
                    "account_id": "account-123456789",
                },
            }
        ),
        encoding="utf-8",
    )

    identity = load_codex_identity(auth_path)

    assert identity.email == "reader@example.com"
    assert identity.display_text == "Signed in as reader@example.com"
    assert "must-not-be-displayed" not in identity.display_text


def test_api_key_login_never_displays_the_key(tmp_path: Path) -> None:
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps({"auth_mode": "apikey", "OPENAI_API_KEY": "secret-key"}),
        encoding="utf-8",
    )

    identity = load_codex_identity(auth_path)

    assert identity.display_text == "Signed in with an API key"
    assert "secret-key" not in identity.display_text


def test_missing_or_invalid_auth_file_is_safe(tmp_path: Path) -> None:
    assert load_codex_identity(tmp_path / "missing.json") == CodexIdentity()

    invalid_path = tmp_path / "auth.json"
    invalid_path.write_text("not json", encoding="utf-8")
    assert load_codex_identity(invalid_path).display_text == "Codex account unavailable"
