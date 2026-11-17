# Tunnel Status

A sleek, native Linux system tray widget (Wayland & X11) for monitoring and controlling a `cloudflared` tunnel.

## Features

- **Cross-desktop System Tray Icon (`StatusNotifierItem`)**: Works natively on KDE Plasma (Wayland & X11), GNOME (with AppIndicator extension), XFCE, and Waybar/Sway/Hyprland.
- **Right-Click Context Menu**: Live status, Rx/Tx traffic summary, **Start**, **Stop**, **Restart**, **Open Dashboard**, **Settings**, and **Quit**.
- **Left-Click Floating Dashboard**: Dark-glass popover card with:
  - Live connection status badge & uptime
  - **Ingress (Rx)**, **Egress (Tx)**, and **Total Traffic** (session + persisted all-time)
  - Real-time dual-line **Throughput Sparkline**
  - HA connections & total request count (when `cloudflared` Prometheus metrics are enabled)
  - One-click Start / Stop / Restart controls
- **Flexible Backends**: Auto-detects `systemd --user`, system `systemd`, or direct `cloudflared` process mode.

## Requirements

- Python 3.10+
- `PyQt6` (`python3-pyqt6` on Debian/Ubuntu, `python-pyqt6` on Arch)

## Quick Start

```bash
python3 main.py
```

Or install the desktop launcher:

```bash
chmod +x install.sh
./install.sh
```

## Traffic Accounting Setup

1. **Systemd `IPAccounting=yes`** (recommended): Add `IPAccounting=yes` to your `cloudflared.service` `[Service]` section (see `packaging/cloudflared-user.service.example`).
2. **Prometheus Metrics**: Run `cloudflared` with `--metrics 127.0.0.1:20241` to also display active HA connections and total HTTP/tunnel requests.
3. **Passwordless Start/Stop**: Either run `cloudflared` as a `systemd --user` service, or install `packaging/90-cloudflared-nopasswd.rules.example` into `/etc/polkit-1/rules.d/`.
