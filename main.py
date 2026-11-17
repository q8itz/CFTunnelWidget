#!/usr/bin/env python3
"""Entry point for Tunnel Status."""

import sys

from tunnel_status.app import run_app

if __name__ == "__main__":
    sys.exit(run_app())
