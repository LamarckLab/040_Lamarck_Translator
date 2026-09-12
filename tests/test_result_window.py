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
