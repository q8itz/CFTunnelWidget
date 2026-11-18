"""Systemd and process controller for cloudflared."""

from __future__ import annotations

import os
import shlex
import subprocess
import threading
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urlparse

from .config import AppConfig, normalize_tunnel_token
from .metrics import (
    PrometheusSnapshot,
    TrafficStats,
    TrafficTracker,
    fetch_prometheus_metrics,
)

_UINT64_MAX_STR = "18446744073709551615"


@dataclass(frozen=True)
class TunnelState:
    """Complete snapshot of cloudflared status and traffic."""

    active: bool
    activating: bool
    state_text: str
    substate: str
    backend_label: str
    uptime_seconds: int | None
    traffic: TrafficStats
    total_requests: int | None
    request_errors: int | None
    ha_connections: int | None
    metrics_available: bool
    ip_accounting_available: bool
    error: str | None = None
    logs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    message: str


def _parse_systemd_show(output: str) -> dict[str, str]:
    props: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            props[key.strip()] = val.strip()
    return props


def _parse_uint(val: str | None) -> int | None:
    if not val or val in ("[not set]", _UINT64_MAX_STR):
        return None
    try:
        parsed = int(val)
        return parsed if parsed >= 0 else None
    except ValueError:
        return None


def _monotonic_usec_now() -> int:
    return int(time.monotonic() * 1_000_000)


