import unittest
from unittest.mock import patch

from tunnel_status.config import AppConfig
from tunnel_status.controller import TunnelController, _parse_systemd_show, _parse_uint
from tunnel_status.metrics import TrafficTracker


class TestController(unittest.TestCase):
    def test_parse_systemd_show_and_uint(self) -> None:
        raw = (
            "LoadState=loaded\n"
            "ActiveState=active\n"
            "SubState=running\n"
            "IPIngressBytes=123456\n"
            "IPEgressBytes=[not set]\n"
        )
        props = _parse_systemd_show(raw)
        self.assertEqual(props["ActiveState"], "active")
        self.assertEqual(_parse_uint(props["IPIngressBytes"]), 123456)
        self.assertIsNone(_parse_uint(props["IPEgressBytes"]))
        self.assertIsNone(_parse_uint("18446744073709551615"))

    def test_systemd_user_status_parsing(self) -> None:
        cfg = AppConfig(mode="systemd-user", metrics_url="")
        ctrl = TunnelController(cfg, tracker=TrafficTracker(persist=False))

        fake_props = {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "ActiveEnterTimestampMonotonic": "0",
            "IPIngressBytes": "2048",
            "IPEgressBytes": "1024",
            "MainPID": "4242",
        }
        with (
            patch.object(ctrl, "_query_systemd", return_value=fake_props),
            patch("tunnel_status.controller.fetch_prometheus_metrics", return_value=None),
        ):
            state = ctrl.get_status()
            self.assertTrue(state.active)
            self.assertEqual(state.state_text, "Connected")
            self.assertTrue(state.ip_accounting_available)
            self.assertEqual(state.traffic.session_rx, 2048)
            self.assertEqual(state.traffic.session_tx, 1024)

    def test_process_command_injects_metrics_and_token_env(self) -> None:
        cfg = AppConfig(
            mode="process",
            tunnel_token="cloudflared.exe service install eyJmysecret",
            edge_ip_version="6",
            metrics_url="http://127.0.0.1:20241/metrics",
            process_command="cloudflared tunnel run",
        )
        ctrl = TunnelController(cfg, tracker=TrafficTracker(persist=False))
        args, env = ctrl._build_process_command_and_env()
        self.assertEqual(
            args,
            [
                "cloudflared",
                "tunnel",
                "--edge-ip-version",
                "6",
                "--metrics",
                "127.0.0.1:20241",
                "run",
            ],
        )
        self.assertEqual(env["TUNNEL_TOKEN"], "eyJmysecret")

    def test_log_buffer_append_and_clear(self) -> None:
        cfg = AppConfig(mode="process", metrics_url="")
        ctrl = TunnelController(cfg, tracker=TrafficTracker(persist=False))
        ctrl._append_log("INF Starting tunnel")
        ctrl._append_log("INF Registered tunnel connection")
        self.assertEqual(
            ctrl.get_logs(),
            ("INF Starting tunnel", "INF Registered tunnel connection"),
        )
        ctrl.clear_logs()
        self.assertEqual(ctrl.get_logs(), ())


if __name__ == "__main__":
    unittest.main()
