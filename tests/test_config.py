from pathlib import Path

from lamarck_translator.config import AppConfig, load_config, save_config


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    expected = AppConfig(model="test-model", clipboard_wait_ms=350)
    save_config(expected, path)
    assert load_config(path) == expected


def test_unknown_config_keys_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"model": "demo", "future_key": true}', encoding="utf-8")
    assert load_config(path).model == "demo"

