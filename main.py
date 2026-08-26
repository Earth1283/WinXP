import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import QApplication

from winxp import theme
from winxp.desktop import Desktop
from winxp.vfs import vfs


def _light_palette():
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.XP_WINDOW_BG))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Base, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f0f0f0"))
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.XP_WINDOW_BG))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#ffffe1"))
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#888888"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.XP_SELECTION_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#888888"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#888888"))
    return palette


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setPalette(_light_palette())
    app.setFont(QFont("Tahoma", 9))
    vfs.load_or_init()
    desktop = Desktop()
    desktop.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
