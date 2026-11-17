#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"
SYSTEMD_USER_DIR="${HOME}/.config/systemd/user"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${SYSTEMD_USER_DIR}"

cat > "${BIN_DIR}/tunnel-status" <<EOF
#!/usr/bin/env bash
exec python3 "${REPO_DIR}/main.py" "\$@"
EOF
chmod +x "${BIN_DIR}/tunnel-status"

cp "${REPO_DIR}/packaging/tunnel-status.desktop" "${APP_DIR}/tunnel-status.desktop"
cp "${REPO_DIR}/packaging/tunnel-status.service.example" "${SYSTEMD_USER_DIR}/tunnel-status.service"

echo "Installed launcher to ${BIN_DIR}/tunnel-status"
echo "Installed desktop entry to ${APP_DIR}/tunnel-status.desktop"
echo "Installed user service to ${SYSTEMD_USER_DIR}/tunnel-status.service"

if command -v systemctl >/dev/null 2>&1; then
    systemctl --user daemon-reload
    systemctl --user enable --now tunnel-status.service
    echo "Enabled and started tunnel-status.service (user)"
fi
