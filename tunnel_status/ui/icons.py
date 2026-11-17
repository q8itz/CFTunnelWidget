"""High-DPI procedural tray and status icons drawn with QPainter."""

from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from .theme import STATUS_ACTIVE, STATUS_ERROR, STATUS_STOPPED, STATUS_WARN


def _draw_tunnel_pixmap(size: int, badge_color: str, active: bool) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    s = float(size)
    # Cloud silhouette
    cloud = QPainterPath()
    cloud.moveTo(s * 0.24, s * 0.70)
    cloud.cubicTo(s * 0.10, s * 0.70, s * 0.08, s * 0.50, s * 0.20, s * 0.45)
    cloud.cubicTo(s * 0.19, s * 0.28, s * 0.36, s * 0.18, s * 0.50, s * 0.24)
    cloud.cubicTo(s * 0.61, s * 0.15, s * 0.80, s * 0.24, s * 0.79, s * 0.41)
    cloud.cubicTo(s * 0.91, s * 0.43, s * 0.92, s * 0.70, s * 0.76, s * 0.70)
    cloud.closeSubpath()

    grad = QLinearGradient(0, s * 0.18, 0, s * 0.72)
    if active:
        grad.setColorAt(0.0, QColor("#F8FAFC"))
        grad.setColorAt(1.0, QColor("#CBD5E1"))
    else:
        grad.setColorAt(0.0, QColor("#94A3B8"))
        grad.setColorAt(1.0, QColor("#64748B"))

    painter.setPen(QPen(QColor(15, 23, 42, 180), max(1.0, s * 0.04)))
    painter.setBrush(grad)
    painter.drawPath(cloud)

    # Inner tunnel arch cut/accent
    arch = QPainterPath()
    arch.moveTo(s * 0.39, s * 0.70)
    arch.lineTo(s * 0.39, s * 0.53)
    arch.cubicTo(s * 0.39, s * 0.41, s * 0.61, s * 0.41, s * 0.61, s * 0.53)
    arch.lineTo(s * 0.61, s * 0.70)
    arch.closeSubpath()

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#0F172A"))
    painter.drawPath(arch)

    # Glowing status dot in bottom-right corner
    dot_r = s * 0.17
    cx = s * 0.78
    cy = s * 0.74
    dot_color = QColor(badge_color)

    # Soft outer glow
    glow = QColor(dot_color)
    glow.setAlpha(95)
    painter.setBrush(glow)
    painter.drawEllipse(QRectF(cx - dot_r * 1.35, cy - dot_r * 1.35, dot_r * 2.7, dot_r * 2.7))

    # Crisp dark ring + status fill
    painter.setPen(QPen(QColor("#0F172A"), max(1.2, s * 0.05)))
    painter.setBrush(dot_color)
    painter.drawEllipse(QRectF(cx - dot_r, cy - dot_r, dot_r * 2, dot_r * 2))

    painter.end()
    return pixmap


def build_tray_icon(active: bool, activating: bool = False, has_error: bool = False) -> QIcon:
    """Create a multi-resolution QIcon reflecting tunnel state."""
    if has_error:
        color = STATUS_ERROR
    elif activating:
        color = STATUS_WARN
    elif active:
        color = STATUS_ACTIVE
    else:
        color = STATUS_STOPPED

    icon = QIcon()
    for sz in (22, 32, 48, 64):
        icon.addPixmap(_draw_tunnel_pixmap(sz, color, active=active))
    return icon
