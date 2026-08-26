from __future__ import annotations

import os
import random

from PyQt6.QtCore import QPoint, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QAction, QColor, QPainter, QPen, QPolygon
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QSlider, QStackedLayout, QVBoxLayout, QWidget,
)

from .. import icons, theme, vfs as vfs_mod
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox

AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".wmv"}
MEDIA_FILTER = (
    "Media Files (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma "
    "*.mp4 *.mov *.avi *.mkv *.webm *.m4v *.wmv)"
)
FILE_ICON_BY_KIND = {vfs_mod.VIDEO: "video_file"}  # else falls back to audio_file

SLIDER_QSS = """
    QSlider::groove:horizontal { height: 4px; background: #aca998; border-radius: 2px; }
    QSlider::handle:horizontal {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #9fb8dd);
        border: 1px solid #4a6ea8; width: 12px; margin: -5px 0; border-radius: 6px;
    }
"""


def _fmt_time(ms):
    total = max(0, ms // 1000)
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


class Visualizer(QWidget):
    """Decorative bar visualizer -- animates while playing, has no relation
    to the actual audio signal (Qt Multimedia doesn't expose spectrum data
    without a lot more plumbing than a toy app like this needs)."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(90)
        self.playing = False
        self.bars = [4] * 24
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(90)

    def set_playing(self, playing):
        self.playing = playing

    def _tick(self):
        if self.playing:
            self.bars = [max(3, min(100, b + random.randint(-30, 35))) for b in self.bars]
        else:
            self.bars = [max(2, b - 8) for b in self.bars]
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#02142a"))
        w, h = self.width(), self.height()
        n = len(self.bars)
        bw = w / n
        top, bot = QColor("#7fe0ff"), QColor("#0a4a8f")
        for i, v in enumerate(self.bars):
            bar_h = int(h * (v / 100.0))
            x = int(i * bw) + 1
            for y in range(bar_h):
                t = y / max(1, bar_h - 1) if bar_h > 1 else 0
                c = QColor(
                    int(top.red() + (bot.red() - top.red()) * t),
                    int(top.green() + (bot.green() - top.green()) * t),
                    int(top.blue() + (bot.blue() - top.blue()) * t),
                )
                p.fillRect(x, h - y, max(1, int(bw) - 2), 1, c)


class TransportButton(QPushButton):
    def __init__(self, glyph, size=28):
        super().__init__()
        self.glyph = glyph
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        pressed = self.isDown()
        top = QColor("#e8f0fb") if not pressed else QColor("#a9c4e8")
        bot = QColor("#9fb8dd") if not pressed else QColor("#7fa0d0")
        for y in range(r.height()):
            t = y / max(1, r.height() - 1)
            c = QColor(
                int(top.red() + (bot.red() - top.red()) * t),
                int(top.green() + (bot.green() - top.green()) * t),
                int(top.blue() + (bot.blue() - top.blue()) * t),
            )
            p.setPen(c)
            p.drawLine(r.left(), r.top() + y, r.right(), r.top() + y)
        p.setPen(QPen(QColor("#4a6ea8"), 1))
        p.drawRoundedRect(r, 3, 3)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#1a2f4a"))
        cx, cy = r.center().x(), r.center().y()
        g = self.glyph
        if g == "play":
            p.drawPolygon(QPolygon([QPoint(cx - 4, cy - 6), QPoint(cx - 4, cy + 6), QPoint(cx + 6, cy)]))
        elif g == "pause":
            p.drawRect(cx - 5, cy - 6, 3, 12)
            p.drawRect(cx + 2, cy - 6, 3, 12)
        elif g == "stop":
            p.drawRect(cx - 5, cy - 5, 10, 10)
        elif g == "prev":
            p.drawRect(cx - 6, cy - 6, 2, 12)
            p.drawPolygon(QPolygon([QPoint(cx + 6, cy - 6), QPoint(cx + 6, cy + 6), QPoint(cx - 4, cy)]))
        elif g == "next":
            p.drawPolygon(QPolygon([QPoint(cx - 6, cy - 6), QPoint(cx - 6, cy + 6), QPoint(cx + 4, cy)]))
            p.drawRect(cx + 4, cy - 6, 2, 12)


class WindowsMediaPlayerWindow(XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Windows Media Player", icon_key="wmp", size=QSize(660, 420))
        self._track_ids: list[str] = []
        self._current_id = None
        self._seeking = False

        self.player = QMediaPlayer(self)
        self.audio_out = QAudioOutput(self)
        self.audio_out.setVolume(0.7)
        self.player.setAudioOutput(self.audio_out)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.mediaStatusChanged.connect(self._on_media_status)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setMenuBar(self._build_menu())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_now_playing(), 1)
        body.addWidget(self._build_playlist())
        root.addLayout(body, 1)

        self.set_content_layout(root)
        self._load_playlist()
        if node_id:
            self._play_track(node_id)

    def closeEvent(self, ev):
        self.player.stop()
        super().closeEvent(ev)

    # -- chrome ---------------------------------------------------------
    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        theme.style_menubar(bar)
        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act("&Import from Computer...", self._import_from_computer))
        file_menu.addSeparator()
        file_menu.addAction(self._act("E&xit", self.close))
        bar.addMenu("&View")
        bar.addMenu("&Play")
        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act("&About Windows Media Player", self._about))
        return bar

    def _act(self, text, slot):
        act = QAction(text, self)
        act.triggered.connect(slot)
        return act

    def _build_now_playing(self):
        panel = QWidget()
        panel.setStyleSheet(f"background: {theme.XP_WINDOW_BG};")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.stack = QStackedLayout()
        self.visualizer = Visualizer()
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background: black;")
        self.stack.addWidget(self.visualizer)
        self.stack.addWidget(self.video_widget)
        stack_container = QWidget()
        stack_container.setLayout(self.stack)
        layout.addWidget(stack_container, 1)
        self.player.setVideoOutput(self.video_widget)

        self.now_playing = QLabel("No track selected")
        self.now_playing.setStyleSheet("background: transparent; font-weight: bold;")
        layout.addWidget(self.now_playing)

        seek_row = QHBoxLayout()
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet(SLIDER_QSS)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        seek_row.addWidget(self.seek_slider, 1)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("background: transparent;")
        seek_row.addWidget(self.time_label)
        layout.addLayout(seek_row)

        transport_row = QHBoxLayout()
        transport_row.addStretch(1)
        self.prev_btn = TransportButton("prev")
        self.play_btn = TransportButton("play", size=32)
        self.stop_btn = TransportButton("stop")
        self.next_btn = TransportButton("next")
        self.prev_btn.clicked.connect(self._play_prev)
        self.play_btn.clicked.connect(self._toggle_play)
        self.stop_btn.clicked.connect(self.player.stop)
        self.next_btn.clicked.connect(self._play_next)
        for b in (self.prev_btn, self.play_btn, self.stop_btn, self.next_btn):
            transport_row.addWidget(b)
        transport_row.addSpacing(16)
        vol_label = QLabel("Vol")
        vol_label.setStyleSheet("background: transparent;")
        transport_row.addWidget(vol_label)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setStyleSheet(SLIDER_QSS)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(70)
        self.vol_slider.valueChanged.connect(lambda v: self.audio_out.setVolume(v / 100))
        transport_row.addWidget(self.vol_slider)
        transport_row.addStretch(1)
        layout.addLayout(transport_row)

        return panel

    def _build_playlist(self):
        panel = QWidget()
        panel.setFixedWidth(190)
        panel.setStyleSheet(f"background: {theme.XP_WINDOW_BG}; border-left: 1px solid #aca998;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        header = QLabel("Now Playing")
        header.setStyleSheet("background: transparent; font-weight: bold;")
        layout.addWidget(header)
        self.list = QListWidget()
        self.list.setStyleSheet("background: white;")
        self.list.itemDoubleClicked.connect(self._on_item_double)
        layout.addWidget(self.list, 1)
        import_btn = QPushButton("Import...")
        import_btn.clicked.connect(self._import_from_computer)
        layout.addWidget(import_btn)
        return panel

    # -- playlist ---------------------------------------------------------
    def _load_playlist(self):
        self.list.clear()
        self._track_ids = []
        children = sorted(vfs_mod.vfs.children_of(vfs_mod.vfs.my_music_id), key=lambda n: n.name.lower())
        for child in children:
            if child.kind not in (vfs_mod.AUDIO, vfs_mod.VIDEO):
                continue
            icon_key = FILE_ICON_BY_KIND.get(child.kind, "audio_file")
            item = QListWidgetItem(icons.icon(icon_key, 18), child.name)
            item.setData(Qt.ItemDataRole.UserRole, child.id)
            self.list.addItem(item)
            self._track_ids.append(child.id)

    def _on_item_double(self, item):
        self._play_track(item.data(Qt.ItemDataRole.UserRole))

    # -- playback ---------------------------------------------------------
    def _play_track(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        path = vfs_mod.vfs.content_path(node_id)
        if not os.path.exists(path):
            XPMessageBox.critical(self, "Windows Media Player", f"Cannot find '{node.name}'.")
            return
        self._current_id = node_id
        self.stack.setCurrentWidget(self.video_widget if node.kind == vfs_mod.VIDEO else self.visualizer)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        self.now_playing.setText(node.name)
        self.setWindowTitle(f"{node.name} - Windows Media Player")

    def _toggle_play(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self._current_id:
            self.player.play()
        elif self._track_ids:
            self._play_track(self._track_ids[0])

    def _play_next(self):
        if not self._track_ids or self._current_id not in self._track_ids:
            return
        idx = self._track_ids.index(self._current_id)
        if idx + 1 < len(self._track_ids):
            self._play_track(self._track_ids[idx + 1])
        else:
            self.player.stop()

    def _play_prev(self):
        if not self._track_ids or self._current_id not in self._track_ids:
            return
        idx = self._track_ids.index(self._current_id)
        if idx > 0:
            self._play_track(self._track_ids[idx - 1])

    def _on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.visualizer.set_playing(playing)
        self.play_btn.glyph = "pause" if playing else "play"
        self.play_btn.update()

    def _on_position(self, pos):
        if not self._seeking:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(pos)
            self.seek_slider.blockSignals(False)
        self.time_label.setText(f"{_fmt_time(pos)} / {_fmt_time(self.player.duration())}")

    def _on_duration(self, dur):
        self.seek_slider.setRange(0, max(0, dur))

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._play_next()

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_released(self):
        self.player.setPosition(self.seek_slider.value())
        self._seeking = False

    # -- import from the real host filesystem ------------------------------
    def _import_from_computer(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import into Media Library", os.path.expanduser("~"), MEDIA_FILTER
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError:
            XPMessageBox.critical(self, "Windows Media Player", "Unable to read the selected file.")
            return
        ext = os.path.splitext(path)[1].lower()
        name = os.path.basename(path)
        if ext in VIDEO_EXTS:
            node = vfs_mod.vfs.create_video_file(vfs_mod.vfs.my_music_id, name, data, ext or ".mp4")
        else:
            node = vfs_mod.vfs.create_audio_file(vfs_mod.vfs.my_music_id, name, data, ext or ".mp3")
        self._load_playlist()
        self._play_track(node.id)

    def _about(self):
        XPMessageBox.information(
            self, "About Windows Media Player",
            "Windows Media Player\nVersion 10 (Build 5000.2000)\n\n"
            "© Microsoft Corporation. All rights reserved."
        )
