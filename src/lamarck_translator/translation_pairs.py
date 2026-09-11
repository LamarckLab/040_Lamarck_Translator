from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranslationPair:
    source: str
    translation: str


def parse_translation_pairs(
    response_text: str,
    source_text: str | None,
) -> list[TranslationPair]:
    """Parse Codex JSON and optionally validate it against selected source text.

    Screenshot translation has no separately captured source string, so its
    recognized English is accepted directly from the structured response.
    """
    cleaned_response = response_text.strip()
    for candidate in _json_candidates(cleaned_response):
        try:
            payload = json.loads(candidate)
        except (TypeError, ValueError):
            continue

        raw_pairs = payload.get("pairs") if isinstance(payload, dict) else payload
        if not isinstance(raw_pairs, list):
            continue

        pairs: list[TranslationPair] = []
        for item in raw_pairs:
            if not isinstance(item, dict):
                pairs = []
                break
            source = item.get("source")
            translation = item.get("translation")
            if not isinstance(source, str) or not isinstance(translation, str):
                pairs = []
                break
            source = source.strip()
            translation = translation.strip()
            if not source or not translation:
                pairs = []
                break
            pairs.append(TranslationPair(source, translation))

        if pairs and (source_text is None or _covers_source(pairs, source_text)):
            return pairs

    if source_text is None:
        return []
    return [TranslationPair(source_text.strip(), cleaned_response)]


def format_translation_pairs(pairs: list[TranslationPair]) -> str:
    return "\n\n".join(
        f"{pair.source}\n{pair.translation}" for pair in pairs
    )


def _json_candidates(text: str) -> list[str]:
    candidates = [text]
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())

    object_start = text.find("{")
    object_end = text.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(text[object_start : object_end + 1])

    array_start = text.find("[")
    array_end = text.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(text[array_start : array_end + 1])

    return list(dict.fromkeys(candidates))


def _covers_source(pairs: list[TranslationPair], source_text: str) -> bool:
    expected = re.sub(r"\s+", "", source_text)
    returned = re.sub(r"\s+", "", "".join(pair.source for pair in pairs))
    return bool(expected) and returned == expected
