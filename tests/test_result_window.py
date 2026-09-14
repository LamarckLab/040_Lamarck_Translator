from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from lamarck_translator.result_window import (
    HTBOTTOM,
    HTBOTTOMLEFT,
    HTBOTTOMRIGHT,
    HTCLIENT,
    HTLEFT,
    HTRIGHT,
    HTTOP,
    HTTOPLEFT,
    HTTOPRIGHT,
    ResultWindow,
    TranslationPairCard,
    format_backend_info,
    resize_hit_test,
)


def test_backend_info_line_names_the_model_and_effort_in_use() -> None:
    assert format_backend_info("gpt-5.6-sol", "high") == (
        "Powered by Codex  ·  gpt-5.6-sol  ·  high effort"
    )
    # an empty model means "whatever Codex defaults to"
    assert format_backend_info("", "high") == (
        "Powered by Codex  ·  Codex default model  ·  high effort"
    )
    # an empty effort is not passed to codex, so it is not advertised either
    assert format_backend_info("gpt-5.6-sol", "  ") == "Powered by Codex  ·  gpt-5.6-sol"


def test_result_window_is_not_permanently_on_top() -> None:
    # It must drop behind whatever the user clicks next, or it covers the text
    # they are trying to select for the next translation.
    QApplication.instance() or QApplication([])
    window = ResultWindow()

    flags = window.windowFlags()
    assert not (flags & Qt.WindowType.WindowStaysOnTopHint)
    assert flags & Qt.WindowType.FramelessWindowHint
    window.close()


def test_launching_opens_a_ready_window_instead_of_only_a_tray_icon() -> None:
    QApplication.instance() or QApplication([])
    window = ResultWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

    window.show_welcome()

    assert window.isVisible()
    assert window.status.text() == "Ready"
    assert window.status_pill.property("state") == "ready"
    assert not window.copy_button.isEnabled(), "there is nothing to copy yet"
    body = window.message_output.toPlainText()
    assert "Alt+C" in body and "Alt+S" in body
    window.close()


def test_an_open_window_is_not_dragged_to_the_cursor_again() -> None:
    # A translation moves through loading -> result. Only the first of those
    # may place the window, or it jumps to wherever the pointer drifted and
    # undoes any move the user made while waiting.
    QApplication.instance() or QApplication([])
    window = ResultWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

    window.show_loading("Translating…")
    window.move(140, 160)

    window.show_result("the translation arrives a few seconds later")

    assert (window.x(), window.y()) == (140, 160)
    window.close()


def test_a_hidden_window_is_placed_at_the_cursor_again() -> None:
    QApplication.instance() or QApplication([])
    window = ResultWindow()
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    placed: list[int] = []
    window._move_near_cursor = lambda: placed.append(1)

    window.show_result("first")
    window.hide()
    window.show_result("second")

    assert placed == [1, 1], "each fresh popup places itself, repeats do not"
    window.close()


def test_header_subtitle_follows_the_configured_backend() -> None:
    QApplication.instance() or QApplication([])
    window = ResultWindow()

    window.set_backend_info("gpt-5.6-sol", "high")

    assert window.subtitle_label.text() == (
        "Powered by Codex  ·  gpt-5.6-sol  ·  high effort"
    )
    window.close()


def test_bilingual_result_builds_linked_pair_cards() -> None:
    app = QApplication.instance() or QApplication([])
    window = ResultWindow()
    window._show_near_cursor = lambda: None
    window.set_account_identity("Signed in as reader@example.com")
    response = (
        '{"pairs":['
        '{"source":"First sentence.","translation":"第一句。"},'
        '{"source":"Second sentence.","translation":"第二句。"}'
        "]}"
    )

    window.show_bilingual_result("First sentence. Second sentence.", response)
    app.processEvents()

    cards = window.findChildren(TranslationPairCard)
    assert len(cards) == 2
    assert cards[0].source_label.text() == "First sentence."
    assert cards[0].translation_label.text() == "第一句。"
    assert window.account_label.text() == "Signed in as reader@example.com"
    assert window._copy_text == (
        "First sentence.\n第一句。\n\nSecond sentence.\n第二句。"
    )

    cards[0]._set_hovered(True)
    assert cards[0].property("hovered") is True

    window.close()


