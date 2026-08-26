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

# "Appearance" schemes -- real XP shipped Blue/Olive Green/Silver. Anything
# that paints chrome (titlebar, taskbar, start button, start menu header)
# should read colors via current_scheme() at paint time, not import these
# as constants, so switching schemes repaints live without rebuilding windows.
SCHEMES = {
    "Windows XP (Blue)": dict(
        title_top="#0a58f2", title_mid="#3f8cf6", title_bot="#0058e6",
        taskbar_top="#3f8cf3", taskbar_bot="#1941b8",
        start_top="#8fe36a", start_bot="#1a6e0a",
        header_left="#1657d6", header_right="#3f8cf6",
    ),
    "Olive Green": dict(
        title_top="#8ba33f", title_mid="#a9c05a", title_bot="#6e8a2c",
        taskbar_top="#a9c05a", taskbar_bot="#5c7a1f",
        start_top="#c9dc7a", start_bot="#6e8a2c",
        header_left="#5c7a1f", header_right="#a9c05a",
    ),
    "Silver": dict(
        title_top="#8592a8", title_mid="#a4b0c4", title_bot="#6e7b91",
        taskbar_top="#a4b0c4", taskbar_bot="#5f6c80",
        start_top="#c3cbd8", start_bot="#6e7b91",
        header_left="#5f6c80", header_right="#a4b0c4",
    ),
}

_current_scheme_name = "Windows XP (Blue)"


def set_scheme(name: str):
    global _current_scheme_name
    if name in SCHEMES:
        _current_scheme_name = name


def current_scheme_name() -> str:
    return _current_scheme_name


def current_scheme() -> dict:
    return SCHEMES[_current_scheme_name]

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
