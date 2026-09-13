from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QIcon,
    QKeyEvent,
    QMouseEvent,
    QPainter,
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


WINDOW_STYLE = """
QWidget#resultWindow {
    background: #F4F7FB;
    color: #172033;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    border: 1px solid #DDE4EF;
}
QFrame#titleBar {
    background: #FBFCFE;
    border: none;
    border-bottom: 1px solid #E4E9F1;
}
QLabel#titleBarIcon {
    background: transparent;
    border: none;
}
QLabel#windowTitleLabel {
    color: #5D687C;
    background: transparent;
    font-size: 11px;
    font-weight: 600;
}
QPushButton#windowCloseButton,
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
    color: #6C7689;
    font-family: "Segoe UI Symbol", "Segoe UI";
    font-size: 17px;
    font-weight: 400;
}
QPushButton#windowMinimizeButton:hover, QPushButton#windowMaximizeButton:hover {
    background: #E9EEF6;
    color: #25304A;
}
QPushButton#windowMinimizeButton:pressed, QPushButton#windowMaximizeButton:pressed {
    background: #DDE4EF;
    color: #172033;
}
QPushButton#windowCloseButton:hover {
    background: #FCE8EA;
    color: #C43242;
}
QPushButton#windowCloseButton:pressed {
    background: #F7D5D9;
    color: #A92332;
}
QWidget#windowBody {
    background: #F4F7FB;
    border: none;
}
QFrame#headerCard, QFrame#contentCard {
    background: #FFFFFF;
    border: 1px solid #E3E9F2;
    border-radius: 14px;
}
QLabel#brandMark {
    background: transparent;
    border: none;
}
QLabel#titleLabel {
    color: #16213A;
    font-size: 20px;
    font-weight: 700;
}
QLabel#subtitleLabel {
    color: #78849A;
    font-size: 11px;
}
QLabel#accountLabel {
    color: #5B47A8;
    font-size: 11px;
    font-weight: 600;
}
QFrame#statusPill {
    border-radius: 12px;
    padding: 0 10px;
}
QFrame#statusPill[state="ready"], QFrame#statusPill[state="loading"] {
    background: #EEF3FF;
    border: 1px solid #DCE6FF;
}
QFrame#statusPill[state="success"] {
    background: #EAF8F1;
    border: 1px solid #CDEDDD;
}
QFrame#statusPill[state="error"] {
    background: #FFF0F0;
    border: 1px solid #FFD7D7;
}
QLabel#statusDot, QLabel#statusText {
    color: #315EFB;
    font-size: 12px;
    font-weight: 600;
}
QFrame#statusPill[state="success"] QLabel {
    color: #17855B;
}
QFrame#statusPill[state="error"] QLabel {
    color: #C83C4A;
}
QLabel#sectionLabel {
    color: #4B5870;
    font-size: 12px;
    font-weight: 600;
}
QTextBrowser#messageOutput {
    background: transparent;
    border: none;
    color: #202A3D;
    selection-background-color: #C9D7FF;
    selection-color: #172033;
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
    background: #CAD2E0;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #9D8FE0;
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
    background: #FBFCFE;
    border: 1px solid #E5EAF2;
    border-radius: 11px;
}
QFrame#translationPairCard[hovered="true"] {
    background: #F2EEFF;
    border-color: #AF9BFA;
}
QLabel#sourceText {
    color: #25304A;
    font-family: "Segoe UI", "Arial";
    font-size: 15px;
    font-weight: 600;
    background: transparent;
}
QLabel#translationText {
    color: #536078;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 15px;
    background: transparent;
}
QFrame#translationPairCard[hovered="true"] QLabel#sourceText {
    color: #40269A;
}
QFrame#translationPairCard[hovered="true"] QLabel#translationText {
    color: #5A3FB0;
}
QPushButton {
    min-height: 36px;
    padding: 0 17px;
    border-radius: 8px;
    border: 1px solid #D7DFEB;
    background: #FFFFFF;
    color: #354159;
    font-size: 13px;
    font-weight: 600;
}
QPushButton:hover {
    background: #F3F6FB;
    border-color: #B9C5D7;
}
QPushButton:pressed {
    background: #E9EEF6;
}
QPushButton[variant="primary"] {
    color: #FFFFFF;
    background: #315EFB;
    border-color: #315EFB;
}
QPushButton[variant="primary"]:hover {
    background: #274FD8;
    border-color: #274FD8;
}
QPushButton[variant="primary"]:pressed {
    background: #1F43BE;
    border-color: #1F43BE;
}
QPushButton[variant="ghost"] {
    background: transparent;
    border-color: transparent;
    color: #6A768C;
}
QPushButton[variant="ghost"]:hover {
    background: #E9EEF6;
    color: #29364F;
}
QPushButton:disabled {
    background: #E9EDF4;
    border-color: #E9EDF4;
    color: #A2ABBA;
}
QLabel#shortcutHint {
    color: #929CAF;
    font-size: 11px;
}
"""


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

        self.minimize_button = MinimizeButton()
        self.minimize_button.clicked.connect(window.showMinimized)
        self.maximize_button = MaximizeRestoreButton(window)
        self.close_button = CloseButton()
        self.close_button.clicked.connect(window.hide)
        window.installEventFilter(self)

        layout.addWidget(self.icon_label)
        layout.addWidget(title)
        layout.addStretch(1)
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
    def __init__(self, pair: TranslationPair, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("translationPairCard")
        self.setProperty("hovered", False)

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

        for widget in (self, self.source_label, self.translation_label):
            widget.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
            widget.installEventFilter(self)

    def eventFilter(self, watched: object, event: QEvent) -> bool:  # noqa: N802
        if event.type() == QEvent.Type.Enter:
            self._set_hovered(True)
        elif event.type() == QEvent.Type.Leave:
            QTimer.singleShot(0, self._sync_hover_state)
        return super().eventFilter(watched, event)

    def _sync_hover_state(self) -> None:
        local_position = self.mapFromGlobal(QCursor.pos())
        self._set_hovered(self.rect().contains(local_position))

    def _set_hovered(self, hovered: bool) -> None:
        if self.property("hovered") == hovered:
            return
        self.setProperty("hovered", hovered)
        for widget in (self, self.source_label, self.translation_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()


class ResultWindow(QWidget):
    retry_requested = Signal()

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
        self.setStyleSheet(WINDOW_STYLE)
        self._copy_text = ""
        self._build_ui()
        self._set_status("Ready", "ready")

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

        self.pairs_scroll = QScrollArea()
        self.pairs_scroll.setObjectName("pairsScroll")
        self.pairs_scroll.setWidgetResizable(True)
        self.pairs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.pairs_container = QWidget()
        self.pairs_container.setObjectName("pairsContainer")
        self.pairs_layout = QVBoxLayout(self.pairs_container)
        self.pairs_layout.setContentsMargins(2, 2, 6, 2)
        self.pairs_layout.setSpacing(9)
        self.pairs_scroll.setWidget(self.pairs_container)

        self.content_stack.addWidget(self.message_output)
        self.content_stack.addWidget(self.pairs_scroll)
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

        footer.addWidget(hint)
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

    def set_backend_info(self, model: str, effort: str) -> None:
        self.subtitle_label.setText(format_backend_info(model, effort))

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

    def show_bilingual_result(
        self,
        source_text: str | None,
        response_text: str,
    ) -> None:
        pairs = parse_translation_pairs(response_text, source_text)
        if not pairs:
            self.show_error(
                "No recognizable English–Chinese sentence pairs were returned. "
                "Please capture the screenshot again."
            )
            return
        self._clear_pairs()
        for pair in pairs:
            self.pairs_layout.addWidget(TranslationPairCard(pair))
        self.pairs_layout.addStretch(1)

        self._copy_text = format_translation_pairs(pairs)
        self.section.setText("Bilingual translation")
        self.copy_button.setText("Copy bilingual text")
        self.copy_button.setEnabled(bool(self._copy_text))
        self.content_stack.setCurrentWidget(self.pairs_scroll)
        self.pairs_scroll.verticalScrollBar().setValue(0)
        self._set_status("Complete", "success")
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

    def _clear_pairs(self) -> None:
        while self.pairs_layout.count():
            item = self.pairs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