def test_screenshot_result_uses_recognized_source_in_bilingual_cards() -> None:
    app = QApplication.instance() or QApplication([])
    window = ResultWindow()
    window._show_near_cursor = lambda: None
    response = (
        '{"pairs":[{"source":"Screenshot sentence.",'
        '"translation":"截图中的句子。"}]}'
    )

    window.show_bilingual_result(None, response)
    app.processEvents()

    cards = window.findChildren(TranslationPairCard)
    assert len(cards) == 1
    assert cards[0].source_label.text() == "Screenshot sentence."
    assert cards[0].translation_label.text() == "截图中的句子。"
    assert window._copy_text == "Screenshot sentence.\n截图中的句子。"
    assert window.copy_button.text() == "Copy bilingual text"

    window.close()


def test_custom_title_bar_buttons_are_centered_and_work() -> None:
    app = QApplication.instance() or QApplication([])
    window = ResultWindow()
    window.show()
    app.processEvents()

    assert window.windowFlags() & Qt.WindowType.FramelessWindowHint
    minimize_center = window.title_bar.minimize_button.geometry().center().y()
    maximize_center = window.title_bar.maximize_button.geometry().center().y()
    button_center = window.title_bar.close_button.geometry().center().y()
    title_bar_center = window.title_bar.rect().center().y()
    assert abs(minimize_center - title_bar_center) <= 1
    assert abs(maximize_center - title_bar_center) <= 1
    assert abs(button_center - title_bar_center) <= 1
    assert (
        window.title_bar.minimize_button.geometry().right()
        < window.title_bar.maximize_button.geometry().left()
    )
    assert (
        window.title_bar.maximize_button.geometry().right()
        < window.title_bar.close_button.geometry().left()
    )

    window.title_bar.minimize_button.click()
    app.processEvents()
    assert window.isMinimized()
    window.showNormal()
    app.processEvents()

    window.title_bar.maximize_button.click()
    app.processEvents()
    assert window.isMaximized()
    assert window.title_bar.maximize_button.toolTip() == "Restore"

    window.title_bar.maximize_button.click()
    app.processEvents()
    assert not window.isMaximized()
    assert window.title_bar.maximize_button.toolTip() == "Maximize"

    window.title_bar.close_button.click()
    app.processEvents()
    assert not window.isVisible()


def test_success_status_updates_pill_and_child_widgets() -> None:
    QApplication.instance() or QApplication([])
    window = ResultWindow()

    window._set_status("Complete", "success")

    assert window.status_pill.property("state") == "success"
    assert window.status.text() == "Complete"
    assert window.status_dot.styleSheet() == ""
    window.close()


def test_frameless_window_edges_have_standard_resize_hit_zones() -> None:
    width, height, border = 760, 550, 9

    assert resize_hit_test(0, 0, width, height, border) == HTTOPLEFT
    assert resize_hit_test(width - 1, 0, width, height, border) == HTTOPRIGHT
    assert resize_hit_test(0, height - 1, width, height, border) == HTBOTTOMLEFT
    assert (
        resize_hit_test(width - 1, height - 1, width, height, border)
        == HTBOTTOMRIGHT
    )
    assert resize_hit_test(0, 100, width, height, border) == HTLEFT
    assert resize_hit_test(width - 1, 100, width, height, border) == HTRIGHT
    assert resize_hit_test(100, 0, width, height, border) == HTTOP
    assert resize_hit_test(100, height - 1, width, height, border) == HTBOTTOM
    assert resize_hit_test(100, 100, width, height, border) == HTCLIENT


