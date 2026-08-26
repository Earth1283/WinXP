from __future__ import annotations

import random

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QKeySequence, QPainter, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QInputDialog, QLabel, QMenu, QVBoxLayout, QWidget,
)

from . import apps, corruption, icons, theme, vfs as vfs_mod, xp_dialog
from .settings import WALLPAPERS, settings
from .start_menu import StartMenu
from .taskbar import Taskbar
from .window_manager import WindowManager

ICON_CELL = QSize(80, 90)
FILE_ICONS = {
    vfs_mod.TEXT: "text_file", vfs_mod.RICH: "wordpad",
    vfs_mod.IMAGE: "bitmap_file", vfs_mod.AUDIO: "audio_file",
    vfs_mod.FOLDER: "folder",
}


class DesktopIcon(QWidget):
    def __init__(self, node_id, parent):
        super().__init__(parent)
        self.node_id = node_id
        self.selected = False
        self.setFixedSize(ICON_CELL)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.text_label.setStyleSheet(
            "color: white; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self.text_label)

        self.refresh()

    def refresh(self):
        node = vfs_mod.vfs.get(self.node_id)
        if not node:
            return
        if node.kind == vfs_mod.SHORTCUT:
            key = node.icon or "text_file"
        elif self.node_id == vfs_mod.vfs.my_docs_id:
            key = "my_documents"
        elif self.node_id == vfs_mod.vfs.recycle_id:
            key = "recycle_bin"
        else:
            key = FILE_ICONS.get(node.kind, "text_file")
        self.icon_label.setPixmap(icons.icon(key, 40).pixmap(40, 40))
        self.text_label.setText(node.name)
        self._paint_selection()

    def _paint_selection(self):
        if self.selected:
            self.text_label.setStyleSheet(
                "color: white; font-size: 11px; background: #2f6fdb;"
            )
            self.icon_label.setStyleSheet("background: rgba(47,111,219,120);")
        else:
            self.text_label.setStyleSheet(
                "color: white; font-size: 11px; background: transparent;"
            )
            self.icon_label.setStyleSheet("background: transparent;")

    def set_selected(self, value):
        self.selected = value
        self._paint_selection()

    def mousePressEvent(self, ev):
        self.window().select_only(self)
        if ev.button() == Qt.MouseButton.RightButton:
            self.window().show_icon_menu(self.node_id, ev.globalPosition().toPoint())

    def mouseDoubleClickEvent(self, ev):
        self.window().open_node(self.node_id)


class Desktop(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle("Windows XP")
        screen = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(screen)
        self.setStyleSheet(theme.WINDOW_QSS)

        self.wm = WindowManager(self._desktop_rect)
        self.wm.on_window_added = self._on_window_added
        self.wm.on_window_removed = self._on_window_removed
        self.wm.on_window_state = self._on_window_state

        self.icons_widgets: dict[str, DesktopIcon] = {}
        self.selected_icon = None

        self.icon_area = QWidget(self)
        self.icon_area.setGeometry(0, 0, self.width(), self.height() - 34)

        self.taskbar = Taskbar(self)
        self.taskbar.start_clicked.connect(self._toggle_start)
        self.taskbar.task_clicked.connect(self._on_task_clicked)
        self.taskbar.task_manager_requested.connect(self._open_task_manager)

        QShortcut(QKeySequence("Ctrl+Shift+Esc"), self, self._open_task_manager)

        self._wallpaper_glitch = False
        self._glitch_timer = QTimer(self)
        self._glitch_timer.timeout.connect(self._glitch_tick)
        self._glitch_timer.start(3000)

        self.start_menu = StartMenu(self)
        self.start_menu.app_chosen.connect(self._launch)

        settings.wallpaper_changed.connect(self.update)

        self._layout_icons()
        self._reposition()

    def resizeEvent(self, ev):
        self._reposition()

    def _reposition(self):
        self.icon_area.setGeometry(0, 0, self.width(), self.height() - 34)
        self.taskbar.setGeometry(0, self.height() - 34, self.width(), 34)

    def _desktop_rect(self) -> QRect:
        top_left = self.mapToGlobal(QPoint(0, 0))
        return QRect(top_left, QSize(self.width(), self.height() - 34))

    def paintEvent(self, ev):
        p = QPainter(self)
        kind, c1, c2 = WALLPAPERS[settings.wallpaper]
        if kind == "solid":
            p.fillRect(self.rect(), QColor(c1))
        else:
            top, bot = QColor(c1), QColor(c2)
            for y in range(self.height()):
                t = y / max(1, self.height() - 1)
                c = QColor(
                    int(top.red() + (bot.red() - top.red()) * t),
                    int(top.green() + (bot.green() - top.green()) * t),
                    int(top.blue() + (bot.blue() - top.blue()) * t),
                )
                p.setPen(c)
                p.drawLine(0, y, self.width(), y)
        if self._wallpaper_glitch:
            for _ in range(40):
                bw = random.randint(20, 160)
                bh = random.randint(2, 14)
                bx = random.randint(0, max(1, self.width() - bw))
                by = random.randint(0, max(1, self.height() - 34 - bh))
                p.fillRect(bx, by, bw, bh, QColor(random.choice(
                    ["#ff00ff", "#00ffff", "#ffffff", "#000000", "#ff2020"]
                )))

    def flash_wallpaper_glitch(self):
        self._wallpaper_glitch = True
        self.update()
        QTimer.singleShot(260, self._clear_wallpaper_glitch)

    def _clear_wallpaper_glitch(self):
        self._wallpaper_glitch = False
        self.update()

    def _glitch_tick(self):
        health = corruption.health
        if health.level <= 0:
            return
        if health.is_dead("csrss.exe"):
            for w in self.wm.windows:
                if w.isVisible() and random.random() < 0.5:
                    w.titlebar.flash_glitch()
        if health.is_dead("winlogon.exe") and random.random() < 0.6:
            self.flash_wallpaper_glitch()
        if health.is_dead("services.exe") and random.random() < 0.4:
            candidates = [w for w in self.wm.windows
                          if w.isVisible() and getattr(w, "_app_key", None) != "task_manager"]
            if candidates:
                random.choice(candidates).freeze(random.randint(2500, 5000))
        if health.is_dead("lsass.exe") and random.random() < 0.2:
            xp_dialog.XPMessageBox.critical(
                self, "Security Alert",
                "Access is denied.\n\nThe Local Security Authority cannot be contacted."
            )
        if random.random() < health.level * 0.05:
            from .apps.bsod import crash
            crash(self.wm, "cascading system failure")

    def mousePressEvent(self, ev):
        self.select_only(None)
        if ev.button() == Qt.MouseButton.RightButton:
            self.show_desktop_menu(ev.globalPosition().toPoint())

    def _layout_icons(self):
        selected_node = self.selected_icon.node_id if self.selected_icon is not None else None
        for w in self.icons_widgets.values():
            w.deleteLater()
        self.icons_widgets.clear()
        self.selected_icon = None

        children = sorted(
            vfs_mod.vfs.children_of(vfs_mod.vfs.desktop_id),
            key=lambda n: n.created,
        )
        margin = 10
        col_height = self.height() - 34 - margin * 2
        per_col = max(1, col_height // ICON_CELL.height())
        for i, node in enumerate(children):
            col = i // per_col
            row = i % per_col
            icon_w = DesktopIcon(node.id, self.icon_area)
            icon_w.move(margin + col * ICON_CELL.width(), margin + row * ICON_CELL.height())
            icon_w.show()
            self.icons_widgets[node.id] = icon_w
            if node.id == selected_node:
                self.select_only(icon_w)

    def select_only(self, widget):
        if self.selected_icon is not None:
            self.selected_icon.set_selected(False)
        self.selected_icon = widget
        if widget is not None:
            widget.set_selected(True)

    def open_node(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        if node.kind == vfs_mod.SHORTCUT:
            self._launch(node.target)
        elif node.kind == vfs_mod.FOLDER:
            self._launch(f"explorer:{node_id}")
        elif node.kind == vfs_mod.TEXT:
            self._launch(f"notepad:{node_id}")
        elif node.kind == vfs_mod.RICH:
            self._launch(f"wordpad:{node_id}")
        elif node.kind == vfs_mod.IMAGE:
            self._launch(f"paint:{node_id}")
        elif node.kind == vfs_mod.AUDIO:
            self._launch(f"wmp:{node_id}")

    def _launch(self, target):
        apps.launch(self.wm, target)

    def _open_task_manager(self):
        for window in self.wm.windows:
            if getattr(window, "_app_key", None) == "task_manager":
                self.wm.restore(window)
                return
        self._launch("task_manager")

    def show_icon_menu(self, node_id, global_pos):
        node = vfs_mod.vfs.get(node_id)
        menu = QMenu(self)
        open_act = menu.addAction("Open")
        open_act.triggered.connect(lambda: self.open_node(node_id))
        menu.addSeparator()
        rename_act = menu.addAction("Rename")
        rename_act.triggered.connect(lambda: self._rename_icon(node_id))
        delete_act = menu.addAction("Delete")
        delete_act.triggered.connect(lambda: self._delete_icon(node_id))
        menu.exec(global_pos)

    def show_desktop_menu(self, global_pos):
        menu = QMenu(self)
        new_menu = menu.addMenu("New")
        folder_act = new_menu.addAction("Folder")
        folder_act.triggered.connect(self._new_folder)
        text_act = new_menu.addAction("Text Document")
        text_act.triggered.connect(self._new_text)
        image_act = new_menu.addAction("Bitmap Image")
        image_act.triggered.connect(self._new_image)
        menu.addSeparator()
        refresh_act = menu.addAction("Refresh")
        refresh_act.triggered.connect(self._layout_icons)
        menu.addSeparator()
        props_act = menu.addAction("Properties")
        props_act.triggered.connect(lambda: self._launch("control_panel"))
        menu.exec(global_pos)

    def _new_folder(self):
        vfs_mod.vfs.create_folder(vfs_mod.vfs.desktop_id)
        self._layout_icons()

    def _new_text(self):
        vfs_mod.vfs.create_text_file(vfs_mod.vfs.desktop_id)
        self._layout_icons()

    def _new_image(self):
        from . import image_codec
        vfs_mod.vfs.create_image_file(
            vfs_mod.vfs.desktop_id, data=image_codec.to_bytes(image_codec.blank())
        )
        self._layout_icons()

    def _rename_icon(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        name, ok = QInputDialog.getText(self, "Rename", "New name:", text=node.name)
        if ok and name.strip():
            vfs_mod.vfs.rename(node_id, name.strip())
            self._layout_icons()

    def _delete_icon(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if xp_dialog.XPMessageBox.confirm(self, "Confirm Delete", f"Delete '{node.name}'?"):
            if node.kind == vfs_mod.SHORTCUT:
                vfs_mod.vfs.delete(node_id, permanent=True)
            else:
                vfs_mod.vfs.delete(node_id)
            self._layout_icons()

    def _toggle_start(self):
        if self.start_menu.isVisible():
            self.start_menu.hide()
        else:
            self.start_menu.show_above(self.taskbar.start_btn)

    def _on_window_added(self, window):
        self.taskbar.add_window(window)

    def _on_window_removed(self, window):
        self.taskbar.remove_window(window)

    def _on_window_state(self):
        if self.wm.active:
            self.taskbar.set_checked(self.wm.active)

    def _on_task_clicked(self, window):
        if window.isVisible() and self.wm.active is window:
            window.minimize()
        else:
            self.wm.restore(window)
