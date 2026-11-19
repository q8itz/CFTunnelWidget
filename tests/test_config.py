import tempfile
import unittest
from pathlib import Path

from tunnel_status.config import AppConfig, normalize_tunnel_token


class TestAppConfig(unittest.TestCase):
    def test_defaults_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig.load(Path(tmp) / "missing.json")
            self.assertEqual(cfg.mode, "auto")
            self.assertEqual(cfg.service_name, "cloudflared.service")
            self.assertEqual(cfg.poll_interval_ms, 2000)

    def test_save_and_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            orig = AppConfig(
                mode="systemd-user",
                service_name="cloudflared-home.service",
                tunnel_token="eyJtesttoken123",
                edge_ip_version="6",
                metrics_url="http://127.0.0.1:9999/metrics",
                poll_interval_ms=1500,
                persist_stats=False,
                process_command="cloudflared tunnel run my-tunnel",
            )
            orig.save(path)
            loaded = AppConfig.load(path)
            self.assertEqual(loaded, orig)

    def test_normalize_tunnel_token(self) -> None:
        self.assertEqual(normalize_tunnel_token("  eyJabc123  "), "eyJabc123")
        self.assertEqual(
            normalize_tunnel_token("cloudflared.exe service install eyJabc123"),
            "eyJabc123",
        )
        self.assertEqual(
            normalize_tunnel_token("cloudflared tunnel run --token eyJabc123"),
            "eyJabc123",
        )

    def test_invalid_values_fall_back_safely(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text('{"mode": "bogus", "poll_interval_ms": 50}', encoding="utf-8")
            cfg = AppConfig.load(path)
            self.assertEqual(cfg.mode, "auto")
            self.assertEqual(cfg.poll_interval_ms, 2000)


if __name__ == "__main__":
    unittest.main()