def test_ctrl_wheel_resizes_the_sentence_text_and_plain_wheel_does_not() -> None:
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent

    app = QApplication.instance() or QApplication([])
    window = ResultWindow()
    window._show_near_cursor = lambda: None
    window.show_bilingual_result(
        "Alpha. Beta.",
        '{"pairs":[{"source":"Alpha.","translation":"甲。"},'
        '{"source":"Beta.","translation":"乙。"}]}',
    )
    app.processEvents()
    start = window.pair_font_size()

    def wheel(delta: int, modifier: Qt.KeyboardModifier) -> None:
        viewport = window.pairs_scroll.viewport()
        event = QWheelEvent(
            QPointF(10, 10), viewport.mapToGlobal(QPoint(10, 10)),
            QPoint(0, 0), QPoint(0, delta),
            Qt.MouseButton.NoButton, modifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        app.sendEvent(viewport, event)
        app.processEvents()

    wheel(120, Qt.KeyboardModifier.ControlModifier)
    assert window.pair_font_size() == start + 1, "ctrl + wheel up enlarges"
    wheel(-120, Qt.KeyboardModifier.ControlModifier)
    wheel(-120, Qt.KeyboardModifier.ControlModifier)
    assert window.pair_font_size() == start - 1, "ctrl + wheel down shrinks"

    before = window.pair_font_size()
    wheel(120, Qt.KeyboardModifier.NoModifier)
    assert window.pair_font_size() == before, "a plain wheel scrolls, it does not zoom"

    # every card follows, and the size survives the next translation
    cards = window.findChildren(TranslationPairCard)
    assert all(f"font-size: {before}px" in c.source_label.styleSheet() for c in cards)
    window.show_bilingual_result(
        "Gamma.", '{"pairs":[{"source":"Gamma.","translation":"丙。"}]}'
    )
    app.processEvents()
    fresh = window.findChildren(TranslationPairCard)
    assert f"font-size: {before}px" in fresh[0].translation_label.styleSheet()
    window.close()


def test_pair_font_size_is_clamped_to_a_readable_range() -> None:
    from lamarck_translator.result_window import (
        MAX_PAIR_FONT_PX, MIN_PAIR_FONT_PX, clamp_pair_font_size,
    )

    assert clamp_pair_font_size(2) == MIN_PAIR_FONT_PX
    assert clamp_pair_font_size(999) == MAX_PAIR_FONT_PX
    assert clamp_pair_font_size(18) == 18


def test_both_palettes_cover_every_placeholder_in_the_sheet() -> None:
    from lamarck_translator.result_window import (
        DARK_PALETTE, LIGHT_PALETTE, WINDOW_STYLE_TEMPLATE, build_window_style,
    )
    import re

    placeholders = set(re.findall(r"\$(\w+)", WINDOW_STYLE_TEMPLATE.template))
    assert placeholders <= set(LIGHT_PALETTE), "light palette is missing a token"
    assert set(LIGHT_PALETTE) == set(DARK_PALETTE), "the palettes have drifted apart"
    for theme in ("light", "dark"):
        sheet = build_window_style(theme)
        assert "$" not in sheet, f"{theme} left a placeholder unsubstituted"
    assert build_window_style("light") != build_window_style("dark")


def test_toggling_repaints_and_flips_the_button_icon() -> None:
    QApplication.instance() or QApplication([])
    window = ResultWindow()

    window.set_theme("light")
    assert window.painted_theme() == "light"
    assert window.title_bar.theme_button._dark is False
    light_sheet = window.styleSheet()

    window.toggle_theme()
    assert window.theme() == "dark", "the button pins an explicit theme"
    assert window.painted_theme() == "dark"
    assert window.title_bar.theme_button._dark is True
    assert window.styleSheet() != light_sheet

    window.toggle_theme()
    assert window.painted_theme() == "light"
    window.close()


def test_unknown_theme_names_fall_back_to_following_the_system() -> None:
    from lamarck_translator.result_window import resolve_theme

    QApplication.instance() or QApplication([])
    window = ResultWindow()

    window.set_theme("solarized")

    assert window.theme() == "system"
    assert window.painted_theme() == resolve_theme("system")
    assert window.painted_theme() in ("light", "dark")
    window.close()
