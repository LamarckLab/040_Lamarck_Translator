from lamarck_translator.prompts import build_image_prompt, build_text_prompt


def test_text_prompt_preserves_source() -> None:
    prompt = build_text_prompt("TRANSLATE", "  Chain H residue 52  ")
    assert "Chain H residue 52" in prompt
    assert prompt.startswith("TRANSLATE")
    assert '"pairs"' in prompt
    assert '"source"' in prompt
    assert '"translation"' in prompt


def test_image_prompt_mentions_screenshot() -> None:
    prompt = build_image_prompt("TRANSLATE")
    assert "截图" in prompt
    assert '"pairs"' in prompt
    assert '"source"' in prompt
    assert '"translation"' in prompt
    assert "只输出一个合法 JSON 对象" in prompt
