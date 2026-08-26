"""Windows XP "Luna" theme constants and QSS."""

# Luna blue palette
XP_BLUE_TITLE_START = "#0058e6"
XP_BLUE_TITLE_MID = "#3d95ff"
XP_BLUE_TITLE_END = "#0058e6"
XP_BLUE_TITLE_ACTIVE_TOP = "#0997ff"
XP_TASKBAR_START = "#245edb"
XP_TASKBAR_END = "#3f8cf3"
XP_START_GREEN_START = "#3fa129"
XP_START_GREEN_END = "#1a6e0a"
XP_DESKTOP_TEAL = "#3a6ea5"
XP_WINDOW_BG = "#ece9d8"
XP_BUTTON_FACE = "#ece9d8"
XP_SELECTION_BLUE = "#316ac5"
XP_LINK_BLUE = "#0000ee"

FONT_FAMILY = "Tahoma"

TITLEBAR_ACTIVE_GRADIENT = f"""
    qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0a58f2, stop:0.5 #3f8cf6, stop:1 #0058e6)
"""

TITLEBAR_INACTIVE_GRADIENT = """
    qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #8296b8, stop:0.5 #94a8c9, stop:1 #7f93b5)
"""

TASKBAR_GRADIENT = """
    qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2a6fdb, stop:0.5 #1c4bc9, stop:1 #1941b8)
"""

START_BUTTON_GRADIENT = """
    qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6fcf4a, stop:0.4 #3fa129, stop:1 #1a6e0a)
"""

WINDOW_QSS = f"""
QWidget {{
    font-family: '{FONT_FAMILY}';
    font-size: 12px;
}}
QMainWindow, QDialog {{
    background: {XP_WINDOW_BG};
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:0.5 #ece9d8, stop:1 #d6d2c2);
    border: 1px solid #716f64;
    border-radius: 3px;
    padding: 4px 14px;
    min-height: 18px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #fff7d6, stop:0.5 #ffe89a, stop:1 #ffce4d);
    border: 1px solid #cc9933;
}}
QPushButton:pressed {{
    background: #ffce4d;
}}
QMenuBar {{
    background: {XP_WINDOW_BG};
    border-bottom: 1px solid #aca998;
}}
QMenuBar::item:selected {{
    background: {XP_SELECTION_BLUE};
    color: white;
}}
QMenu {{
    background: white;
    color: black;
    border: 1px solid #716f64;
}}
QMenu::item {{
    color: black;
    padding: 4px 24px 4px 12px;
}}
QMenu::item:selected {{
    background: {XP_SELECTION_BLUE};
    color: white;
}}
QMenu::item:disabled {{
    color: #888888;
}}
QScrollBar:vertical {{
    background: #ece9d8;
    width: 17px;
    border: 1px solid #9b9b9b;
}}
QScrollBar::handle:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #f4f3ee, stop:0.5 #d6d2c2, stop:1 #f4f3ee);
    border: 1px solid #9b9b9b;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    background: #ece9d8;
    height: 16px;
    border: 1px solid #9b9b9b;
}}
QToolTip {{
    background: #ffffe1;
    border: 1px solid black;
    color: black;
}}
QStatusBar {{
    background: {XP_WINDOW_BG};
    border-top: 1px solid #aca998;
}}
"""
