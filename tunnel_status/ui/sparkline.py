"""Custom-painted dual-line throughput sparkline widget."""

from __future__ import annotations

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QWidget

from ..metrics import format_rate
from .theme import ACCENT_RX, ACCENT_TX, BORDER_SUBTLE, TEXT_MUTED


class TrafficSparkline(QWidget):
    """Anti-aliased dual-series sparkline for Rx (Ingress) and Tx (Egress) rates."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rx: tuple[float, ...] = (0.0,) * 60
        self._tx: tuple[float, ...] = (0.0,) * 60
        self.setMinimumHeight(74)

    def set_series(self, rx: tuple[float, ...], tx: tuple[float, ...]) -> None:
        self._rx = rx if len(rx) >= 2 else (0.0, 0.0)
        self._tx = tx if len(tx) >= 2 else (0.0, 0.0)
        self.update()

    def _build_paths(
        self,
        values: tuple[float, ...],
        left: float,
        top: float,
        width: float,
        height: float,
        max_val: float,
    ) -> tuple[QPainterPath, QPainterPath]:
        n = len(values)
        step = width / max(1, n - 1)
        pts: list[QPointF] = []
        for idx, val in enumerate(values):
            x = left + idx * step
            norm = min(1.0, max(0.0, val / max_val))
            y = top + height - (norm * height)
            pts.append(QPointF(x, y))

        line_path = QPainterPath(pts[0])
        for i in range(1, len(pts)):
            prev_pt = pts[i - 1]
            curr_pt = pts[i]
            mid_x = (prev_pt.x() + curr_pt.x()) / 2.0
            line_path.cubicTo(mid_x, prev_pt.y(), mid_x, curr_pt.y(), curr_pt.x(), curr_pt.y())

        area_path = QPainterPath(line_path)
        area_path.lineTo(pts[-1].x(), top + height)
        area_path.lineTo(pts[0].x(), top + height)
        area_path.closeSubpath()
        return line_path, area_path

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self.rect()
        pad_x = 6.0
        pad_top = 18.0
        pad_bottom = 6.0
        w = max(10.0, rect.width() - pad_x * 2)
        h = max(10.0, rect.height() - pad_top - pad_bottom)

        # Subtle horizontal guide lines
        grid_pen = QPen(QColor(BORDER_SUBTLE))
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        grid_pen.setWidthF(1.0)
        painter.setPen(grid_pen)
        for frac in (0.0, 0.5, 1.0):
            gy = pad_top + h * frac
            painter.drawLine(QPointF(pad_x, gy), QPointF(pad_x + w, gy))

        peak = max(max(self._rx, default=0.0), max(self._tx, default=0.0), 1024.0)

        # Peak rate label in top-right
        painter.setPen(QColor(TEXT_MUTED))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(
            int(pad_x),
            0,
            int(w),
            int(pad_top - 2),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            f"Peak: {format_rate(peak)}",
        )

        # Draw Tx first, then Rx on top
        for values, hex_color, fill_alpha in (
            (self._tx, ACCENT_TX, 45),
            (self._rx, ACCENT_RX, 65),
        ):
            line_path, area_path = self._build_paths(values, pad_x, pad_top, w, h, peak)
            grad = QLinearGradient(0, pad_top, 0, pad_top + h)
            c_top = QColor(hex_color)
            c_top.setAlpha(fill_alpha)
            c_bot = QColor(hex_color)
            c_bot.setAlpha(0)
            grad.setColorAt(0.0, c_top)
            grad.setColorAt(1.0, c_bot)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawPath(area_path)

            pen = QPen(QColor(hex_color), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(line_path)

        painter.end()
