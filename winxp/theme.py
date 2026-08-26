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

MENU_QSS = f"""
QMenuBar {{
    background: {XP_WINDOW_BG};
    border-bottom: 1px solid #aca998;
    padding: 1px 2px;
    spacing: 0px;
}}
QMenuBar::item {{
    background: transparent;
    color: black;
    padding: 3px 8px;
    margin: 0px;
    border: 1px solid transparent;
    border-radius: 2px;
}}
QMenuBar::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #eaf3ff, stop:1 #c2ddfc);
    border: 1px solid #7da2ce;
}}
QMenuBar::item:pressed {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #c2ddfc, stop:1 #a6c8ee);
    border: 1px solid #3169c6;
}}
QMenu {{
    background: white;
    color: black;
    border: 1px solid #716f64;
    padding: 2px 0px;
}}
QMenu::item {{
    color: black;
    padding: 4px 24px 4px 20px;
}}
QMenu::item:selected {{
    background: {XP_SELECTION_BLUE};
    color: white;
}}
QMenu::item:disabled {{
    color: #888888;
}}
QMenu::separator {{
    height: 1px;
    background: #d4d0c8;
    margin: 3px 4px;
}}
QMenu::icon {{
    padding-left: 4px;
}}
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
{MENU_QSS}
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


def style_menubar(bar):
    """Force the menu bar to render inside the window instead of the OS's
    native global menu bar (macOS), and give it authentic Luna chrome."""
    bar.setNativeMenuBar(False)
    bar.setStyleSheet(MENU_QSS)
