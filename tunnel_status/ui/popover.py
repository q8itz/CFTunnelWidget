"""Floating dark-glass dashboard popover for Cloudflare Tunnel status."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent, QMouseEvent
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..controller import TunnelState
from ..metrics import format_bytes, format_rate, format_uptime
from .icons import build_tray_icon
from .sparkline import TrafficSparkline
from .theme import (
    ACCENT_RX,
    ACCENT_TX,
    POPOVER_QSS,
    STATUS_ACTIVE,
    STATUS_ERROR,
    STATUS_STOPPED,
    STATUS_WARN,
    TEXT_MUTED,
)


def _make_metric_tile(title: str, accent_hex: str | None = None) -> tuple[QFrame, QLabel, QLabel]:
    tile = QFrame()
    tile.setObjectName("MetricTile")
    layout = QVBoxLayout(tile)
    layout.setContentsMargins(12, 10, 12, 10)
    layout.setSpacing(2)

    title_lbl = QLabel(title.upper())
    title_lbl.setObjectName("TileTitle")
    if accent_hex:
        title_lbl.setStyleSheet(f"color: {accent_hex}; font-size: 10px; font-weight: 700;")

    val_lbl = QLabel("0 B")
    val_lbl.setObjectName("TileValue")

    sub_lbl = QLabel("--")
    sub_lbl.setObjectName("TileSub")

    layout.addWidget(title_lbl)
    layout.addWidget(val_lbl)
    layout.addWidget(sub_lbl)
    return tile, val_lbl, sub_lbl


class TunnelPopover(QWidget):
    """Frameless floating card showing tunnel status, traffic, and controls."""

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(420)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._card = QWidget(self)
        self._card.setObjectName("PopoverCard")
        self._card.setStyleSheet(POPOVER_QSS)
        outer.addWidget(self._card)

        root = QVBoxLayout(self._card)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(12)

        # --- Header ---
        header = QHBoxLayout()
        header.setSpacing(8)

        self._icon_lbl = QLabel()
        self._icon_lbl.setFixedSize(28, 28)
        self._icon_lbl.setPixmap(build_tray_icon(False).pixmap(28, 28))
        header.addWidget(self._icon_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title_lbl = QLabel("Cloudflare Tunnel")
        title_lbl.setObjectName("TitleLabel")
        self._backend_lbl = QLabel("systemd")
        self._backend_lbl.setObjectName("SubLabel")
        self._backend_lbl.setMinimumWidth(0)
        title_col.addWidget(title_lbl)
        title_col.addWidget(self._backend_lbl)
        header.addLayout(title_col, 1)

        self._status_pill = QLabel("● Stopped")
        self._status_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._apply_pill_style(STATUS_STOPPED)
        header.addWidget(self._status_pill)

        settings_btn = QPushButton("⚙")
        settings_btn.setObjectName("IconBtn")
        settings_btn.setFixedSize(26, 26)
        settings_btn.setToolTip("Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self.settings_requested.emit)
        header.addWidget(settings_btn)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("IconBtn")
        close_btn.setFixedSize(26, 26)
        close_btn.setToolTip("Hide")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)

        root.addLayout(header)

        # --- Metric Tiles (2x2) ---
        grid = QGridLayout()
        grid.setSpacing(8)

        rx_tile, self._rx_val, self._rx_sub = _make_metric_tile("Ingress (Rx)", ACCENT_RX)
        tx_tile, self._tx_val, self._tx_sub = _make_metric_tile("Egress (Tx)", ACCENT_TX)
        tot_tile, self._tot_val, self._tot_sub = _make_metric_tile("Total Traffic")
        up_tile, self._up_val, self._up_sub = _make_metric_tile("Uptime & Health")

        grid.addWidget(rx_tile, 0, 0)
        grid.addWidget(tx_tile, 0, 1)
        grid.addWidget(tot_tile, 1, 0)
        grid.addWidget(up_tile, 1, 1)
        root.addLayout(grid)

        # --- Live Throughput Sparkline ---
        graph_card = QFrame()
        graph_card.setObjectName("GraphCard")
        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(10, 8, 10, 8)
        graph_layout.setSpacing(4)

        graph_hdr = QHBoxLayout()
        g_title = QLabel("LIVE THROUGHPUT")
        g_title.setObjectName("TileTitle")
        g_legend = QLabel(
            f"<span style='color:{ACCENT_RX};'>●</span> Rx  "
            f"<span style='color:{ACCENT_TX};'>●</span> Tx"
        )
        g_legend.setStyleSheet("font-size: 10px; color: #94A3B8;")
        graph_hdr.addWidget(g_title)
        graph_hdr.addStretch(1)
        graph_hdr.addWidget(g_legend)
        graph_layout.addLayout(graph_hdr)

        self._sparkline = TrafficSparkline()
        graph_layout.addWidget(self._sparkline)
        root.addWidget(graph_card)

        # --- Hint / Error Banner ---
        self._hint_lbl = QLabel("")
        self._hint_lbl.setWordWrap(True)
        self._hint_lbl.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 10px;")
        self._hint_lbl.hide()
        root.addWidget(self._hint_lbl)

        # --- Controls ---
        actions = QHBoxLayout()
        actions.setSpacing(8)

        self._toggle_btn = QPushButton("Start Tunnel")
        self._toggle_btn.setObjectName("PrimaryStartBtn")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        actions.addWidget(self._toggle_btn, 2)

        self._restart_btn = QPushButton("Restart")
        self._restart_btn.setObjectName("SecondaryBtn")
        self._restart_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restart_btn.clicked.connect(self.restart_requested.emit)
        actions.addWidget(self._restart_btn, 1)

        root.addLayout(actions)

        self._is_active = False
        self._busy = False
        self._user_moved = False
        self._drag_offset: QPoint | None = None

    def _apply_pill_style(self, hex_color: str) -> None:
        self._status_pill.setStyleSheet(
            f"background-color: rgba(255, 255, 255, 0.05);"
            f"border: 1px solid {hex_color};"
            f"border-radius: 10px;"
            f"color: {hex_color};"
            f"font-size: 11px;"
            f"font-weight: 600;"
            f"padding: 3px 9px;"
        )

    def _on_toggle_clicked(self) -> None:
        if self._is_active:
            self.stop_requested.emit()
        else:
            self.start_requested.emit()

    def set_busy(self, busy: bool, label: str = "Working...") -> None:
        self._busy = busy
        self._toggle_btn.setEnabled(not busy)
        self._restart_btn.setEnabled(not busy)
        if busy:
            self._toggle_btn.setText(label)

    def update_state(self, state: TunnelState, service_name: str) -> None:
        self._is_active = state.active
        self._icon_lbl.setPixmap(
            build_tray_icon(
                state.active,
                activating=state.activating,
                has_error=bool(state.error),
            ).pixmap(28, 28)
        )
        if state.backend_label == "process":
            self._backend_lbl.setText("cloudflared · process")
        else:
            self._backend_lbl.setText(f"{service_name} · {state.backend_label}")

        if state.error and not state.active:
            self._apply_pill_style(STATUS_ERROR)
            self._status_pill.setText(f"● {state.state_text}")
        elif state.activating:
            self._apply_pill_style(STATUS_WARN)
            self._status_pill.setText(f"◌ {state.state_text}")
        elif state.active:
            self._apply_pill_style(STATUS_ACTIVE)
            self._status_pill.setText(f"● {state.state_text}")
        else:
            self._apply_pill_style(STATUS_STOPPED)
            self._status_pill.setText(f"○ {state.state_text}")

        t = state.traffic
        self._rx_val.setText(format_bytes(t.session_rx))
        self._rx_sub.setText(f"{format_rate(t.rx_rate)} live")

        self._tx_val.setText(format_bytes(t.session_tx))
        self._tx_sub.setText(f"{format_rate(t.tx_rate)} live")

        session_total = t.session_rx + t.session_tx
        all_time_total = t.all_time_rx + t.all_time_tx
        self._tot_val.setText(format_bytes(session_total))
        self._tot_sub.setText(f"All-time: {format_bytes(all_time_total)}")

        self._up_val.setText(format_uptime(state.uptime_seconds))
        health_parts: list[str] = []
        if state.ha_connections is not None:
            health_parts.append(f"{state.ha_connections} HA conn")
        if state.total_requests is not None:
            health_parts.append(f"{state.total_requests:,} req")
        self._up_sub.setText(" · ".join(health_parts) if health_parts else state.substate)

        self._sparkline.set_series(t.history_rx, t.history_tx)

        if state.error:
            self._hint_lbl.setText(f"Note: {state.error}")
            self._hint_lbl.show()
        elif state.active and not state.ip_accounting_available and not state.metrics_available:
            self._hint_lbl.setText(
                "Tip: Enable IPAccounting=yes on the systemd unit or --metrics for traffic stats."
            )
            self._hint_lbl.show()
        else:
            self._hint_lbl.hide()

        if not self._busy:
            self._toggle_btn.setEnabled(True)
            self._restart_btn.setEnabled(state.active)
            if state.active:
                self._toggle_btn.setObjectName("PrimaryStopBtn")
                self._toggle_btn.setText("Stop Tunnel")
            else:
                self._toggle_btn.setObjectName("PrimaryStartBtn")
                self._toggle_btn.setText("Start Tunnel")
            # Re-polish button after objectName swap
            self._toggle_btn.style().unpolish(self._toggle_btn)
            self._toggle_btn.style().polish(self._toggle_btn)

    def show_near_tray(self) -> None:
        self.adjustSize()
        if not self._user_moved:
            screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
            if screen is not None:
                avail = screen.availableGeometry()
                x = avail.right() - self.width() - 12
                y = avail.bottom() - self.height() - 12
                self.move(max(avail.left() + 8, x), max(avail.top() + 8, y))
        self.show()
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                self._user_moved = True
                event.accept()
                return
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is not None and self._drag_offset is not None and (
            event.buttons() & Qt.MouseButton.LeftButton
        ):
            self._user_moved = True
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # noqa: N802
        if event is not None and event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
