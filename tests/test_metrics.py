import tempfile
import unittest
from pathlib import Path

from tunnel_status.metrics import (
    TrafficTracker,
    format_bytes,
    format_uptime,
    parse_prometheus_text,
)


class TestMetrics(unittest.TestCase):
    def test_format_bytes(self) -> None:
        self.assertEqual(format_bytes(0), "0 B")
        self.assertEqual(format_bytes(512), "512 B")
        self.assertEqual(format_bytes(1536), "1.50 KB")
        self.assertEqual(format_bytes(25 * 1024 * 1024), "25.0 MB")

    def test_format_uptime(self) -> None:
        self.assertEqual(format_uptime(None), "--")
        self.assertEqual(format_uptime(45), "45s")
        self.assertEqual(format_uptime(125), "2m 5s")
        self.assertEqual(format_uptime(3661), "1h 1m 1s")
        self.assertEqual(format_uptime(90061), "1d 1h 1m")

    def test_parse_prometheus_text(self) -> None:
        sample = """
# HELP cloudflared_tunnel_total_requests Total requests
# TYPE cloudflared_tunnel_total_requests counter
cloudflared_tunnel_total_requests 120
cloudflared_tunnel_ha_connections{protocol="quic"} 4
quic_client_total_bytes_received{conn="0"} 1000
quic_client_total_bytes_received{conn="1"} 2500
quic_client_total_bytes_sent{conn="0"} 500
"""
        parsed = parse_prometheus_text(sample)
        self.assertEqual(parsed["cloudflared_tunnel_total_requests"], 120.0)
        self.assertEqual(parsed["cloudflared_tunnel_ha_connections"], 4.0)
        self.assertEqual(parsed["quic_client_total_bytes_received"], 3500.0)
        self.assertEqual(parsed["quic_client_total_bytes_sent"], 500.0)

    def test_traffic_tracker_handles_reset_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = Path(tmp) / "stats.json"
            tracker = TrafficTracker(stats_path=stats_path, persist=True, history_len=10)

            s1 = tracker.update(1000, 500, now=10.0)
            self.assertEqual(s1.session_rx, 1000)
            self.assertEqual(s1.session_tx, 500)
            self.assertEqual(s1.rx_rate, 0.0)

            s2 = tracker.update(3000, 1500, now=12.0)
            self.assertEqual(s2.session_rx, 3000)
            self.assertEqual(s2.session_tx, 1500)
            self.assertAlmostEqual(s2.rx_rate, 1000.0)
            self.assertAlmostEqual(s2.tx_rate, 500.0)

            # Simulate service restart (counter resets to 200 / 100)
            s3 = tracker.update(200, 100, now=14.0)
            self.assertEqual(s3.session_rx, 3200)
            self.assertEqual(s3.all_time_rx, 3200)
            self.assertEqual(s3.all_time_tx, 1600)

            tracker.save()
            reloaded = TrafficTracker(stats_path=stats_path, persist=True, history_len=10)
            s4 = reloaded.update(None, None, now=15.0)
            self.assertEqual(s4.all_time_rx, 3200)
            self.assertEqual(s4.all_time_tx, 1600)


if __name__ == "__main__":
    unittest.main()
