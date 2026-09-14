from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


DEFAULT_PROMPT = (
    "你是一名严谨的科研文献翻译助手。将用户提供的英文准确翻译为简体中文。"
    "保留蛋白质科学、结构生物学、机器学习和软件工程领域的专业术语、缩写、"
    "公式、残基编号、链名、文件名、路径、命令和参数；必要时在中文术语后用括号保留英文。"
    "不要扩写，不要加入原文没有的信息，不要使用 Markdown 标题，只输出译文。"
)


@dataclass(slots=True)
class AppConfig:
    text_hotkey: str = "Alt+C"
    screenshot_hotkey: str = "Alt+S"
    model: str = "gpt-5.6-sol"
    reasoning_effort: str = "high"
    timeout_seconds: int = 120
    clipboard_wait_ms: int = 220
    restore_clipboard: bool = True
    pair_font_size: int = 15
    prompt: str = DEFAULT_PROMPT


def config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    root = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    return root / "LamarckTranslator" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_path()
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg

    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    allowed = {field.name for field in fields(AppConfig)}
    values = {key: value for key, value in raw.items() if key in allowed}
    return AppConfig(**values)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
