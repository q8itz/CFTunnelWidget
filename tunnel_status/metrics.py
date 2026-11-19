"""Traffic accounting, Prometheus metrics parsing, and formatting helpers."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path

_METRIC_LINE_RE = re.compile(
    r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{[^}]*\})?\s+([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|NaN|[+-]?Inf)(?:\s+\d+)?$"
)


def format_bytes(num_bytes: int | float) -> str:
    """Format byte count into human-readable IEC/SI-style units."""
    value = max(0.0, float(num_bytes))
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.2f} {unit}" if value < 10 else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{int(num_bytes)} B"


def format_rate(bytes_per_sec: float) -> str:
    """Format throughput in bytes/sec."""
    return f"{format_bytes(bytes_per_sec)}/s"


def format_uptime(seconds: int | None) -> str:
    """Format duration in seconds into a compact string."""
    if seconds is None or seconds < 0:
        return "--"
    secs = int(seconds)
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


@dataclass(frozen=True)
class PrometheusSnapshot:
    """Relevant metrics scraped from cloudflared's /metrics endpoint."""

    total_requests: int | None = None
    request_errors: int | None = None
    ha_connections: int | None = None
    rx_bytes: int | None = None
    tx_bytes: int | None = None
    net_rx_bytes: int | None = None
    net_tx_bytes: int | None = None


def read_proc_io_bytes(pid: int | None) -> tuple[int, int] | None:
    """Read per-process (rchar, wchar) from /proc/<pid>/io on Linux."""
    if pid is None or pid <= 0:
        return None
    io_path = Path(f"/proc/{pid}/io")
    try:
        content = io_path.read_text(encoding="utf-8")
    except OSError:
        return None
    rchar: int | None = None
    wchar: int | None = None
    for line in content.splitlines():
        if line.startswith("rchar:"):
            try:
                rchar = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
        elif line.startswith("wchar:"):
            try:
                wchar = int(line.split(":", 1)[1].strip())
            except ValueError:
                pass
    if rchar is not None and wchar is not None:
        return rchar, wchar
    return None


def parse_prometheus_text(text: str) -> dict[str, float]:
    """Sum Prometheus metric values by metric name across all label sets."""
    totals: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _METRIC_LINE_RE.match(line)
        if not match:
            continue
        name, val_str = match.group(1), match.group(2)
        try:
            val = float(val_str)
        except ValueError:
            continue
        if val != val:  # NaN check
            continue
        totals[name] = totals.get(name, 0.0) + val
    return totals


