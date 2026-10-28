"""Stylesheets and asset paths shared by the PhotoChop window."""
from __future__ import annotations

import os


ASSETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "assets")

TOOLBOX_QSS = """
QToolButton { border: 1px solid transparent; background: transparent; }
QToolButton:hover { border: 1px solid #a0a090; background: #f6f5ee; }
QToolButton:checked { border: 1px solid #6a6a5a; background: #d4d0c0;
                      border-top-color: #8a8a7a; border-left-color: #8a8a7a; }
"""

OPTIONS_QSS = """
QWidget#optionsBar { background: #ece9d8; border-bottom: 1px solid #9a9a8a; }
QWidget#optHolder { background: transparent; }
QLabel { background: transparent; font-size: 11px; }
QCheckBox { background: transparent; font-size: 11px; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { font-size: 11px; }
"""
