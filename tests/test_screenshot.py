from PySide6.QtCore import QRect, QSize

from lamarck_translator.screenshot import map_logical_rect_to_pixels


def test_maps_selection_to_125_percent_physical_pixels() -> None:
    rect = QRect(100, 80, 320, 200)

    mapped = map_logical_rect_to_pixels(
        rect,
        logical_size=QSize(1536, 864),
        pixel_size=QSize(1920, 1080),
    )

    assert mapped.x() == 125
    assert mapped.y() == 100
    assert mapped.width() == 400
    assert mapped.height() == 250


def test_maps_selection_without_scaling_at_100_percent() -> None:
    rect = QRect(100, 80, 320, 200)

    mapped = map_logical_rect_to_pixels(
        rect,
        logical_size=QSize(1920, 1080),
        pixel_size=QSize(1920, 1080),
    )

    assert mapped == rect
