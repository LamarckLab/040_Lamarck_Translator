from __future__ import annotations

import ctypes
import math
import sys
from string import Template
from ctypes import wintypes

from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QTextOption,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .history import DONE, FAILED, RUNNING, SCREENSHOT, SELECTION, History, TranslationJob
from .translation_pairs import TranslationPair, format_translation_pairs, parse_translation_pairs


WM_NCHITTEST = 0x0084
HTCLIENT = 1
HTLEFT = 10
HTRIGHT = 11
HTTOP = 12
HTTOPLEFT = 13
HTTOPRIGHT = 14
HTBOTTOM = 15
HTBOTTOMLEFT = 16
HTBOTTOMRIGHT = 17
RESIZE_BORDER_DIP = 7

DEFAULT_PAIR_FONT_PX = 15
MIN_PAIR_FONT_PX = 10
MAX_PAIR_FONT_PX = 32
# Pointer slack that still counts as a click rather than a text drag.
CLICK_SLOP_PX = 4
# Centre of the drawn status mark inside a history tab.
STATUS_ICON_X = 15

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010


def resize_hit_test(
    x: int, y: int, width: int, height: int, border: int
) -> int:
    """Return the Windows non-client hit code for a frameless window edge."""
    on_left = x < border
    on_right = x >= width - border
    on_top = y < border
    on_bottom = y >= height - border

    if on_top and on_left:
        return HTTOPLEFT
    if on_top and on_right:
        return HTTOPRIGHT
    if on_bottom and on_left:
        return HTBOTTOMLEFT
    if on_bottom and on_right:
        return HTBOTTOMRIGHT
    if on_left:
        return HTLEFT
    if on_right:
        return HTRIGHT
    if on_top:
        return HTTOP
    if on_bottom:
        return HTBOTTOM
    return HTCLIENT


def format_backend_info(model: str, effort: str) -> str:
    """Subtitle line naming the model and effort every translation actually uses."""
    # The raw config values are shown verbatim, so the header can never drift
    # from what is handed to codex exec.
    parts = ["Powered by Codex", model.strip() or "Codex default model"]
    if effort.strip():
        parts.append(f"{effort.strip()} effort")
    return "  ·  ".join(parts)


LIGHT_PALETTE = {
    "accent": "#315EFB",
    "accent_text": "#315EFB",
    "accent_hover": "#274FD8",
    "accent_pressed": "#1F43BE",
    "account_fg": "#5B47A8",
    "bg": "#F4F7FB",
    "body_fg": "#202A3D",
    "btn_bg": "#FFFFFF",
    "btn_border": "#D7DFEB",
    "btn_disabled_bg": "#E9EDF4",
    "btn_fg": "#354159",
    "btn_hover_bg": "#F3F6FB",
    "btn_hover_border": "#B9C5D7",
    "card": "#FFFFFF",
    "card_border": "#E3E9F2",
    "close_hover_bg": "#FCE8EA",
    "close_hover_fg": "#C43242",
    "close_pressed_bg": "#F7D5D9",
    "close_pressed_fg": "#A92332",
    "disabled_fg": "#A2ABBA",
    "ghost_fg": "#6A768C",
    "ghost_hover_fg": "#29364F",
    "hint_fg": "#929CAF",
    "muted": "#78849A",
    "on_accent": "#FFFFFF",
    "pair_border": "#E5EAF2",
    "pair_hover_bg": "#F2EEFF",
    "pair_marked_bg": "#E8F7EE",
    "pair_marked_border": "#8ED2AD",
    "pair_marked_hover_bg": "#D5EEE0",
    "pair_marked_hover_border": "#5CBE8C",
    "pair_marked_source": "#12613C",
    "pair_marked_translation": "#2A7550",
    "pair_hover_border": "#AF9BFA",
    "pair_hover_source": "#40269A",
    "pair_hover_translation": "#5A3FB0",
    "pill_err_bg": "#FFF0F0",
    "pill_err_border": "#FFD7D7",
    "pill_err_fg": "#C83C4A",
    "pill_ok_bg": "#EAF8F1",
    "pill_ok_border": "#CDEDDD",
    "pill_ok_fg": "#17855B",
    "pill_ready_bg": "#EEF3FF",
    "pill_ready_border": "#DCE6FF",
    "pressed_fill": "#DDE4EF",
    "raised": "#FBFCFE",
    "scroll_handle": "#CAD2E0",
    "scroll_handle_hover": "#9D8FE0",
    "section_fg": "#4B5870",
    "selection_bg": "#C9D7FF",
    "subtle_hover": "#E9EEF6",
    "tab_active_bg": "#FFFFFF",
    "tab_active_fg": "#25304A",
    "tab_bg": "#EDF1F7",
    "tab_fg": "#6A768C",
    "text": "#172033",
    "text_strong": "#25304A",
    "title_fg": "#16213A",
    "titlebar_border": "#E4E9F1",
    "titlebar_fg": "#5D687C",
    "translation_fg": "#536078",
    "wbtn_fg": "#6C7689",
    "window_border": "#DDE4EF",
}

