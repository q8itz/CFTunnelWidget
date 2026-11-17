#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/applications"

mkdir -p "${BIN_DIR}" "${APP_DIR}"

cat > "${BIN_DIR}/tunnel-status" <<EOF
#!/usr/bin/env bash
exec python3 "${REPO_DIR}/main.py" "\$@"
EOF
chmod +x "${BIN_DIR}/tunnel-status"

cp "${REPO_DIR}/packaging/tunnel-status.desktop" "${APP_DIR}/tunnel-status.desktop"

echo "Installed launcher to ${BIN_DIR}/tunnel-status"
echo "Installed desktop entry to ${APP_DIR}/tunnel-status.desktop"
echo "To autostart on login: mkdir -p ~/.config/autostart && cp ${APP_DIR}/tunnel-status.desktop ~/.config/autostart/"
