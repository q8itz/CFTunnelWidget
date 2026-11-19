"""Settings dialog for configuring Tunnel Status."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import AppConfig, EdgeIpVersion, ServiceMode, normalize_tunnel_token
from .theme import DIALOG_QSS


class SettingsDialog(QDialog):
    """Modal dialog for editing AppConfig."""

    reset_stats_requested = pyqtSignal()

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tunnel Status Settings")
        self.setMinimumWidth(400)
        self.setStyleSheet(DIALOG_QSS)

        self._config = config
        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(10)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["auto", "systemd-user", "systemd-system", "process"])
        idx = self._mode_combo.findText(config.mode)
        if idx >= 0:
            self._mode_combo.setCurrentIndex(idx)
        form.addRow("Control Mode:", self._mode_combo)

        self._service_edit = QLineEdit(config.service_name)
        form.addRow("Systemd Unit:", self._service_edit)

        token_row = QHBoxLayout()
        token_row.setSpacing(6)
        self._token_edit = QLineEdit(config.tunnel_token)
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("Paste tunnel token (eyJ...)")
        self._token_toggle_btn = QPushButton("Show")
        self._token_toggle_btn.setCheckable(True)
        self._token_toggle_btn.toggled.connect(self._toggle_token_visibility)
        token_row.addWidget(self._token_edit, 1)
        token_row.addWidget(self._token_toggle_btn)
        form.addRow("Tunnel Token:", token_row)

        self._edge_ip_combo = QComboBox()
        self._edge_ip_combo.addItem("Auto (IPv4 / IPv6)", "auto")
        self._edge_ip_combo.addItem("IPv6 only (6)", "6")
        self._edge_ip_combo.addItem("IPv4 only (4)", "4")
        ip_idx = self._edge_ip_combo.findData(config.edge_ip_version)
        if ip_idx >= 0:
            self._edge_ip_combo.setCurrentIndex(ip_idx)
        form.addRow("Edge IP Version:", self._edge_ip_combo)

        self._metrics_edit = QLineEdit(config.metrics_url)
        self._metrics_edit.setPlaceholderText("http://127.0.0.1:20241/metrics")
        form.addRow("Metrics URL:", self._metrics_edit)

        self._cmd_edit = QLineEdit(config.process_command)
        form.addRow("Process Command:", self._cmd_edit)

        self._poll_spin = QSpinBox()
        self._poll_spin.setRange(500, 30000)
        self._poll_spin.setSingleStep(500)
        self._poll_spin.setSuffix(" ms")
        self._poll_spin.setValue(config.poll_interval_ms)
        form.addRow("Poll Interval:", self._poll_spin)

        self._persist_chk = QCheckBox("Persist all-time traffic stats across restarts")
        self._persist_chk.setChecked(config.persist_stats)
        form.addRow("", self._persist_chk)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        reset_btn = QPushButton("Reset All-Time Stats")
        reset_btn.clicked.connect(self.reset_stats_requested.emit)
        buttons.addWidget(reset_btn)
        buttons.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        save_btn = QPushButton("Save")
        save_btn.setObjectName("SaveBtn")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.accept)
        buttons.addWidget(save_btn)

        layout.addLayout(buttons)

    def _toggle_token_visibility(self, checked: bool) -> None:
        self._token_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )
        self._token_toggle_btn.setText("Hide" if checked else "Show")

    def build_config(self) -> AppConfig:
        mode_text = self._mode_combo.currentText()
        mode: ServiceMode = (
            mode_text
            if mode_text in ("auto", "systemd-user", "systemd-system", "process")
            else "auto"
        )
        edge_ip_data = self._edge_ip_combo.currentData()
        edge_ip: EdgeIpVersion = edge_ip_data if edge_ip_data in ("auto", "6", "4") else "auto"
        return AppConfig(
            mode=mode,
            service_name=self._service_edit.text().strip() or "cloudflared.service",
            tunnel_token=normalize_tunnel_token(self._token_edit.text()),
            edge_ip_version=edge_ip,
            metrics_url=self._metrics_edit.text().strip(),
            poll_interval_ms=self._poll_spin.value(),
            persist_stats=self._persist_chk.isChecked(),
            process_command=self._cmd_edit.text().strip() or "cloudflared tunnel run",
        )