DARK_PALETTE = {
    "accent": "#3D6AF0",
    "accent_text": "#86A8FF",
    "accent_hover": "#3E6BF0",
    "accent_pressed": "#345CD8",
    "account_fg": "#B49CFF",
    "bg": "#141922",
    "body_fg": "#D6DEEA",
    "btn_bg": "#232A36",
    "btn_border": "#38414F",
    "btn_disabled_bg": "#1E242E",
    "btn_fg": "#D6DEEA",
    "btn_hover_bg": "#2A323F",
    "btn_hover_border": "#4A5566",
    "card": "#1C222D",
    "card_border": "#2C3542",
    "close_hover_bg": "#3A2228",
    "close_hover_fg": "#FF8A96",
    "close_pressed_bg": "#4A2A31",
    "close_pressed_fg": "#FFA3AC",
    "disabled_fg": "#5A6473",
    "ghost_fg": "#8B96A9",
    "ghost_hover_fg": "#DDE4EF",
    "hint_fg": "#6E7889",
    "muted": "#8B96A9",
    "on_accent": "#FFFFFF",
    "pair_border": "#333D4C",
    "pair_hover_bg": "#272040",
    "pair_marked_bg": "#17301F",
    "pair_marked_border": "#2F6B47",
    "pair_marked_hover_bg": "#1E3F2B",
    "pair_marked_hover_border": "#439762",
    "pair_marked_source": "#8FE3B4",
    "pair_marked_translation": "#77C89C",
    "pair_hover_border": "#7C63DE",
    "pair_hover_source": "#CDBCFF",
    "pair_hover_translation": "#B3A2F0",
    "pill_err_bg": "#32181C",
    "pill_err_border": "#50252B",
    "pill_err_fg": "#FF7E8B",
    "pill_ok_bg": "#14291F",
    "pill_ok_border": "#22432F",
    "pill_ok_fg": "#52C08C",
    "pill_ready_bg": "#1D2740",
    "pill_ready_border": "#2E3C61",
    "pressed_fill": "#313B4A",
    "raised": "#212734",
    "scroll_handle": "#39424F",
    "scroll_handle_hover": "#7C63DE",
    "section_fg": "#A6B1C3",
    "selection_bg": "#2F4479",
    "subtle_hover": "#272F3C",
    "tab_active_bg": "#2B333F",
    "tab_active_fg": "#E9EEF6",
    "tab_bg": "#20262F",
    "tab_fg": "#8B96A9",
    "text": "#E4EAF3",
    "text_strong": "#E9EEF6",
    "title_fg": "#F0F4FA",
    "titlebar_border": "#262E3A",
    "titlebar_fg": "#96A1B3",
    "translation_fg": "#A9B5C7",
    "wbtn_fg": "#8C97A8",
    "window_border": "#2B3340",
}

THEMES = {"light": LIGHT_PALETTE, "dark": DARK_PALETTE}


WINDOW_STYLE_TEMPLATE = Template("""
QWidget#resultWindow {
    background: $bg;
    color: $text;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    border: 1px solid $window_border;
}
QFrame#titleBar {
    background: $raised;
    border: none;
    border-bottom: 1px solid $titlebar_border;
}
QLabel#titleBarIcon {
    background: transparent;
    border: none;
}
QLabel#windowTitleLabel {
    color: $titlebar_fg;
    background: transparent;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#windowCloseButton,
QPushButton#windowThemeButton,
QPushButton#windowMinimizeButton,
QPushButton#windowMaximizeButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
    border: none;
    border-radius: 7px;
    background: transparent;
    color: $wbtn_fg;
    font-family: "Segoe UI Symbol", "Segoe UI";
    font-size: 17px;
    font-weight: 400;
}
QPushButton#windowThemeButton:hover,
QPushButton#windowMinimizeButton:hover, QPushButton#windowMaximizeButton:hover {
    background: $subtle_hover;
    color: $text_strong;
}
QPushButton#windowThemeButton:pressed,
QPushButton#windowMinimizeButton:pressed, QPushButton#windowMaximizeButton:pressed {
    background: $pressed_fill;
    color: $text;
}
QPushButton#windowCloseButton:hover {
    background: $close_hover_bg;
    color: $close_hover_fg;
}
QPushButton#windowCloseButton:pressed {
    background: $close_pressed_bg;
    color: $close_pressed_fg;
}
QWidget#windowBody {
    background: $bg;
    border: none;
}
QFrame#headerCard, QFrame#contentCard {
    background: $card;
    border: 1px solid $card_border;
    border-radius: 14px;
}
QLabel#brandMark {
    background: transparent;
    border: none;
}
QLabel#titleLabel {
    color: $title_fg;
    font-size: 20px;
    font-weight: 700;
}
QLabel#subtitleLabel {
    color: $muted;
    font-size: 11px;
}
QLabel#accountLabel {
    color: $account_fg;
    font-size: 11px;
    font-weight: 600;
}
QLabel#creditLabel {
    color: $account_fg;
    background: transparent;
    font-size: 11px;
    font-weight: 600;
}
QFrame#statusPill {
    border-radius: 12px;
    padding: 0 10px;
}
QFrame#statusPill[state="ready"], QFrame#statusPill[state="loading"] {
    background: $pill_ready_bg;
    border: 1px solid $pill_ready_border;
}
QFrame#statusPill[state="success"] {
    background: $pill_ok_bg;
    border: 1px solid $pill_ok_border;
}
QFrame#statusPill[state="error"] {
    background: $pill_err_bg;
    border: 1px solid $pill_err_border;
}
QLabel#statusDot, QLabel#statusText {
    color: $accent_text;
    font-size: 12px;
    font-weight: 600;
}
QFrame#statusPill[state="success"] QLabel {
    color: $pill_ok_fg;
}
QFrame#statusPill[state="error"] QLabel {
    color: $pill_err_fg;
}
QWidget#historyStrip {
    background: transparent;
    border: none;
}
QPushButton#historyTab {
    outline: none;
    min-height: 26px;
    max-height: 26px;
    min-width: 86px;
    max-width: 86px;
    padding: 0 10px 0 28px;
    border: 1px solid $card_border;
    border-radius: 7px;
    background: $tab_bg;
    color: $tab_fg;
    font-size: 11px;
    font-weight: 600;
    text-align: left;
}
QPushButton#historyTab:hover {
    background: $subtle_hover;
    color: $tab_active_fg;
}
QPushButton#historyTab:checked {
    background: $tab_active_bg;
    border-color: $accent;
    color: $tab_active_fg;
}
QLabel#sectionLabel {
    color: $section_fg;
    font-size: 12px;
    font-weight: 600;
}
QTextBrowser#messageOutput {
    background: transparent;
    border: none;
    color: $body_fg;
    selection-background-color: $selection_bg;
    selection-color: $text;
    font-size: 16px;
}
QStackedWidget#contentStack, QScrollArea#pairsScroll, QWidget#pairsContainer {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    width: 10px;
    margin: 2px 0;
    background: transparent;
    border: none;
}
QScrollBar::handle:vertical {
    min-height: 34px;
    background: $scroll_handle;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: $scroll_handle_hover;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    width: 0;
    height: 0;
    background: transparent;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QFrame#translationPairCard {
    background: $raised;
    border: 1px solid $pair_border;
    border-radius: 11px;
}
QFrame#translationPairCard[hovered="true"] {
    background: $pair_hover_bg;
    border-color: $pair_hover_border;
}
QLabel#sourceText {
    color: $text_strong;
    font-family: "Segoe UI", "Arial";
    font-size: 15px;
    font-weight: 600;
    background: transparent;
}
QLabel#translationText {
    color: $translation_fg;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 15px;
    background: transparent;
}
QFrame#translationPairCard[hovered="true"] QLabel#sourceText {
    color: $pair_hover_source;
}
QFrame#translationPairCard[hovered="true"] QLabel#translationText {
    color: $pair_hover_translation;
}
QFrame#translationPairCard[marked="true"] {
    background: $pair_marked_bg;
    border-color: $pair_marked_border;
}
QFrame#translationPairCard[marked="true"][hovered="true"] {
    background: $pair_marked_hover_bg;
    border-color: $pair_marked_hover_border;
}
QFrame#translationPairCard[marked="true"] QLabel#sourceText {
    color: $pair_marked_source;
}
QFrame#translationPairCard[marked="true"] QLabel#translationText {
    color: $pair_marked_translation;
}
QPushButton {
    min-height: 36px;
    padding: 0 17px;
    border-radius: 8px;
    border: 1px solid $btn_border;
    background: $btn_bg;
    color: $btn_fg;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: $btn_hover_bg;
    border-color: $btn_hover_border;
}
QPushButton:pressed {
    background: $subtle_hover;
}
QPushButton[variant="primary"] {
    color: $on_accent;
    background: $accent;
    border-color: $accent;
}
QPushButton[variant="primary"]:hover {
    background: $accent_hover;
    border-color: $accent_hover;
}
QPushButton[variant="primary"]:pressed {
    background: $accent_pressed;
    border-color: $accent_pressed;
}
QPushButton[variant="ghost"] {
    background: transparent;
    border-color: transparent;
    color: $ghost_fg;
}
QPushButton[variant="ghost"]:hover {
    background: $subtle_hover;
    color: $ghost_hover_fg;
}
QPushButton:disabled {
    background: $btn_disabled_bg;
    border-color: $btn_disabled_bg;
    color: $disabled_fg;
}
QLabel#shortcutHint {
    color: $hint_fg;
    font-size: 11px;
}
""")