def fetch_prometheus_metrics(url: str, timeout: float = 1.2) -> PrometheusSnapshot | None:
    """Fetch and parse cloudflared Prometheus metrics, returning None if unreachable."""
    if not url:
        return None
    req = urllib.request.Request(url, headers={"Accept": "text/plain"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None

    parsed = parse_prometheus_text(body)
    if not parsed:
        return None

    def _first_int(*keys: str) -> int | None:
        for key in keys:
            if key in parsed:
                return int(parsed[key])
        return None

    return PrometheusSnapshot(
        total_requests=_first_int("cloudflared_tunnel_total_requests"),
        request_errors=_first_int("cloudflared_tunnel_request_errors"),
        ha_connections=_first_int("cloudflared_tunnel_ha_connections"),
        rx_bytes=_first_int("quic_client_total_bytes_received", "quic_client_receive_bytes"),
        tx_bytes=_first_int("quic_client_total_bytes_sent", "quic_client_sent_bytes"),
        net_rx_bytes=_first_int("process_network_receive_bytes_total"),
        net_tx_bytes=_first_int("process_network_transmit_bytes_total"),
    )


@dataclass(frozen=True)
class TrafficStats:
    """Computed traffic statistics for UI display."""

    session_rx: int
    session_tx: int
    all_time_rx: int
    all_time_tx: int
    rx_rate: float
    tx_rate: float
    history_rx: tuple[float, ...]
    history_tx: tuple[float, ...]


class TrafficTracker:
    """Tracks live throughput, session totals, and persisted all-time totals."""

    def __init__(
        self,
        stats_path: Path | None = None,
        persist: bool = True,
        history_len: int = 60,
    ) -> None:
        self._stats_path = stats_path
        self._persist = persist
        self._history_rx: deque[float] = deque([0.0] * history_len, maxlen=history_len)
        self._history_tx: deque[float] = deque([0.0] * history_len, maxlen=history_len)

        self._last_raw_rx: int | None = None
        self._last_raw_tx: int | None = None
        self._last_time: float | None = None

        self._session_rx: int = 0
        self._session_tx: int = 0
        self._all_time_rx: int = 0
        self._all_time_tx: int = 0
        self._last_save_time: float = 0.0

        if self._persist and self._stats_path is not None:
            self._load()

    def _load(self) -> None:
        if self._stats_path is None or not self._stats_path.exists():
            return
        try:
            data = json.loads(self._stats_path.read_text(encoding="utf-8"))
            self._all_time_rx = max(0, int(data.get("all_time_rx", 0)))
            self._all_time_tx = max(0, int(data.get("all_time_tx", 0)))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        if not self._persist or self._stats_path is None:
            return
        try:
            self._stats_path.parent.mkdir(parents=True, exist_ok=True)
            self._stats_path.write_text(
                json.dumps(
                    {
                        "all_time_rx": self._all_time_rx,
                        "all_time_tx": self._all_time_tx,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            self._last_save_time = time.monotonic()
        except OSError:
            pass

    def reset_all_time(self) -> None:
        self._all_time_rx = 0
        self._all_time_tx = 0
        self._session_rx = 0
        self._session_tx = 0
        self.save()

    def update(
        self,
        raw_rx: int | None,
        raw_tx: int | None,
        now: float | None = None,
    ) -> TrafficStats:
        """Update counters with the latest raw byte readings."""
        ts = time.monotonic() if now is None else now
        rx_rate = 0.0
        tx_rate = 0.0

        if raw_rx is not None and raw_tx is not None:
            raw_rx = max(0, raw_rx)
            raw_tx = max(0, raw_tx)

            if self._last_raw_rx is None or self._last_raw_tx is None:
                # First observation: initialize baseline without spiking rate,
                # but reflect current active session bytes if service was already running.
                self._session_rx = raw_rx
                self._session_tx = raw_tx
                if self._all_time_rx == 0 and self._all_time_tx == 0:
                    self._all_time_rx = raw_rx
                    self._all_time_tx = raw_tx
            else:
                delta_rx = raw_rx - self._last_raw_rx if raw_rx >= self._last_raw_rx else raw_rx
                delta_tx = raw_tx - self._last_raw_tx if raw_tx >= self._last_raw_tx else raw_tx
                self._session_rx += delta_rx
                self._session_tx += delta_tx
                self._all_time_rx += delta_rx
                self._all_time_tx += delta_tx

                dt = ts - (self._last_time or ts)
                if dt > 0.05:
                    rx_rate = delta_rx / dt
                    tx_rate = delta_tx / dt

            self._last_raw_rx = raw_rx
            self._last_raw_tx = raw_tx
            self._last_time = ts
        else:
            self._last_raw_rx = None
            self._last_raw_tx = None
            self._last_time = ts

        self._history_rx.append(rx_rate)
        self._history_tx.append(tx_rate)

        if self._persist and (ts - self._last_save_time) >= 10.0:
            self.save()

        return TrafficStats(
            session_rx=self._session_rx,
            session_tx=self._session_tx,
            all_time_rx=self._all_time_rx,
            all_time_tx=self._all_time_tx,
            rx_rate=rx_rate,
            tx_rate=tx_rate,
            history_rx=tuple(self._history_rx),
            history_tx=tuple(self._history_tx),
        )
