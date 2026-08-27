"""Shared look for the Setup wizard.

Lives on its own so the wizard and the extra pages cannot drift apart, and
so neither has to import the other.
"""
from __future__ import annotations

import platform

_SYSTEM = platform.system()

# Tahoma only exists on Windows -- pick a font that's actually installed on
# whatever OS this is running under so text doesn't fall back to an ugly
# generic serif on Linux/mac.
UI_FONT_FAMILY = {"Windows": "Tahoma", "Darwin": "Helvetica Neue"}.get(
    _SYSTEM, "DejaVu Sans")
MONO_FONT_FAMILY = {"Windows": "Lucida Console", "Darwin": "Monaco"}.get(
    _SYSTEM, "DejaVu Sans Mono")

SIDEBAR_BLUE_TOP = "#1657d6"
SIDEBAR_BLUE_BOTTOM = "#3f8cf6"
BODY_BG = "#ece9d8"
TEXT_COLOR = "#000000"
SUBTEXT_COLOR = "#4a4a4a"
ACCENT_BLUE = "#1657d6"
RULE_COLOR = "#aca899"

# The blue of the text-mode phase, and the grey status strip along its bottom.
SETUP_BLUE = "#0a246a"
SETUP_STATUS_BG = "#c0c0c0"

BUTTON_STYLE = f"""
QPushButton {{
    background-color: #f5f4ee;
    border: 1px solid #7f9db9;
    border-radius: 3px;
    padding: 4px 14px;
    color: {TEXT_COLOR};
}}
QPushButton:hover {{ background-color: #ffffff; }}
QPushButton:pressed {{ background-color: #dcdad5; }}
QPushButton:disabled {{ color: #9a9a9a; border-color: #c8c8c8; }}
"""

PROGRESSBAR_STYLE = f"""
QProgressBar {{
    border: 1px solid #7f9db9;
    border-radius: 2px;
    background: #ffffff;
    text-align: center;
    height: 18px;
    color: {TEXT_COLOR};
}}
QProgressBar::chunk {{
    background-color: {ACCENT_BLUE};
    border-radius: 2px;
}}
"""

TREE_STYLE = f"""
QTreeWidget {{
    background: #ffffff;
    border: 1px solid #7f9db9;
    color: {TEXT_COLOR};
    outline: none;
}}
QTreeWidget::item {{ height: 19px; }}
QTreeWidget::item:selected {{ background: {ACCENT_BLUE}; color: #ffffff; }}
QHeaderView::section {{
    background: #f0eee2;
    border: none;
    border-right: 1px solid {RULE_COLOR};
    border-bottom: 1px solid {RULE_COLOR};
    padding: 3px 6px;
    color: {TEXT_COLOR};
}}
"""

TEXTBOX_STYLE = f"""
QTextEdit {{
    background: #ffffff;
    border: 1px solid #7f9db9;
    color: {TEXT_COLOR};
}}
"""

KEYBOX_STYLE = f"""
QLineEdit {{
    background: #ffffff;
    border: 1px solid #7f9db9;
    padding: 3px;
    color: {TEXT_COLOR};
}}
QLineEdit:focus {{ border: 1px solid {ACCENT_BLUE}; }}
"""
