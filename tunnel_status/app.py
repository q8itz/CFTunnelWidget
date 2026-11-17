"""Main Qt application wiring QSystemTrayIcon, popover, context menu, and worker pool."""

from __future__ import annotations

import sys
from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .config import AppConfig
from .controller import ActionResult, TunnelController, TunnelState
from .metrics import format_bytes, format_rate
from .ui.icons import build_tray_icon
from .ui.popover import TunnelPopover
from .ui.settings_dialog import SettingsDialog
from .ui.theme import MENU_QSS


class _WorkerSignals(QObject):
    status_ready = pyqtSignal(object)
    action_done = pyqtSignal(object)


class _TaskRunnable(QRunnable):
    def __init__(self, fn: Callable[[], object], signal: pyqtSignal) -> None:
        super().__init__()
        self._fn = fn
        self._signal = signal

    def run(self) -> None:
        result = self._fn()
        self._signal.emit(result)


class TunnelTrayApp(QObject):
    """Coordinates the tray icon, popover dashboard, and background controller."""

    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self._app = app
        self._config = AppConfig.load()
        self._controller = TunnelController(self._config)
        self._pool = QThreadPool.globalInstance()
        self._signals = _WorkerSignals()
        self._signals.status_ready.connect(self._on_status_ready)
        self._signals.action_done.connect(self._on_action_done)

        self._poll_in_flight = False
        self._last_state: TunnelState | None = None

        # Popover dashboard
        self._popover = TunnelPopover()
        self._popover.start_requested.connect(lambda: self._run_action("start"))
        self._popover.stop_requested.connect(lambda: self._run_action("stop"))
        self._popover.restart_requested.connect(lambda: self._run_action("restart"))
        self._popover.settings_requested.connect(self._open_settings)

        # Tray icon & right-click context menu
        self._tray = QSystemTrayIcon(build_tray_icon(False), self)
        self._tray.setToolTip("Cloudflare Tunnel: Checking...")
        self._tray.activated.connect(self._on_tray_activated)

        self._menu = QMenu()
        self._menu.setStyleSheet(MENU_QSS)

        self._status_action = self._menu.addAction("Status: Checking...")
        self._status_action.setEnabled(False)
        self._traffic_action = self._menu.addAction("Traffic: --")
        self._traffic_action.setEnabled(False)
        self._menu.addSeparator()

        self._start_action = self._menu.addAction("Start Tunnel")
        self._start_action.triggered.connect(lambda: self._run_action("start"))

        self._stop_action = self._menu.addAction("Stop Tunnel")
        self._stop_action.triggered.connect(lambda: self._run_action("stop"))

        self._restart_action = self._menu.addAction("Restart Tunnel")
        self._restart_action.triggered.connect(lambda: self._run_action("restart"))

        self._menu.addSeparator()
        self._dashboard_action = self._menu.addAction("Open Dashboard")
        self._dashboard_action.triggered.connect(self._toggle_popover)

        self._settings_action = self._menu.addAction("Settings...")
        self._settings_action.triggered.connect(self._open_settings)

        self._menu.addSeparator()
        self._quit_action = self._menu.addAction("Quit")
        self._quit_action.triggered.connect(self._quit)

        self._tray.setContextMenu(self._menu)
        self._tray.show()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll_status)
        self._timer.start(self._config.poll_interval_ms)
        self._poll_status()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.MiddleClick,
        ):
            self._toggle_popover()

    def _toggle_popover(self) -> None:
        if self._popover.isVisible():
            self._popover.hide()
        else:
            self._popover.show_near_tray()

    def _poll_status(self) -> None:
        if self._poll_in_flight:
            return
        self._poll_in_flight = True
        task = _TaskRunnable(self._controller.get_status, self._signals.status_ready)
        self._pool.start(task)

    def _on_status_ready(self, state: TunnelState) -> None:
        self._poll_in_flight = False
        self._last_state = state

        self._tray.setIcon(
            build_tray_icon(
                state.active,
                activating=state.activating,
                has_error=bool(state.error),
            )
        )

        t = state.traffic
        total_session = t.session_rx + t.session_tx
        self._tray.setToolTip(
            f"Cloudflare Tunnel: {state.state_text}\n"
            f"Rx: {format_bytes(t.session_rx)} ({format_rate(t.rx_rate)})\n"
            f"Tx: {format_bytes(t.session_tx)} ({format_rate(t.tx_rate)})\n"
            f"Total: {format_bytes(total_session)}"
        )

        dot = "●" if state.active else "○"
        self._status_action.setText(f"{dot} {state.state_text} ({self._config.service_name})")
        self._traffic_action.setText(
            f"Traffic: ↓ {format_bytes(t.session_rx)}  ↑ {format_bytes(t.session_tx)}"
        )
        self._start_action.setEnabled(not state.active)
        self._stop_action.setEnabled(state.active)
        self._restart_action.setEnabled(state.active)

        self._popover.update_state(state, self._config.service_name)

    def _run_action(self, action: str) -> None:
        busy_label = {
            "start": "Starting...",
            "stop": "Stopping...",
            "restart": "Restarting...",
        }.get(action, "Working...")
        self._popover.set_busy(True, busy_label)

        fn = getattr(self._controller, action)
        task = _TaskRunnable(fn, self._signals.action_done)
        self._pool.start(task)

    def _on_action_done(self, result: ActionResult) -> None:
        self._popover.set_busy(False)
        if not result.ok:
            self._tray.showMessage(
                "Cloudflare Tunnel",
                result.message,
                QSystemTrayIcon.MessageIcon.Warning,
                4000,
            )
        self._poll_status()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._config)
        dlg.reset_stats_requested.connect(self._controller.tracker.reset_all_time)
        if dlg.exec():
            new_cfg = dlg.build_config()
            new_cfg.save()
            self._config = new_cfg
            self._controller.update_config(new_cfg)
            self._timer.setInterval(new_cfg.poll_interval_ms)
            self._poll_status()

    def _quit(self) -> None:
        self._timer.stop()
        self._controller.tracker.save()
        self._tray.hide()
        self._app.quit()


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Tunnel Status")
    app.setDesktopFileName("tunnel-status")
    app.setQuitOnLastWindowClosed(False)

    _tray_app = TunnelTrayApp(app)  # keep reference alive
    return app.exec()
