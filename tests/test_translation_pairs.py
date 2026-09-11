from lamarck_translator.translation_pairs import (
    TranslationPair,
    format_translation_pairs,
    parse_translation_pairs,
)


def test_parse_translation_pairs_preserves_order() -> None:
    source = "Alpha is first. Beta is second."
    response = (
        '{"pairs":['
        '{"source":"Alpha is first.","translation":"Alpha 是第一个。"},'
        '{"source":"Beta is second.","translation":"Beta 是第二个。"}'
        "]}"
    )

    assert parse_translation_pairs(response, source) == [
        TranslationPair("Alpha is first.", "Alpha 是第一个。"),
        TranslationPair("Beta is second.", "Beta 是第二个。"),
    ]


def test_parse_translation_pairs_accepts_json_fence() -> None:
    source = "A short sentence."
    response = (
        "```json\n"
        '{"pairs":[{"source":"A short sentence.","translation":"一个短句。"}]}\n'
        "```"
    )

    pairs = parse_translation_pairs(response, source)
    assert pairs[0].translation == "一个短句。"


def test_parse_screenshot_pairs_uses_recognized_english_source() -> None:
    response = (
        '{"pairs":['
        '{"source":"Text recognized from an image.",'
        '"translation":"从图片中识别出的文字。"}'
        "]}"
    )

    assert parse_translation_pairs(response, None) == [
        TranslationPair("Text recognized from an image.", "从图片中识别出的文字。")
    ]


def test_invalid_screenshot_response_has_no_fake_source_pair() -> None:
    assert parse_translation_pairs("无法识别。", None) == []


def test_invalid_or_incomplete_response_falls_back_to_full_source() -> None:
    source = "First sentence. Second sentence."
    response = (
        '{"pairs":[{"source":"First sentence.",'
        '"translation":"第一句。"}]}'
    )

    assert parse_translation_pairs(response, source) == [
        TranslationPair(source, response)
    ]


def test_format_translation_pairs_is_interleaved() -> None:
    pairs = [
        TranslationPair("English one.", "中文一。"),
        TranslationPair("English two.", "中文二。"),
    ]

    assert format_translation_pairs(pairs) == (
        "English one.\n中文一。\n\nEnglish two.\n中文二。"
    )