class TunnelController:
    """Queries and controls cloudflared via systemd or direct process."""

    def __init__(self, config: AppConfig, tracker: TrafficTracker | None = None) -> None:
        self.config = config
        self.tracker = tracker or TrafficTracker(
            stats_path=AppConfig.stats_path(),
            persist=config.persist_stats,
        )
        self._managed_proc: subprocess.Popen[str] | None = None
        self._proc_start_monotonic: float | None = None
        self._resolved_mode: str | None = None
        self._log_lock = threading.Lock()
        self._log_lines: deque[str] = deque(maxlen=400)

    def _append_log(self, line: str) -> None:
        cleaned = line.rstrip("\r\n")
        if not cleaned:
            return
        with self._log_lock:
            self._log_lines.append(cleaned)

    def clear_logs(self) -> None:
        with self._log_lock:
            self._log_lines.clear()

    def get_logs(self) -> tuple[str, ...]:
        with self._log_lock:
            return tuple(self._log_lines)

    def _drain_process_output(self, proc: subprocess.Popen[str]) -> None:
        if proc.stdout is not None:
            try:
                for line in proc.stdout:
                    self._append_log(line)
            except (OSError, ValueError):
                pass
            finally:
                try:
                    proc.stdout.close()
                except OSError:
                    pass
        rc = proc.poll()
        if rc is not None:
            self._append_log(f"[tunnel-status] cloudflared exited with code {rc}")

    def _query_journalctl(self, user_scope: bool, lines: int = 80) -> tuple[str, ...]:
        cmd = ["journalctl"]
        if user_scope:
            cmd.append("--user")
        cmd.extend(["-u", self.config.service_name, "-n", str(lines), "--no-pager", "-o", "short"])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0 and res.stdout:
                return tuple(res.stdout.splitlines())
        except (OSError, subprocess.SubprocessError):
            pass
        return ()

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        self._resolved_mode = None

    def _unit_exists(self, user_scope: bool, unit: str) -> bool:
        cmd = ["systemctl"]
        if user_scope:
            cmd.append("--user")
        cmd.extend(["show", unit, "--property=LoadState", "--value"])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            return res.returncode == 0 and res.stdout.strip() not in ("", "not-found")
        except (OSError, subprocess.SubprocessError):
            return False

    def resolve_mode(self) -> str:
        if self.config.mode != "auto":
            return self.config.mode
        if self._resolved_mode is not None:
            return self._resolved_mode

        unit = self.config.service_name
        if self._unit_exists(user_scope=True, unit=unit):
            self._resolved_mode = "systemd-user"
        elif self._unit_exists(user_scope=False, unit=unit):
            self._resolved_mode = "systemd-system"
        else:
            self._resolved_mode = "process"
        return self._resolved_mode

    def _query_systemd(self, user_scope: bool) -> dict[str, str] | None:
        cmd = ["systemctl"]
        if user_scope:
            cmd.append("--user")
        cmd.extend(
            [
                "show",
                self.config.service_name,
                "--property=LoadState,ActiveState,SubState,ActiveEnterTimestampMonotonic,IPIngressBytes,IPEgressBytes,MainPID",
            ]
        )
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.5)
            if res.returncode != 0:
                return None
            return _parse_systemd_show(res.stdout)
        except (OSError, subprocess.SubprocessError):
            return None

    def _find_external_cloudflared_pid(self) -> int | None:
        try:
            res = subprocess.run(
                ["pgrep", "-x", "cloudflared"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip().splitlines()[0])
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return None

    def get_status(self) -> TunnelState:
        mode = self.resolve_mode()
        prom: PrometheusSnapshot | None = fetch_prometheus_metrics(self.config.metrics_url)

        if mode in ("systemd-user", "systemd-system"):
            user_scope = mode == "systemd-user"
            scope_tag = "user" if user_scope else "system"
            props = self._query_systemd(user_scope=user_scope)
            if props is None:
                traffic = self.tracker.update(None, None)
                return TunnelState(
                    active=False,
                    activating=False,
                    state_text="Unavailable",
                    substate="systemd error",
                    backend_label=f"systemd ({scope_tag})",
                    uptime_seconds=None,
                    traffic=traffic,
                    total_requests=None,
                    request_errors=None,
                    ha_connections=None,
                    metrics_available=False,
                    ip_accounting_available=False,
                    error=f"Could not query {self.config.service_name}",
                )

            load_state = props.get("LoadState", "unknown")
            active_state = props.get("ActiveState", "unknown")
            substate = props.get("SubState", "")

            if load_state == "not-found":
                traffic = self.tracker.update(None, None)
                return TunnelState(
                    active=False,
                    activating=False,
                    state_text="Not Installed",
                    substate=self.config.service_name,
                    backend_label=f"systemd ({scope_tag})",
                    uptime_seconds=None,
                    traffic=traffic,
                    total_requests=None,
                    request_errors=None,
                    ha_connections=None,
                    metrics_available=False,
                    ip_accounting_available=False,
                    error=f"Unit {self.config.service_name} not found",
                )

            is_active = active_state == "active"
            is_activating = active_state in ("activating", "reloading", "deactivating")

            uptime_sec: int | None = None
            if is_active:
                enter_us = _parse_uint(props.get("ActiveEnterTimestampMonotonic"))
                if enter_us:
                    uptime_sec = max(0, (_monotonic_usec_now() - enter_us) // 1_000_000)

            ip_in = _parse_uint(props.get("IPIngressBytes"))
            ip_out = _parse_uint(props.get("IPEgressBytes"))
            ip_acct_ok = ip_in is not None and ip_out is not None

            raw_rx = ip_in if ip_acct_ok else (prom.rx_bytes if prom else None)
            raw_tx = ip_out if ip_acct_ok else (prom.tx_bytes if prom else None)
            traffic = self.tracker.update(raw_rx if is_active else None, raw_tx if is_active else None)

            state_label = {
                "active": "Connected",
                "activating": "Connecting",
                "reloading": "Reloading",
                "deactivating": "Stopping",
                "inactive": "Stopped",
                "failed": "Failed",
            }.get(active_state, active_state.capitalize())

            return TunnelState(
                active=is_active,
                activating=is_activating,
                state_text=state_label,
                substate=substate or active_state,
                backend_label=f"systemd ({scope_tag})",
                uptime_seconds=uptime_sec,
                traffic=traffic,
                total_requests=prom.total_requests if prom else None,
                request_errors=prom.request_errors if prom else None,
                ha_connections=prom.ha_connections if prom else None,
                metrics_available=prom is not None,
                ip_accounting_available=ip_acct_ok,
                error=None if active_state != "failed" else "Service entered failed state",
                logs=self._query_journalctl(user_scope=user_scope),
            )

        # Direct process mode
        running = False
        if self._managed_proc is not None:
            if self._managed_proc.poll() is None:
                running = True
            else:
                self._managed_proc = None
                self._proc_start_monotonic = None

        if not running:
            ext_pid = self._find_external_cloudflared_pid()
            running = ext_pid is not None

        uptime_sec = None
        if running and self._proc_start_monotonic is not None:
            uptime_sec = max(0, int(time.monotonic() - self._proc_start_monotonic))

        raw_rx = prom.rx_bytes if (running and prom) else None
        raw_tx = prom.tx_bytes if (running and prom) else None
        traffic = self.tracker.update(raw_rx, raw_tx)

        return TunnelState(
            active=running,
            activating=False,
            state_text="Connected" if running else "Stopped",
            substate="running" if running else "no process",
            backend_label="process",
            uptime_seconds=uptime_sec,
            traffic=traffic,
            total_requests=prom.total_requests if prom else None,
            request_errors=prom.request_errors if prom else None,
            ha_connections=prom.ha_connections if prom else None,
            metrics_available=prom is not None,
            ip_accounting_available=False,
            logs=self.get_logs(),
        )

    def _run_systemctl(self, user_scope: bool, action: str) -> ActionResult:
        cmd = ["systemctl"]
        if user_scope:
            cmd.append("--user")
        cmd.extend([action, self.config.service_name])
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0)
            if res.returncode == 0:
                return ActionResult(True, f"Tunnel {action} succeeded")
            err = res.stderr.strip() or res.stdout.strip() or f"Exit code {res.returncode}"
            return ActionResult(False, err)
        except (OSError, subprocess.SubprocessError) as exc:
            return ActionResult(False, str(exc))

    def _build_process_command_and_env(self) -> tuple[list[str], dict[str, str]]:
        args = shlex.split(self.config.process_command)
        if not args:
            return [], dict(os.environ)

        if "--metrics" not in args and self.config.metrics_url:
            parsed = urlparse(self.config.metrics_url)
            if parsed.netloc:
                if "run" in args:
                    run_idx = args.index("run")
                    args = [*args[:run_idx], "--metrics", parsed.netloc, *args[run_idx:]]
                else:
                    args.extend(["--metrics", parsed.netloc])

        env = dict(os.environ)
        token = normalize_tunnel_token(self.config.tunnel_token)
        if token and "--token" not in args:
            env["TUNNEL_TOKEN"] = token
        return args, env

    def start(self) -> ActionResult:
        mode = self.resolve_mode()
        if mode == "systemd-user":
            return self._run_systemctl(True, "start")
        if mode == "systemd-system":
            return self._run_systemctl(False, "start")

        if self._managed_proc is not None and self._managed_proc.poll() is None:
            return ActionResult(True, "Tunnel already running")
        try:
            args, env = self._build_process_command_and_env()
            if not args:
                return ActionResult(False, "Empty process command")
            self._append_log(f"$ {shlex.join(args)}")
            self._managed_proc = subprocess.Popen(
                args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            self._proc_start_monotonic = time.monotonic()
            reader = threading.Thread(
                target=self._drain_process_output,
                args=(self._managed_proc,),
                daemon=True,
            )
            reader.start()
            return ActionResult(True, "Started cloudflared process")
        except OSError as exc:
            self._append_log(f"[tunnel-status] Failed to start: {exc}")
            return ActionResult(False, str(exc))

    def stop(self) -> ActionResult:
        mode = self.resolve_mode()
        if mode == "systemd-user":
            return self._run_systemctl(True, "stop")
        if mode == "systemd-system":
            return self._run_systemctl(False, "stop")

        if self._managed_proc is not None and self._managed_proc.poll() is None:
            self._append_log("[tunnel-status] Stopping cloudflared...")
            self._managed_proc.terminate()
            try:
                self._managed_proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._managed_proc.kill()
            self._managed_proc = None
            self._proc_start_monotonic = None
            return ActionResult(True, "Stopped cloudflared process")

        ext_pid = self._find_external_cloudflared_pid()
        if ext_pid is not None:
            try:
                subprocess.run(["kill", "-TERM", str(ext_pid)], check=True, timeout=3.0)
                return ActionResult(True, f"Sent SIGTERM to cloudflared ({ext_pid})")
            except (OSError, subprocess.SubprocessError) as exc:
                return ActionResult(False, str(exc))
        return ActionResult(True, "Tunnel already stopped")

    def restart(self) -> ActionResult:
        mode = self.resolve_mode()
        if mode == "systemd-user":
            return self._run_systemctl(True, "restart")
        if mode == "systemd-system":
            return self._run_systemctl(False, "restart")
        stop_res = self.stop()
        if not stop_res.ok:
            return stop_res
        return self.start()
