import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from tunnel_status.config import AppConfig
from tunnel_status.controller import TunnelState
from tunnel_status.metrics import TrafficStats
from tunnel_status.ui.icons import build_tray_icon
from tunnel_status.ui.popover import TunnelPopover
from tunnel_status.ui.settings_dialog import SettingsDialog


class TestUISmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_icons_and_popover_render(self) -> None:
        for active, activating, err in (
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (False, False, False),
        ):
            icon = build_tray_icon(active, activating=activating, has_error=err)
            self.assertFalse(icon.isNull())

        popover = TunnelPopover()
        state = TunnelState(
            active=True,
            activating=False,
            state_text="Connected",
            substate="running",
            backend_label="systemd (user)",
            uptime_seconds=3661,
            traffic=TrafficStats(
                session_rx=1024 * 1024,
                session_tx=512 * 1024,
                all_time_rx=5 * 1024 * 1024,
                all_time_tx=2 * 1024 * 1024,
                rx_rate=12345.0,
                tx_rate=6789.0,
                history_rx=(100.0, 200.0, 150.0, 400.0),
                history_tx=(50.0, 80.0, 120.0, 200.0),
            ),
            total_requests=4200,
            request_errors=0,
            ha_connections=4,
            metrics_available=True,
            ip_accounting_available=True,
            logs=("INF Starting tunnel", "INF Registered tunnel connection"),
        )
        popover.update_state(state, "cloudflared.service")
        self.assertIn("Registered tunnel connection", popover._log_console.toPlainText())
        popover.repaint()
        popover.close()

    def test_settings_dialog_roundtrip(self) -> None:
        cfg = AppConfig(
            mode="systemd-user",
            service_name="cf.service",
            tunnel_token="cloudflared.exe service install eyJsmoke",
            edge_ip_version="6",
            poll_interval_ms=3000,
        )
        dlg = SettingsDialog(cfg)
        built = dlg.build_config()
        self.assertEqual(built.mode, "systemd-user")
        self.assertEqual(built.service_name, "cf.service")
        self.assertEqual(built.tunnel_token, "eyJsmoke")
        self.assertEqual(built.edge_ip_version, "6")
        self.assertEqual(built.poll_interval_ms, 3000)
        dlg.close()


if __name__ == "__main__":
    unittest.main()