def resolve_theme(theme: str) -> str:
    """Map a configured theme onto the one actually painted.

    "system" follows the Windows setting and keeps following it, so the
    window changes with the OS; "light" and "dark" pin it.
    """
    if theme in THEMES:
        return theme
    hints = QGuiApplication.styleHints()
    scheme = hints.colorScheme() if hints is not None else None
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"


def build_window_style(theme: str) -> str:
    """One sheet serves both themes; only the palette put into it changes."""
    return WINDOW_STYLE_TEMPLATE.substitute(THEMES.get(theme, LIGHT_PALETTE))



class CloseButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("windowCloseButton")
        self.setToolTip("Close")
        self.setAccessibleName("Close window")

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = 4.2
        painter.drawLine(
            QPointF(center.x() - radius, center.y() - radius),
            QPointF(center.x() + radius, center.y() + radius),
        )
        painter.drawLine(
            QPointF(center.x() + radius, center.y() - radius),
            QPointF(center.x() - radius, center.y() + radius),
        )


class MinimizeButton(QPushButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("windowMinimizeButton")
        self.setToolTip("Minimize")
        self.setAccessibleName("Minimize window")

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        center = QPointF(self.width() / 2, self.height() / 2 + 2)
        painter.drawLine(
            QPointF(center.x() - 4.5, center.y()),
            QPointF(center.x() + 4.5, center.y()),
        )


class MaximizeRestoreButton(QPushButton):
    def __init__(self, window: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self.setObjectName("windowMaximizeButton")
        self.clicked.connect(self.toggle_window_state)
        self.sync_state()

    def toggle_window_state(self) -> None:
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync_state()

    def sync_state(self) -> None:
        action = "Restore" if self._window.isMaximized() else "Maximize"
        self.setToolTip(action)
        self.setAccessibleName(f"{action} window")
        self.update()

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(QPalette.ColorRole.ButtonText)
        painter.setPen(QPen(color, 1.35, Qt.PenStyle.SolidLine))
        center = QPointF(self.width() / 2, self.height() / 2)
        if self._window.isMaximized():
            # A compact pair of overlapping windows is the conventional
            # Windows restore icon.
            painter.drawLine(
                QPointF(center.x() - 2.5, center.y() - 4.5),
                QPointF(center.x() + 4.0, center.y() - 4.5),
            )
            painter.drawLine(
                QPointF(center.x() + 4.0, center.y() - 4.5),
                QPointF(center.x() + 4.0, center.y() + 2.0),
            )
            painter.drawRect(
                QRectF(center.x() - 4.0, center.y() - 2.0, 8.0, 7.5)
            )
        else:
            painter.drawRect(
                QRectF(center.x() - 4.5, center.y() - 4.5, 9.0, 9.0)
            )


class ThemeButton(QPushButton):
    """Shows the theme it switches TO: a moon in light, a sun in dark."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("windowThemeButton")
        self._dark = False
        self.sync_state()

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.sync_state()

    def sync_state(self) -> None:
        target = "light" if self._dark else "dark"
        self.setToolTip(f"Switch to {target} theme")
        self.setAccessibleName(f"Switch to {target} theme")
        self.update()

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = self.palette().color(QPalette.ColorRole.ButtonText)
        centre = QPointF(self.width() / 2, self.height() / 2)
        if self._dark:
            # sun: filled core plus eight rays
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawEllipse(centre, 3.2, 3.2)
            pen = QPen(colour, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            for index in range(8):
                angle = math.radians(index * 45)
                dx, dy = math.cos(angle), math.sin(angle)
                painter.drawLine(
                    QPointF(centre.x() + dx * 5.2, centre.y() + dy * 5.2),
                    QPointF(centre.x() + dx * 7.0, centre.y() + dy * 7.0),
                )
        else:
            # moon: a disc with a second disc punched out of it
            path = QPainterPath()
            path.addEllipse(centre, 6.2, 6.2)
            bite = QPainterPath()
            bite.addEllipse(QPointF(centre.x() + 3.4, centre.y() - 2.8), 5.6, 5.6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawPath(path.subtracted(bite))


class WindowTitleBar(QFrame):
    def __init__(self, window: QWidget) -> None:
        super().__init__(window)
        self._window = window
        self.setObjectName("titleBar")
        self.setFixedHeight(42)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 9, 6)
        layout.setSpacing(8)

        self.icon_label = QLabel("L")
        self.icon_label.setObjectName("titleBarIcon")
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setFixedSize(20, 20)

        title = QLabel("Lamarck Translator")
        title.setObjectName("windowTitleLabel")

        self.theme_button = ThemeButton()
        self.theme_button.clicked.connect(window.toggle_theme)
        self.minimize_button = MinimizeButton()
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button = MaximizeRestoreButton(window)
        self.close_button = CloseButton()
        self.close_button.clicked.connect(window.hide)
        window.installEventFilter(self)

        layout.addWidget(self.icon_label)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(self.theme_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.minimize_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.maximize_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_icon(self, icon: QIcon) -> None:
        if not icon.isNull():
            self.icon_label.setText("")
            self.icon_label.setPixmap(icon.pixmap(20, 20))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._window.windowHandle()
            if handle is not None:
                handle.startSystemMove()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.maximize_button.toggle_window_state()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        window = getattr(self, "_window", None)
        if watched is window and event.type() == QEvent.Type.WindowStateChange:
            self.maximize_button.sync_state()
        return super().eventFilter(watched, event)


class TranslationPairCard(QFrame):
    def __init__(
        self,
        pair: TranslationPair,
        font_px: int = DEFAULT_PAIR_FONT_PX,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("translationPairCard")
        self.setProperty("hovered", False)
        self.setProperty("marked", False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 12)
        layout.setSpacing(7)

        self.source_label = QLabel(pair.source)
        self.source_label.setObjectName("sourceText")
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setWordWrap(True)
        self.source_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.source_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.translation_label = QLabel(pair.translation)
        self.translation_label.setObjectName("translationText")
        self.translation_label.setTextFormat(Qt.TextFormat.PlainText)
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.translation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(self.source_label)
        layout.addWidget(self.translation_label)

        self.set_font_size(font_px)

        for widget in (self, self.source_label, self.translation_label):
            widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def hover_targets(self) -> tuple[QWidget, ...]:
        """Widgets whose enter and leave events mean "the pointer is on me"."""
        return (self, self.source_label, self.translation_label)

    def set_font_size(self, font_px: int) -> None:
        # A per-widget sheet outranks the window sheet for font-size while
        # leaving its weight, family and colour (including the hover rules)
        # in force, so only the size moves.
        for label in (self.source_label, self.translation_label):
            label.setStyleSheet(f"font-size: {font_px}px;")

    def set_hovered(self, hovered: bool) -> None:
        self._set_state("hovered", hovered)

    def is_marked(self) -> bool:
        return bool(self.property("marked"))

    def toggle_marked(self) -> None:
        """Sticky "I have read this", cleared only by another click."""
        self._set_state("marked", not self.is_marked())

    def _set_state(self, name: str, value: bool) -> None:
        if self.property(name) == value:
            return
        self.setProperty(name, value)
        for widget in (self, self.source_label, self.translation_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()


class PairsPage(QScrollArea):
    """One translation's cards.

    Each job keeps its own page rather than the window rebuilding a single
    list, so green read-marks and scroll position simply stay where they were
    when you switch away and back.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pairsScroll")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        container = QWidget()
        container.setObjectName("pairsContainer")
        self.pairs_layout = QVBoxLayout(container)
        self.pairs_layout.setContentsMargins(2, 2, 6, 2)
        self.pairs_layout.setSpacing(9)
        self.setWidget(container)
        self.container = container

    def cards(self) -> list["TranslationPairCard"]:
        return self.container.findChildren(TranslationPairCard)

    def fill(self, pairs: list[TranslationPair], font_px: int, watcher: QWidget) -> None:
        for card in self.cards():
            card.setParent(None)
            card.deleteLater()
        while self.pairs_layout.count():
            self.pairs_layout.takeAt(0)
        for pair in pairs:
            card = TranslationPairCard(pair, font_px)
            for target in card.hover_targets():
                target.installEventFilter(watcher)
            self.pairs_layout.addWidget(card)
        self.pairs_layout.addStretch(1)


class HistoryTab(QPushButton):
    """One entry in the history strip: a drawn status mark and a clock time.

    The tab does not try to show the translation itself. Five tabs of elided
    source text read as a row of ragged ellipses and still do not say what is
    in them; the time tells them apart and the tooltip carries the text.
    """

    SPIN_MS = 60

    def __init__(self, job_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.job_id = job_id
        self.setObjectName("historyTab")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # A tab is a click target, not a keyboard stop. Taking focus would
        # draw the style's dotted focus rectangle over the tab.
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._status = DONE
        self._seen = True
        self._colors: dict[str, str] = {}
        self._angle = 0
        self._spin = QTimer(self)
        self._spin.setInterval(self.SPIN_MS)
        self._spin.timeout.connect(self._advance_spinner)

    def _advance_spinner(self) -> None:
        self._angle = (self._angle + 24) % 360
        self.update()

    def render_job(self, job: "TranslationJob", active: bool, colors: dict) -> None:
        self._status, self._seen, self._colors = job.status, job.seen, colors
        self.setText(job.started_label())
        self.setChecked(active)
        if job.is_screenshot:
            detail = "Screenshot translation"
        else:
            detail = " ".join((job.source_text or "").split()) or "Selection"
        self.setToolTip(f"{job.started_label()}  ·  {detail}")
        # Only spin while there is something to spin for.
        if job.is_running and not self._spin.isActive():
            self._spin.start()
        elif not job.is_running and self._spin.isActive():
            self._spin.stop()
        self.update()

    def _status_colour(self) -> QColor:
        if self._status == FAILED:
            return QColor(self._colors.get("pill_err_fg", "#C83C4A"))
        if self._status == RUNNING or not self._seen:
            return QColor(self._colors.get("accent_text", "#315EFB"))
        return QColor(self._colors.get("tab_fg", "#6A768C"))

    def paintEvent(self, event: QEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = self._status_colour()
        centre = QPointF(STATUS_ICON_X, self.height() / 2)
        pen = QPen(colour, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                   Qt.PenJoinStyle.RoundJoin)

        if self._status == RUNNING:
            # An arc that turns: a still mark cannot say "in progress".
            painter.setPen(QPen(colour, 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            box = QRectF(centre.x() - 4.4, centre.y() - 4.4, 8.8, 8.8)
            painter.drawArc(box, -self._angle * 16, 260 * 16)
        elif self._status == FAILED:
            painter.setPen(pen)
            r = 3.4
            painter.drawLine(QPointF(centre.x() - r, centre.y() - r),
                             QPointF(centre.x() + r, centre.y() + r))
            painter.drawLine(QPointF(centre.x() + r, centre.y() - r),
                             QPointF(centre.x() - r, centre.y() + r))
        elif not self._seen:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colour)
            painter.drawEllipse(centre, 3.4, 3.4)
        else:
            painter.setPen(pen)
            painter.drawLine(QPointF(centre.x() - 3.9, centre.y() + 0.2),
                             QPointF(centre.x() - 1.2, centre.y() + 2.9))
            painter.drawLine(QPointF(centre.x() - 1.2, centre.y() + 2.9),
                             QPointF(centre.x() + 4.0, centre.y() - 3.0))


def clamp_pair_font_size(font_px: int) -> int:
    return max(MIN_PAIR_FONT_PX, min(MAX_PAIR_FONT_PX, int(font_px)))


class ResultWindow(QWidget):
    retry_requested = Signal()
    pair_font_size_changed = Signal(int)
    theme_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("resultWindow")
        self.setWindowTitle("Lamarck Translator")
        # Deliberately not WindowStaysOnTopHint: the window must drop behind
        # whatever the user clicks next, or it covers the text they want to
        # select. _raise_above_foreground() puts it in front on each show.
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
        )
        self.setMinimumSize(600, 430)
        self.resize(760, 550)
        self._theme = "system"
        self._painted_theme = resolve_theme("system")
        self.setStyleSheet(build_window_style(self._painted_theme))
        self._copy_text = ""
        self._pair_font_px = DEFAULT_PAIR_FONT_PX
        self._press_origin: QPoint | None = None
        self._history = History()
        self._pages: dict[int, PairsPage] = {}
        self._tabs: dict[int, HistoryTab] = {}
        self._active_page: PairsPage | None = None
        self._build_ui()
        self.title_bar.theme_button.set_dark(self._painted_theme == "dark")
        self._set_status("Ready", "ready")
        hints = QGuiApplication.styleHints()
        if hints is not None:
            hints.colorSchemeChanged.connect(self._system_theme_changed)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.title_bar = WindowTitleBar(self)
        root.addWidget(self.title_bar)

        body = QWidget()
        body.setObjectName("windowBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(22, 18, 22, 18)
        body_layout.setSpacing(14)
        root.addWidget(body, 1)

        header = QFrame()
        header.setObjectName("headerCard")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 14, 16, 14)
        header_layout.setSpacing(12)

        self.brand_mark = QLabel("L")
        self.brand_mark.setObjectName("brandMark")
        self.brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_mark.setFixedSize(44, 44)

        title = QLabel("Lamarck Translator")
        title.setObjectName("titleLabel")
        self.subtitle_label = QLabel("Powered by Codex")
        self.subtitle_label.setObjectName("subtitleLabel")
        self.subtitle_label.setToolTip("Model and reasoning effort used for every translation")
        self.account_label = QLabel("Codex account unavailable")
        self.account_label.setObjectName("accountLabel")
        self.account_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.account_label.setToolTip("OpenAI account used by the local Codex CLI")
        title_stack = QVBoxLayout()
        title_stack.setContentsMargins(0, 0, 0, 0)
        title_stack.setSpacing(1)
        title_stack.addWidget(title)
        title_stack.addWidget(self.subtitle_label)
        title_stack.addWidget(self.account_label)

        self.status_pill = QFrame()
        self.status_pill.setObjectName("statusPill")
        self.status_pill.setFixedHeight(28)
        status_layout = QHBoxLayout(self.status_pill)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(6)
        self.status_dot = QLabel("●")
        self.status_dot.setObjectName("statusDot")
        self.status = QLabel()
        self.status.setObjectName("statusText")
        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status)

        header_layout.addWidget(self.brand_mark)
        header_layout.addLayout(title_stack)
        header_layout.addStretch(1)
        header_layout.addWidget(self.status_pill)
        body_layout.addWidget(header)

        card = QFrame()
        card.setObjectName("contentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 14)
        card_layout.setSpacing(8)

        self.section = QLabel("Translation")
        self.section.setObjectName("sectionLabel")

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")

        self.message_output = QTextBrowser()
        self.message_output.setObjectName("messageOutput")
        self.message_output.setOpenExternalLinks(True)
        self.message_output.setFrameShape(QFrame.Shape.NoFrame)
        self.message_output.setFont(QFont("Microsoft YaHei UI", 11))
        self.message_output.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.message_output.document().setDocumentMargin(2)

        self.history_strip = QWidget()
        self.history_strip.setObjectName("historyStrip")
        self.history_layout = QHBoxLayout(self.history_strip)
        self.history_layout.setContentsMargins(0, 0, 0, 2)
        self.history_layout.setSpacing(6)
        self.history_strip.hide()

        self.content_stack.addWidget(self.message_output)
        card_layout.addWidget(self.history_strip)
        card_layout.addWidget(self.section)
        card_layout.addWidget(self.content_stack, 1)

        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(28, 46, 82, 24))
        card.setGraphicsEffect(shadow)
        body_layout.addWidget(card, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        hint = QLabel("Alt+C  Translate    ·    Alt+S  Screenshot    ·    Esc  Close")
        hint.setObjectName("shortcutHint")

        self.copy_button = QPushButton("Copy translation")
        self.copy_button.setProperty("variant", "primary")
        self.copy_button.clicked.connect(self.copy_output)
        self.retry_button = QPushButton("Retry")
        self.retry_button.setMinimumWidth(88)
        self.retry_button.setToolTip("Run the translation again")
        self.retry_button.clicked.connect(self.retry_requested)
        self.copy_button.setMinimumWidth(184)
        self.close_button = QPushButton("Close")
        self.close_button.setMinimumWidth(82)
        self.close_button.setToolTip("Hide this window")
        self.close_button.clicked.connect(self.hide)

        self.credit_label = QLabel("Developed by L. Mingkai")
        self.credit_label.setObjectName("creditLabel")
        self.credit_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        hint_stack = QVBoxLayout()
        hint_stack.setContentsMargins(0, 0, 0, 0)
        hint_stack.setSpacing(3)
        hint_stack.addWidget(hint)
        hint_stack.addWidget(self.credit_label)

        footer.addLayout(hint_stack)
        footer.addStretch(1)
        footer.addWidget(self.retry_button)
        footer.addWidget(self.copy_button)
        footer.addWidget(self.close_button)
        body_layout.addLayout(footer)

    def set_brand_icon(self, icon: QIcon) -> None:
        if not icon.isNull():
            self.brand_mark.setText("")
            self.brand_mark.setPixmap(icon.pixmap(44, 44))
            self.title_bar.set_icon(icon)

    def set_account_identity(self, text: str) -> None:
        self.account_label.setText(text or "Codex account unavailable")

    def theme(self) -> str:
        return self._theme

    def painted_theme(self) -> str:
        return self._painted_theme

    def set_theme(self, theme: str, announce: bool = False) -> None:
        if theme not in THEMES and theme != "system":
            theme = "system"
        self._theme = theme
        self._repaint_theme()
        if announce:
            self.theme_changed.emit(theme)

    def toggle_theme(self) -> None:
        """The button always pins an explicit theme, never back to system."""
        self.set_theme("light" if self._painted_theme == "dark" else "dark", announce=True)

    def _system_theme_changed(self) -> None:
        if self._theme == "system":
            self._repaint_theme()

    def _repaint_theme(self) -> None:
        painted = resolve_theme(self._theme)
        if painted == self._painted_theme and self.styleSheet():
            return
        self._painted_theme = painted
        self.setStyleSheet(build_window_style(painted))
        self.title_bar.theme_button.set_dark(painted == "dark")
        self._rebuild_history()
        # The status pill paints from a dynamic property, so it needs a
        # re-polish to pick the new palette up.
        for widget in (self.status_pill, self.status_dot, self.status):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.update()

    # ---- translation history ------------------------------------------
    def active_job(self) -> TranslationJob | None:
        return self._history.active

    def add_job(
        self,
        mode: str,
        prompt: str,
        label: str,
        source_text: str | None = None,
        image_path: Path | None = None,
    ) -> TranslationJob:
        """Register a translation that has just been sent."""
        # Starting one translation must not take the screen away from a
        # finished one being read; that is the whole point of running the next
        # passage while you read this one.
        reading = self._is_reading_result()
        job, evicted = self._history.add(mode, prompt, label, source_text, image_path)
        for gone in evicted:
            page = self._pages.pop(gone.job_id, None)
            if page is not None:
                self.content_stack.removeWidget(page)
                page.deleteLater()
        if not reading:
            self._history.activate(job.job_id)
        self._rebuild_history()
        self._render_active()
        self._show_near_cursor()
        return job

    def complete_job(self, job_id: int, response: str) -> None:
        job = self._history.complete(job_id, response)
        if job is None:
            return
        job.pairs = parse_translation_pairs(response, job.source_text)
        if not job.pairs:
            self._history.fail(
                job_id,
                "No recognizable English-Chinese sentence pairs were returned. "
                "Please try again, or capture the area again.",
            )
        else:
            page = PairsPage()
            page.viewport().installEventFilter(self)
            page.verticalScrollBar().valueChanged.connect(self._schedule_pair_hover_sync)
            page.fill(job.pairs, self._pair_font_px, self)
            self._pages[job_id] = page
            self.content_stack.addWidget(page)
        self._settle_job(job)

    def fail_job(self, job_id: int, error: str) -> None:
        job = self._history.fail(job_id, error)
        if job is not None:
            self._settle_job(job)

    def _settle_job(self, job: TranslationJob) -> None:
        self._rebuild_history()
        active = self._history.active
        if active is not None and active.job_id == job.job_id:
            self._render_active()
            self._show_near_cursor()
        # Otherwise the tab keeps its unread dot and the reader is left alone.

    def _is_reading_result(self) -> bool:
        job = self._history.active
        return bool(self.isVisible() and job is not None and job.status == DONE)

    def _activate_job(self, job_id: int) -> None:
        if self._history.activate(job_id) is None:
            return
        self._rebuild_history()
        self._render_active()

    def _rebuild_history(self) -> None:
        jobs = self._history.jobs
        palette = THEMES.get(self._painted_theme, LIGHT_PALETTE)
        active = self._history.active
        active_id = active.job_id if active else None
        for job_id, tab in list(self._tabs.items()):
            if self._history.get(job_id) is None:
                self.history_layout.removeWidget(tab)
                tab.deleteLater()
                del self._tabs[job_id]
        for job in jobs:
            tab = self._tabs.get(job.job_id)
            if tab is None:
                tab = HistoryTab(job.job_id)
                tab.clicked.connect(lambda _=False, i=job.job_id: self._activate_job(i))
                self._tabs[job.job_id] = tab
                self.history_layout.addWidget(tab)
            tab.render_job(job, job.job_id == active_id, palette)
        # One translation needs no strip; it would be a label for itself.
        self.history_strip.setVisible(len(jobs) > 1)

    def _render_active(self) -> None:
        job = self._history.active
        if job is None:
            return
        self.retry_button.setEnabled(job.can_retry)
        if job.is_running:
            self._set_status(job.label, "loading")
            self.section.setText("Translation")
            self.message_output.setPlainText(
                "Waiting for Codex to return a translation…"
            )
            self.content_stack.setCurrentWidget(self.message_output)
            self._copy_text = ""
            self.copy_button.setEnabled(False)
            self._active_page = None
            return
        if job.status == FAILED:
            self._set_status("Failed", "error")
            self.section.setText("Message")
            self.message_output.setPlainText(job.error)
            self.content_stack.setCurrentWidget(self.message_output)
            self._copy_text = ""
            self.copy_button.setEnabled(False)
            self._active_page = None
            return
        page = self._pages.get(job.job_id)
        if page is None:
            return
        self._copy_text = format_translation_pairs(job.pairs)
        self.section.setText("Bilingual translation")
        self.copy_button.setText("Copy bilingual text")
        self.copy_button.setEnabled(bool(self._copy_text))
        self._set_status("Complete", "success")
        self.content_stack.setCurrentWidget(page)
        self._active_page = page
        self._schedule_pair_hover_sync()

    def set_backend_info(self, model: str, effort: str) -> None:
        self.subtitle_label.setText(format_backend_info(model, effort))

    def pair_font_size(self) -> int:
        return self._pair_font_px

    def set_pair_font_size(self, font_px: int, announce: bool = False) -> None:
        font_px = clamp_pair_font_size(font_px)
        if font_px == self._pair_font_px:
            return
        self._pair_font_px = font_px
        for page in self._pages.values():
            for card in page.cards():
                card.set_font_size(font_px)
            # Cards keep their old height until the layout re-measures them.
            page.container.adjustSize()
        self._schedule_pair_hover_sync()
        if announce:
            self.pair_font_size_changed.emit(font_px)

    @staticmethod
    def _card_for(widget: object) -> "TranslationPairCard | None":
        """The card a click landed on, whether on it or on one of its labels."""
        while isinstance(widget, QWidget):
            if isinstance(widget, TranslationPairCard):
                return widget
            widget = widget.parentWidget()
        return None

    def _schedule_pair_hover_sync(self) -> None:
        # Deferred: during a leave or a scroll the layout has not settled yet,
        # so the cursor test would read stale geometry.
        QTimer.singleShot(0, self._sync_pair_hover)

    def _sync_pair_hover(self) -> None:
        """Light the one card under the pointer, and only that one.

        Each card used to track itself from its own enter and leave events.
        Enter always arrived; leave did not, whenever the pointer crossed
        straight into a neighbour, or the cards moved rather than the pointer.
        Recomputing every card from the real cursor position cannot leave a
        stale highlight behind, whatever route the pointer took.
        """
        # The sync is deferred, so it can land before the UI is built or after
        # the window has been torn down; a scrollbar signal reaches it in both.
        scroll = getattr(self, "_active_page", None)
        if scroll is None:
            return
        try:
            cards = scroll.cards()
        except RuntimeError:
            return  # the C++ side is already gone
        if not cards:
            return
        viewport = scroll.viewport()
        cursor = QCursor.pos()
        # A card scrolled half under the card edge is still geometrically under
        # the cursor, so the viewport has to agree the pointer is on the list.
        on_list = (
            scroll.isVisible()
            and viewport.rect().contains(viewport.mapFromGlobal(cursor))
        )
        for card in cards:
            card.set_hovered(
                on_list and card.rect().contains(card.mapFromGlobal(cursor))
            )

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        if event.type() in (QEvent.Type.Enter, QEvent.Type.Leave):
            self._schedule_pair_hover_sync()
        elif event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._press_origin = event.globalPosition().toPoint()
        elif event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                card = self._card_for(watched)
                origin, self._press_origin = self._press_origin, None
                # Only a click marks. A drag is the user selecting text, and
                # the labels stay selectable, so the two must not collide.
                if card is not None and origin is not None:
                    moved = (event.globalPosition().toPoint() - origin).manhattanLength()
                    if moved <= CLICK_SLOP_PX:
                        card.toggle_marked()
        if (
            self._active_page is not None
            and watched is self._active_page.viewport()
            and event.type() == QEvent.Type.Wheel
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            # angleDelta is in eighths of a degree; one notch is 120.
            notches = event.angleDelta().y() / 120
            if notches:
                step = 1 if notches > 0 else -1
                self.set_pair_font_size(self._pair_font_px + step, announce=True)
            return True
        return super().eventFilter(watched, event)

    def _set_status(self, text: str, state: str) -> None:
        self.status.setText(text)
        self.status_pill.setProperty("state", state)
        for widget in (self.status_pill, self.status_dot, self.status):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def show_welcome(self) -> None:
        """Opened on launch, so double-clicking the exe shows something."""
        self._set_status("Ready", "ready")
        self.section.setText("Ready")
        self.message_output.setPlainText(
            "Select English text anywhere and press Alt+C.\n"
            "Press Alt+S to drag a box over a scanned page or a figure.\n\n"
            "This window steps aside on its own: click any other app and it "
            "drops behind, and the next translation brings it back."
        )
        self.content_stack.setCurrentWidget(self.message_output)
        self._copy_text = ""
        self.copy_button.setEnabled(False)
        self._move_to_screen_center()
        self.show()
        self.raise_()
        self.activateWindow()
        self._raise_above_foreground()

    def _move_to_screen_center(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.center().x() - self.width() // 2,
                  area.center().y() - self.height() // 2)

    def show_loading(self, label: str) -> None:
        self._set_status(label, "loading")
        self.section.setText("Translation")
        self.message_output.setPlainText("Waiting for Codex to return a translation…")
        self.content_stack.setCurrentWidget(self.message_output)
        self._copy_text = ""
        self.copy_button.setEnabled(False)
        self._show_near_cursor()

    def show_result(self, text: str) -> None:
        self._set_status("Complete", "success")
        self.section.setText("Translation")
        self.message_output.setPlainText(text)
        self.content_stack.setCurrentWidget(self.message_output)
        self._copy_text = text
        self.copy_button.setText("Copy text")
        self.copy_button.setEnabled(bool(text.strip()))
        self._show_near_cursor()


    def show_error(self, message: str) -> None:
        self._set_status("Failed", "error")
        self.section.setText("Message")
        self.message_output.setPlainText(message)
        self.content_stack.setCurrentWidget(self.message_output)
        self._copy_text = ""
        self.copy_button.setEnabled(False)
        self._show_near_cursor()

    def copy_output(self) -> None:
        QGuiApplication.clipboard().setText(self._copy_text)
        self._set_status("Copied", "success")


    def _move_near_cursor(self) -> None:
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x = min(QCursor.pos().x() + 18, area.right() - self.width())
        y = min(QCursor.pos().y() + 18, area.bottom() - self.height())
        self.move(max(area.left(), x), max(area.top(), y))

    def _show_near_cursor(self) -> None:
        # Only place the window when it is coming back from hidden. A
        # translation moves through several states, and repositioning on each
        # one would drag the window to wherever the pointer drifted while the
        # user waited, and undo any move or resize they made themselves.
        if not self.isVisible():
            self._move_near_cursor()
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        self._raise_above_foreground()

    def _raise_above_foreground(self) -> None:
        """Put the window in front once, without making it permanently topmost.

        Alt+C fires while another app owns the foreground, and Windows lets a
        background process raise a window far less readily than it lets one set
        topmost. Setting topmost and immediately clearing it wins the race, then
        leaves normal stacking so the next click sends this window behind.
        """
        if sys.platform != "win32":
            return
        handle = self.windowHandle()
        if handle is None:
            return
        user32 = ctypes.windll.user32
        user32.SetWindowPos.argtypes = (
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        )
        user32.SetWindowPos.restype = wintypes.BOOL
        hwnd = wintypes.HWND(int(handle.winId()))
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        user32.SetWindowPos(hwnd, wintypes.HWND(HWND_TOPMOST), 0, 0, 0, 0, flags)
        user32.SetWindowPos(hwnd, wintypes.HWND(HWND_NOTOPMOST), 0, 0, 0, 0, flags)

    def nativeEvent(self, event_type, message):  # noqa: N802, ANN001
        if sys.platform == "win32" and not self.isMaximized():
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_NCHITTEST:
                user32 = ctypes.windll.user32
                user32.ScreenToClient.argtypes = (
                    wintypes.HWND,
                    ctypes.POINTER(wintypes.POINT),
                )
                user32.ScreenToClient.restype = wintypes.BOOL
                user32.GetClientRect.argtypes = (
                    wintypes.HWND,
                    ctypes.POINTER(wintypes.RECT),
                )
                user32.GetClientRect.restype = wintypes.BOOL

                screen_x = ctypes.c_short(msg.lParam & 0xFFFF).value
                screen_y = ctypes.c_short((msg.lParam >> 16) & 0xFFFF).value
                point = wintypes.POINT(screen_x, screen_y)
                client_rect = wintypes.RECT()
                if user32.ScreenToClient(msg.hWnd, ctypes.byref(point)) and user32.GetClientRect(
                    msg.hWnd, ctypes.byref(client_rect)
                ):
                    border = max(
                        RESIZE_BORDER_DIP,
                        round(RESIZE_BORDER_DIP * self.devicePixelRatioF()),
                    )
                    hit = resize_hit_test(
                        point.x,
                        point.y,
                        client_rect.right - client_rect.left,
                        client_rect.bottom - client_rect.top,
                        border,
                    )
                    if hit != HTCLIENT:
                        return True, hit
        return super().nativeEvent(event_type, message)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
