from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


def map_logical_rect_to_pixels(
    rect: QRect, logical_size: QSize, pixel_size: QSize
) -> QRectF:
    """Map a widget-space selection to the captured pixmap's physical pixels."""
    if logical_size.width() <= 0 or logical_size.height() <= 0:
        return QRectF()
    scale_x = pixel_size.width() / logical_size.width()
    scale_y = pixel_size.height() / logical_size.height()
    return QRectF(
        rect.x() * scale_x,
        rect.y() * scale_y,
        rect.width() * scale_x,
        rect.height() * scale_y,
    )


class ScreenshotOverlay(QWidget):
    captured = Signal(object)
    cancelled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._background = QPixmap()
        self._start: QPoint | None = None
        self._end: QPoint | None = None

    def begin(self) -> None:
        screen = QGuiApplication.screenAt(self._cursor_position())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.cancelled.emit()
            return
        self._background = screen.grabWindow(0)
        self.setGeometry(screen.geometry())
        self._start = None
        self._end = None
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    @staticmethod
    def _cursor_position() -> QPoint:
        from PySide6.QtGui import QCursor

        return QCursor.pos()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.position().toPoint()
            self._end = self._start
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._start is not None:
            self._end = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        self._end = event.position().toPoint()
        rect = QRect(self._start, self._end).normalized().intersected(self.rect())
        if rect.width() < 8 or rect.height() < 8:
            self.close()
            self.cancelled.emit()
            return

        pixel_rect = map_logical_rect_to_pixels(
            rect, self.size(), self._background.size()
        ).toAlignedRect()
        pixel_rect = pixel_rect.intersected(self._background.rect())
        cropped = self._background.copy(pixel_rect)
        cropped.setDevicePixelRatio(1.0)
        handle = tempfile.NamedTemporaryFile(
            prefix="lamarck-translator-", suffix=".png", delete=False
        )
        handle.close()
        path = Path(handle.name)
        if not cropped.save(str(path), "PNG"):
            path.unlink(missing_ok=True)
            self.close()
            self.cancelled.emit()
            return
        self.close()
        self.captured.emit(path)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(self.rect(), self._background)
        painter.fillRect(self.rect(), QColor(10, 18, 35, 125))

        message = "Drag to select an area to translate  ·  Esc to cancel"
        if self._start is not None and self._end is not None:
            rect = QRect(self._start, self._end).normalized()
            source_rect = map_logical_rect_to_pixels(
                rect, self.size(), self._background.size()
            )
            painter.drawPixmap(QRectF(rect), self._background, source_rect)
            painter.setPen(QPen(QColor("#4E7BFF"), 3))
            painter.drawRect(rect)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#FFFFFF"))
            for point in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()):
                painter.drawEllipse(point, 4, 4)
            pixel_rect = source_rect.toAlignedRect()
            message = (
                f"{pixel_rect.width()} × {pixel_rect.height()} px"
                "  ·  Release to translate"
            )

        painter.setFont(QFont("Microsoft YaHei UI", 11, QFont.Weight.Medium))
        metrics = painter.fontMetrics()
        panel_width = metrics.horizontalAdvance(message) + 44
        panel = QRectF((self.width() - panel_width) / 2, 26, panel_width, 44)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(20, 29, 48, 225))
        painter.drawRoundedRect(panel, 12, 12)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(panel, Qt.AlignmentFlag.AlignCenter, message)
