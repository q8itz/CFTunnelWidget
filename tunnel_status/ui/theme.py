"""Color palette and Qt stylesheets for a modern dark-glass UI."""

BG_CARD = "#12151E"
BG_TILE = "#1A1E2B"
BG_TILE_HOVER = "#212636"
BORDER_SUBTLE = "#282E3F"
TEXT_PRIMARY = "#F1F5F9"
TEXT_SECONDARY = "#94A3B8"
TEXT_MUTED = "#64748B"

ACCENT_RX = "#38BDF8"       # Sky cyan (Ingress / Download)
ACCENT_TX = "#A78BFA"       # Soft violet (Egress / Upload)
STATUS_ACTIVE = "#10B981"   # Emerald
STATUS_WARN = "#F59E0B"     # Amber
STATUS_STOPPED = "#64748B"  # Slate
STATUS_ERROR = "#F43F5E"    # Rose

POPOVER_QSS = f"""
QWidget#PopoverCard {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 14px;
    color: {TEXT_PRIMARY};
    font-family: "Inter", "Noto Sans", "Segoe UI", sans-serif;
}}
QFrame#MetricTile {{
    background-color: {BG_TILE};
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
}}
QFrame#GraphCard {{
    background-color: {BG_TILE};
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 10px;
}}
QPlainTextEdit#LogConsole {{
    background-color: #0B0E14;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    color: #CBD5E1;
    font-family: "JetBrains Mono", "Fira Code", "Noto Sans Mono", monospace;
    font-size: 10px;
    padding: 6px;
    selection-background-color: #0284C7;
}}
QPushButton#MiniLinkBtn {{
    background-color: transparent;
    border: none;
    color: {TEXT_SECONDARY};
    font-size: 10px;
    padding: 2px 4px;
}}
QPushButton#MiniLinkBtn:hover {{
    color: {TEXT_PRIMARY};
}}
QLabel#TitleLabel {{
    color: {TEXT_PRIMARY};
    font-size: 14px;
    font-weight: 700;
}}
QLabel#SubLabel {{
    color: {TEXT_SECONDARY};
    font-size: 11px;
}}
QLabel#TileTitle {{
    color: {TEXT_SECONDARY};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.4px;
}}
QLabel#TileValue {{
    color: {TEXT_PRIMARY};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#TileSub {{
    color: {TEXT_MUTED};
    font-size: 11px;
}}
QPushButton#IconBtn {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    color: {TEXT_SECONDARY};
    font-size: 13px;
    padding: 4px 6px;
}}
QPushButton#IconBtn:hover {{
    background-color: {BG_TILE_HOVER};
    color: {TEXT_PRIMARY};
}}
QPushButton#PrimaryStartBtn {{
    background-color: #059669;
    border: 1px solid #10B981;
    border-radius: 8px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 14px;
}}
QPushButton#PrimaryStartBtn:hover {{
    background-color: #10B981;
}}
QPushButton#PrimaryStartBtn:disabled {{
    background-color: #1F2937;
    border-color: #374151;
    color: #6B7280;
}}
QPushButton#PrimaryStopBtn {{
    background-color: #BE123C;
    border: 1px solid #F43F5E;
    border-radius: 8px;
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 14px;
}}
QPushButton#PrimaryStopBtn:hover {{
    background-color: #E11D48;
}}
QPushButton#SecondaryBtn {{
    background-color: {BG_TILE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 500;
    padding: 8px 12px;
}}
QPushButton#SecondaryBtn:hover {{
    background-color: {BG_TILE_HOVER};
}}
QPushButton#SecondaryBtn:disabled {{
    color: {TEXT_MUTED};
}}
"""

MENU_QSS = f"""
QMenu {{
    background-color: {BG_CARD};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 8px;
    padding: 6px;
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QMenu::item {{
    padding: 6px 18px 6px 12px;
    border-radius: 6px;
}}
QMenu::item:selected {{
    background-color: {BG_TILE_HOVER};
}}
QMenu::item:disabled {{
    color: {TEXT_SECONDARY};
    font-weight: 600;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_SUBTLE};
    margin: 4px 8px;
}}
"""

DIALOG_QSS = f"""
QDialog {{
    background-color: {BG_CARD};
    color: {TEXT_PRIMARY};
    font-family: "Inter", "Noto Sans", "Segoe UI", sans-serif;
}}
QLabel {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
}}
QLineEdit, QComboBox, QSpinBox {{
    background-color: {BG_TILE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 6px 8px;
    font-size: 12px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT_RX};
}}
QCheckBox {{
    color: {TEXT_PRIMARY};
    font-size: 12px;
    spacing: 8px;
}}
QPushButton {{
    background-color: {BG_TILE};
    border: 1px solid {BORDER_SUBTLE};
    border-radius: 6px;
    color: {TEXT_PRIMARY};
    padding: 6px 14px;
    font-size: 12px;
}}
QPushButton:hover {{
    background-color: {BG_TILE_HOVER};
}}
QPushButton#SaveBtn {{
    background-color: #0284C7;
    border-color: {ACCENT_RX};
    font-weight: 600;
}}
QPushButton#SaveBtn:hover {{
    background-color: #0EA5E9;
}}
"""
