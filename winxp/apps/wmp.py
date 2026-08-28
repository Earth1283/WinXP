from __future__ import annotations

import os
import random

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMenuBar,
    QProgressBar, QPushButton, QSlider, QSplitter, QStackedLayout,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QToolButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .. import icons, theme, vfs as vfs_mod
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox
from .wmp_widgets import (
    EqualizerPanel, NavButton, PlaybackDisplay, SectionHeader, SLIDER_QSS,
    TransportButton, Visualizer,
)


FILE_ICON_BY_KIND = {vfs_mod.VIDEO: "video_file"}
PAGE_LABELS = {
    "now_playing": "Now Playing",
    "media_guide": "Media Guide",
    "copy_cd": "Copy from CD",
    "library": "Media Library",
    "radio": "Radio Tuner",
    "burn": "Copy to CD or Device",
    "skins": "Skin Chooser",
}


def format_time(milliseconds):
    total = max(0, milliseconds // 1000)
    minutes, seconds = divmod(total, 60)
    return f"{minutes}:{seconds:02d}"


class WindowsMediaPlayerWindow(XPWindow):
    def __init__(self, wm, node_id=None):
        super().__init__(wm, title="Windows Media Player", icon_key="wmp", size=QSize(920, 650))
        self.library_ids = []
        self.track_ids = []
        self.current_id = None
        self.seeking = False
        self.mini_mode = False
        self.normal_size = QSize(920, 650)
        self.current_page = "now_playing"
        self.nav_buttons = {}

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.7)
        self.player.setAudioOutput(self.audio_output)
        self.player.positionChanged.connect(self.on_position)
        self.player.durationChanged.connect(self.on_duration)
        self.player.playbackStateChanged.connect(self.on_state)
        self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.errorOccurred.connect(self.on_player_error)

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.menu_bar = self.build_menu()
        root.setMenuBar(self.menu_bar)
        self.brand_header = self.build_brand_header()
        root.addWidget(self.brand_header)

        self.workspace = QWidget()
        workspace_layout = QHBoxLayout(self.workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        self.nav_panel = self.build_navigation()
        workspace_layout.addWidget(self.nav_panel)
        self.pages = QStackedWidget()
        self.page_widgets = {
            "now_playing": self.build_now_playing_page(),
            "media_guide": self.build_media_guide_page(),
            "copy_cd": self.build_copy_cd_page(),
            "library": self.build_library_page(),
            "radio": self.build_radio_page(),
            "burn": self.build_burn_page(),
            "skins": self.build_skins_page(),
        }
        for page in self.page_widgets.values():
            self.pages.addWidget(page)
        workspace_layout.addWidget(self.pages, 1)
        root.addWidget(self.workspace, 1)

        self.equalizer = EqualizerPanel()
        self.equalizer.hide()
        root.addWidget(self.equalizer)
        self.transport = self.build_transport()
        root.addWidget(self.transport)
        self.set_content_layout(root)

        self.load_library()
        self.show_page("now_playing")
        if node_id:
            self.play_track(node_id)

    def closeEvent(self, event):
        self.player.stop()
        super().closeEvent(event)

    def action(self, menu, text, slot=None, shortcut=None, checkable=False, checked=False):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.addAction(action)
        action.setCheckable(checkable)
        action.setChecked(checked)
        action.triggered.connect(slot or (lambda: self.not_available(text)))
        menu.addAction(action)
        return action

    def build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)

        menu = bar.addMenu("&File")
        self.action(menu, "&Open...", lambda: self.show_page("library"), "Ctrl+O")
        self.action(menu, "Open &URL...")
        self.action(menu, "Add to Media &Library...", self.refresh_library, "F3")
        menu.addSeparator()
        self.action(menu, "&Close", self.close, "Alt+F4")

        menu = bar.addMenu("&View")
        self.full_mode_action = self.action(menu, "&Full Mode", self.show_full_mode,
                                            "Ctrl+1", checkable=True, checked=True)
        self.skin_mode_action = self.action(menu, "&Skin Mode", self.show_skin_mode,
                                            "Ctrl+2", checkable=True)
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        mode_group.addAction(self.full_mode_action)
        mode_group.addAction(self.skin_mode_action)
        menu.addSeparator()
        self.playlist_action = self.action(menu, "Now Playing &List", self.toggle_playlist,
                                           checkable=True, checked=True)
        self.equalizer_action = self.action(menu, "Graphic &Equalizer", self.toggle_equalizer,
                                            checkable=True)
        visualizations = menu.addMenu("&Visualizations")
        group = QActionGroup(self)
        for mode in Visualizer.MODES:
            item = self.action(visualizations, mode,
                               lambda _=False, name=mode: self.set_visualization(name),
                               checkable=True, checked=mode == "Bars")
            group.addAction(item)
        self.action(menu, "Video Si&ze")
        self.action(menu, "&Full Screen", self.toggle_maximize, "Alt+Enter")

        menu = bar.addMenu("&Play")
        self.action(menu, "&Play/Pause", self.toggle_play, "Ctrl+P")
        self.action(menu, "&Stop", self.player.stop, "Ctrl+S")
        menu.addSeparator()
        self.action(menu, "Pre&vious", self.play_previous, "Ctrl+B")
        self.action(menu, "&Next", self.play_next, "Ctrl+F")
        menu.addSeparator()
        self.shuffle_menu_action = self.action(menu, "Sh&uffle", self.sync_shuffle_from_menu,
                                               "Ctrl+H", checkable=True)
        self.repeat_menu_action = self.action(menu, "&Repeat", self.sync_repeat_from_menu,
                                              "Ctrl+T", checkable=True)
        menu.addSeparator()
        self.action(menu, "Volume &Up", lambda: self.change_volume(5), "F10")
        self.action(menu, "Volume &Down", lambda: self.change_volume(-5), "F9")
        self.action(menu, "&Mute", self.toggle_mute, "F8")

        menu = bar.addMenu("&Tools")
        self.action(menu, "Download &Plug-ins")
        self.action(menu, "Download &Skins", lambda: self.show_page("skins"))
        self.action(menu, "&Options...", self.show_options)

        menu = bar.addMenu("&Help")
        self.action(menu, "&Help Topics", self.show_help, "F1")
        self.action(menu, "Privacy &Statement")
        menu.addSeparator()
        self.action(menu, "Check for Player &Updates", self.check_updates)
        self.action(menu, "&About Windows Media Player", self.about)
        return bar

    def build_brand_header(self):
        panel = QWidget()
        panel.setFixedHeight(49)
        panel.setStyleSheet("background:#07182b;border-bottom:1px solid #466783")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 5, 10, 5)
        logo = QLabel()
        logo.setPixmap(icons.icon("wmp", 34).pixmap(34, 34))
        layout.addWidget(logo)
        wordmark = QLabel("Windows Media Player")
        wordmark.setStyleSheet("color:white;font-size:16px;font-weight:bold;background:transparent")
        layout.addWidget(wordmark)
        caption = QLabel("for Windows XP")
        caption.setStyleSheet("color:#7fa4c5;font-size:10px;background:transparent")
        layout.addWidget(caption, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addStretch(1)
        self.mode_label = QLabel("NOW PLAYING")
        self.mode_label.setStyleSheet("color:#91b5d4;font-size:10px;font-weight:bold;letter-spacing:1px")
        layout.addWidget(self.mode_label)
        return panel

    def build_navigation(self):
        panel = QWidget()
        panel.setFixedWidth(164)
        panel.setStyleSheet("background:#081b2f;border-right:1px solid #526e86")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(1)
        for key, label in PAGE_LABELS.items():
            button = NavButton(label, key)
            button.clicked.connect(lambda _=False, page=key: self.show_page(page))
            layout.addWidget(button)
            self.nav_buttons[key] = button
        layout.addStretch(1)
        branding = QLabel("windowsmedia.com")
        branding.setAlignment(Qt.AlignmentFlag.AlignCenter)
        branding.setStyleSheet("color:#597a96;font-size:9px;background:transparent;padding:8px")
        layout.addWidget(branding)
        return panel

    def build_now_playing_page(self):
        page = QWidget()
        page.setStyleSheet("background:#c9d6e1")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(SectionHeader("Now Playing", "Double-click the visualization to change its collection."))
        content = QHBoxLayout()
        content.setContentsMargins(8, 8, 8, 8)
        content.setSpacing(7)
        visual_panel = QWidget()
        visual_layout = QVBoxLayout(visual_panel)
        visual_layout.setContentsMargins(0, 0, 0, 0)
        self.visual_stack = QStackedLayout()
        self.visualizer = Visualizer()
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background:black")
        self.visual_stack.addWidget(self.visualizer)
        self.visual_stack.addWidget(self.video_widget)
        visual_container = QWidget()
        visual_container.setLayout(self.visual_stack)
        visual_layout.addWidget(visual_container, 1)
        self.track_detail = QLabel("Select an item from the Now Playing list.")
        self.track_detail.setStyleSheet("background:#e7eef4;border:1px solid #91a6b8;padding:5px;color:#294761")
        visual_layout.addWidget(self.track_detail)
        content.addWidget(visual_panel, 1)

        self.playlist_panel = QWidget()
        self.playlist_panel.setFixedWidth(232)
        self.playlist_panel.setStyleSheet("background:#e7eef4;border:1px solid #8298aa")
        playlist_layout = QVBoxLayout(self.playlist_panel)
        playlist_layout.setContentsMargins(5, 5, 5, 5)
        row = QHBoxLayout()
        title = QLabel("Now Playing List")
        title.setStyleSheet("font-weight:bold;color:#28445d;background:transparent")
        row.addWidget(title)
        row.addStretch(1)
        options = QToolButton()
        options.setText("▾")
        options.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        options_menu = QMenu(options)
        options_menu.addAction("Sort by Title", self.sort_playlist)
        options_menu.addAction("Clear List", self.clear_playlist)
        options.setMenu(options_menu)
        row.addWidget(options)
        playlist_layout.addLayout(row)
        self.playlist = QListWidget()
        self.playlist.setStyleSheet("background:white;border:1px solid #91a2af")
        self.playlist.itemDoubleClicked.connect(self.play_playlist_item)
        playlist_layout.addWidget(self.playlist, 1)
        content.addWidget(self.playlist_panel)
        layout.addLayout(content, 1)
        self.player.setVideoOutput(self.video_widget)
        return page

    def build_media_guide_page(self):
        page = QWidget()
        page.setStyleSheet("background:white")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SectionHeader("Media Guide", "Music, movies, and several business models from 2001."))
        guide = QTextBrowser()
        guide.setStyleSheet("background:white;border:0")
        guide.setHtml("""
        <body style='font-family:Tahoma;font-size:11px;margin:12px;color:#23394c'>
        <table width='100%' cellpadding='8' cellspacing='5'><tr valign='top'>
        <td width='65%' bgcolor='#e7f0f7'><font size='5' color='#174f7c'><b>WindowsMedia.com</b></font>
        <h2>Experience music and video on the Internet</h2>
        <p><b>Featured this week:</b> Artists explain why 64 Kbps is practically indistinguishable from being there.</p>
        <hr><h3>Music</h3><p><a href='#'>New releases</a> &nbsp; | &nbsp; Artist interviews &nbsp; | &nbsp; Music videos</p>
        <h3>Movies &amp; TV</h3><p>Watch trailers in a rectangle the size of a postage stamp. Buffering builds character.</p></td>
        <td width='35%' bgcolor='#d9e6f0'><h3>Today's Picks</h3>
        <p>• The Future of Broadband<br>• Codec Wars: No Survivors<br>• Behind the Music License</p>
        <h3>Sign In</h3><p>Use your Passport to personalize Media Guide and centralize one more decision.</p></td>
        </tr></table></body>
        """)
        layout.addWidget(guide, 1)
        return page

    def build_copy_cd_page(self):
        page = QWidget()
        page.setStyleSheet("background:#f3f6f8")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SectionHeader("Copy from CD", "Copy tracks from an audio CD to your Media Library."))
        body = QVBoxLayout()
        body.setContentsMargins(16, 18, 16, 16)
        drive = QLabel("Audio CD (D:) — No disc inserted")
        drive.setStyleSheet("font-size:14px;font-weight:bold;color:#35556f")
        body.addWidget(drive)
        table = QTableWidget(4, 4)
        table.setHorizontalHeaderLabels(("Copy", "Track", "Title", "Length"))
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for row, title in enumerate(("Track 01", "Track 02", "Track 03", "Enhanced CD Content")):
            check = QTableWidgetItem()
            check.setCheckState(Qt.CheckState.Checked if row < 3 else Qt.CheckState.Unchecked)
            table.setItem(row, 0, check)
            table.setItem(row, 1, QTableWidgetItem(str(row + 1)))
            table.setItem(row, 2, QTableWidgetItem(title))
            table.setItem(row, 3, QTableWidgetItem("--:--"))
        body.addWidget(table, 1)
        row = QHBoxLayout()
        quality = QComboBox()
        quality.addItems(("Windows Media Audio 64 Kbps", "Windows Media Audio 96 Kbps", "MP3 128 Kbps"))
        row.addWidget(QLabel("Copy settings:"))
        row.addWidget(quality)
        row.addStretch(1)
        copy = QPushButton("Copy Music")
        copy.clicked.connect(self.copy_cd)
        row.addWidget(copy)
        body.addLayout(row)
        layout.addLayout(body, 1)
        return page

    def build_library_page(self):
        page = QWidget()
        page.setStyleSheet("background:#edf2f6")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SectionHeader("Media Library", "Organize music, video, and playlists on this computer."))
        search_row = QHBoxLayout()
        search_row.setContentsMargins(8, 6, 8, 5)
        search_row.addWidget(QLabel("Search:"))
        self.library_search = QLineEdit()
        self.library_search.setPlaceholderText("Type a title, artist, or album")
        self.library_search.textChanged.connect(self.filter_library)
        search_row.addWidget(self.library_search, 1)
        layout.addLayout(search_row)
        splitter = QSplitter()
        self.library_tree = QTreeWidget()
        self.library_tree.setHeaderHidden(True)
        self.library_tree.setMinimumWidth(170)
        root = QTreeWidgetItem(["Media Library"])
        root.setExpanded(True)
        for label in ("All Music", "Artist", "Album", "Genre", "My Playlists", "Recently Played"):
            root.addChild(QTreeWidgetItem([label]))
        self.library_tree.addTopLevelItem(root)
        root.setExpanded(True)
        splitter.addWidget(self.library_tree)
        self.library_table = QTableWidget(0, 5)
        self.library_table.setHorizontalHeaderLabels(("Title", "Artist", "Album", "Genre", "Length"))
        self.library_table.verticalHeader().hide()
        self.library_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.library_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.library_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.library_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents)
        self.library_table.cellDoubleClicked.connect(self.play_library_row)
        splitter.addWidget(self.library_table)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)
        return page

    def build_radio_page(self):
        page = QWidget()
        page.setStyleSheet("background:#eef3f6")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SectionHeader("Radio Tuner", "Find Internet radio stations by genre or bandwidth."))
        content = QHBoxLayout()
        content.setContentsMargins(12, 12, 12, 12)
        genres = QListWidget()
        genres.setFixedWidth(145)
        genres.addItems(("Featured Stations", "Rock", "Jazz", "Classical", "News", "Talk", "56 Kbps or less"))
        genres.setCurrentRow(0)
        content.addWidget(genres)
        stations = QListWidget()
        for name, detail in (
            ("Radio Free Redmond", "Corporate rock — 64 Kbps"),
            ("Dial-Up Dreams", "Ambient modem tones — 32 Kbps"),
            ("The Codec", "Alternative — Windows Media Audio"),
            ("Public Radio Without Context", "News and talk — 20 Kbps"),
            ("Buffering...", "Experimental — bitrate unavailable"),
        ):
            item = QListWidgetItem(icons.icon("audio_file", 18), f"{name}\n{detail}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            stations.addItem(item)
        stations.itemDoubleClicked.connect(lambda item: self.play_station(item.data(Qt.ItemDataRole.UserRole)))
        content.addWidget(stations, 1)
        layout.addLayout(content, 1)
        return page

    def build_burn_page(self):
        page = QWidget()
        page.setStyleSheet("background:#eef3f6")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SectionHeader("Copy to CD or Device", "Build a list, choose a destination, and hope the disc is writable."))
        body = QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 12)
        row = QHBoxLayout()
        row.addWidget(QLabel("Items to copy"))
        row.addStretch(1)
        destination = QComboBox()
        destination.addItems(("CD Drive (D:)", "Portable Device (not connected)"))
        row.addWidget(QLabel("Items on device:"))
        row.addWidget(destination)
        body.addLayout(row)
        self.burn_list = QListWidget()
        body.addWidget(self.burn_list, 1)
        capacity = QProgressBar()
        capacity.setRange(0, 700)
        capacity.setValue(8)
        capacity.setFormat("8 MB used — 692 MB free")
        body.addWidget(capacity)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Status: No writable disc detected"))
        controls.addStretch(1)
        copy = QPushButton("Copy")
        copy.clicked.connect(self.copy_to_cd)
        controls.addWidget(copy)
        body.addLayout(controls)
        layout.addLayout(body, 1)
        return page

    def build_skins_page(self):
        page = QWidget()
        page.setStyleSheet("background:#e8eef3")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(SectionHeader("Skin Chooser", "Choose a different appearance for Windows Media Player."))
        body = QHBoxLayout()
        body.setContentsMargins(15, 15, 15, 15)
        self.skin_list = QListWidget()
        self.skin_list.addItems(("Windows XP", "Compact", "Corporate", "Headspace", "Miniplayer"))
        self.skin_list.setCurrentRow(0)
        body.addWidget(self.skin_list, 1)
        preview = QWidget()
        preview.setFixedWidth(285)
        preview.setStyleSheet("background:#06182b;border:2px solid #7790a5")
        preview_layout = QVBoxLayout(preview)
        title = QLabel("Windows Media Player")
        title.setStyleSheet("color:white;font-weight:bold")
        preview_layout.addWidget(title)
        fake_display = PlaybackDisplay()
        fake_display.set_values("Sample Music", "Paused", "0:42")
        preview_layout.addWidget(fake_display)
        buttons = QHBoxLayout()
        for glyph in ("prev", "play", "stop", "next"):
            buttons.addWidget(TransportButton(glyph, 25))
        buttons.addStretch(1)
        preview_layout.addLayout(buttons)
        preview_layout.addStretch(1)
        apply_button = QPushButton("Apply Skin")
        apply_button.clicked.connect(self.apply_skin)
        preview_layout.addWidget(apply_button, 0, Qt.AlignmentFlag.AlignRight)
        body.addWidget(preview)
        layout.addLayout(body, 1)
        return page

    def build_transport(self):
        deck = QWidget()
        deck.setFixedHeight(94)
        deck.setStyleSheet("background:#253b4f;border-top:1px solid #6e879b")
        root = QVBoxLayout(deck)
        root.setContentsMargins(8, 5, 8, 5)
        root.setSpacing(4)
        seek_row = QHBoxLayout()
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setStyleSheet(SLIDER_QSS)
        self.seek_slider.sliderPressed.connect(self.on_seek_pressed)
        self.seek_slider.sliderReleased.connect(self.on_seek_released)
        seek_row.addWidget(self.seek_slider, 1)
        self.duration_label = QLabel("0:00 / 0:00")
        self.duration_label.setStyleSheet("color:#dce6ee;background:transparent;font-size:10px")
        seek_row.addWidget(self.duration_label)
        root.addLayout(seek_row)
        controls = QHBoxLayout()
        self.playback_display = PlaybackDisplay()
        self.playback_display.setFixedWidth(260)
        controls.addWidget(self.playback_display)
        controls.addStretch(1)
        self.previous_button = TransportButton("prev")
        self.play_button = TransportButton("play", 36)
        self.stop_button = TransportButton("stop")
        self.next_button = TransportButton("next")
        self.previous_button.clicked.connect(self.play_previous)
        self.play_button.clicked.connect(self.toggle_play)
        self.stop_button.clicked.connect(self.player.stop)
        self.next_button.clicked.connect(self.play_next)
        for button in (self.previous_button, self.play_button, self.stop_button, self.next_button):
            controls.addWidget(button)
        controls.addSpacing(8)
        self.shuffle_button = self.mode_button("Shuffle")
        self.repeat_button = self.mode_button("Repeat")
        self.shuffle_button.toggled.connect(self.sync_shuffle_from_button)
        self.repeat_button.toggled.connect(self.sync_repeat_from_button)
        controls.addWidget(self.shuffle_button)
        controls.addWidget(self.repeat_button)
        controls.addStretch(1)
        self.mute_button = self.mode_button("Mute")
        self.mute_button.toggled.connect(self.audio_output.setMuted)
        controls.addWidget(self.mute_button)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setStyleSheet(SLIDER_QSS)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.setFixedWidth(90)
        self.volume_slider.valueChanged.connect(lambda value: self.audio_output.setVolume(value / 100))
        controls.addWidget(self.volume_slider)
        root.addLayout(controls)
        return deck

    def mode_button(self, text):
        button = QToolButton()
        button.setText(text)
        button.setCheckable(True)
        button.setStyleSheet("""
            QToolButton{color:#d7e5ef;background:#172a3b;border:1px solid #4d667b;padding:4px}
            QToolButton:checked{background:#d9851b;color:white;border-color:#f2b25e}
        """)
        return button

    def show_page(self, key):
        self.current_page = key
        self.pages.setCurrentWidget(self.page_widgets[key])
        self.nav_buttons[key].setChecked(True)
        self.mode_label.setText(PAGE_LABELS[key].upper())
        if key == "library":
            self.populate_library_table()
        elif key == "burn":
            self.populate_burn_list()

    def load_library(self):
        self.library_ids = []
        self.playlist.clear()
        children = sorted(vfs_mod.vfs.children_of(vfs_mod.vfs.my_music_id), key=lambda node: node.name.lower())
        for node in children:
            if node.kind not in (vfs_mod.AUDIO, vfs_mod.VIDEO):
                continue
            icon_key = FILE_ICON_BY_KIND.get(node.kind, "audio_file")
            item = QListWidgetItem(icons.icon(icon_key, 18), node.name)
            item.setData(Qt.ItemDataRole.UserRole, node.id)
            self.playlist.addItem(item)
            self.library_ids.append(node.id)
        self.track_ids = list(self.library_ids)
        self.populate_library_table()
        self.populate_burn_list()

    def refresh_library(self):
        self.load_library()
        self.playback_display.set_values(status="Media Library refreshed")

    def metadata(self, node):
        stem = os.path.splitext(node.name)[0]
        if stem.lower() == "chimes":
            return stem, "Microsoft", "Windows XP", "Soundtrack", "0:01"
        if stem.lower() == "sample music":
            return stem, "Unknown Artist", "Sample Music", "Other", "0:02"
        return stem, "Unknown Artist", "Unknown Album", "Unknown", "--:--"

    def populate_library_table(self):
        if not hasattr(self, "library_table"):
            return
        self.library_table.setRowCount(0)
        for node_id in self.library_ids:
            node = vfs_mod.vfs.get(node_id)
            if not node:
                continue
            row = self.library_table.rowCount()
            self.library_table.insertRow(row)
            for column, value in enumerate(self.metadata(node)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, node_id)
                self.library_table.setItem(row, column, item)

    def populate_burn_list(self):
        if not hasattr(self, "burn_list"):
            return
        self.burn_list.clear()
        for node_id in self.library_ids:
            node = vfs_mod.vfs.get(node_id)
            if node:
                self.burn_list.addItem(QListWidgetItem(icons.icon("audio_file", 18), node.name))

    def filter_library(self, text):
        query = text.strip().lower()
        for row in range(self.library_table.rowCount()):
            haystack = " ".join(self.library_table.item(row, column).text()
                                for column in range(self.library_table.columnCount())).lower()
            self.library_table.setRowHidden(row, query not in haystack)

    def play_library_row(self, row, column):
        item = self.library_table.item(row, 0)
        if item:
            self.play_track(item.data(Qt.ItemDataRole.UserRole))

    def play_playlist_item(self, item):
        self.play_track(item.data(Qt.ItemDataRole.UserRole))

    def play_track(self, node_id):
        node = vfs_mod.vfs.get(node_id)
        if not node:
            return
        path = vfs_mod.vfs.content_path(node_id)
        if not os.path.exists(path):
            XPMessageBox.critical(self, "Windows Media Player", f"Windows Media Player cannot find '{node.name}'.")
            return
        self.current_id = node_id
        if node_id not in self.track_ids:
            self.track_ids.append(node_id)
        self.visual_stack.setCurrentWidget(self.video_widget if node.kind == vfs_mod.VIDEO else self.visualizer)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()
        title, artist, album, genre, length = self.metadata(node)
        self.track_detail.setText(f"{title}  •  {artist}  •  {album}")
        self.playback_display.set_values(title=title, status=f"{artist} — {album}", time="0:00")
        self.setWindowTitle(f"{title} - Windows Media Player")
        self.select_playlist_id(node_id)
        self.show_page("now_playing")

    def select_playlist_id(self, node_id):
        for row in range(self.playlist.count()):
            item = self.playlist.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == node_id:
                self.playlist.setCurrentRow(row)
                return

    def toggle_play(self):
        state = self.player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.current_id:
            self.player.play()
        elif self.track_ids:
            self.play_track(self.track_ids[0])

    def play_next(self):
        if not self.track_ids:
            return
        if self.shuffle_button.isChecked():
            choices = [node_id for node_id in self.track_ids if node_id != self.current_id] or self.track_ids
            self.play_track(random.choice(choices))
            return
        if self.current_id not in self.track_ids:
            self.play_track(self.track_ids[0])
            return
        index = self.track_ids.index(self.current_id) + 1
        if index < len(self.track_ids):
            self.play_track(self.track_ids[index])
        elif self.repeat_button.isChecked():
            self.play_track(self.track_ids[0])
        else:
            self.player.stop()

    def play_previous(self):
        if not self.track_ids:
            return
        if self.player.position() > 3000 and self.current_id:
            self.player.setPosition(0)
            return
        if self.current_id not in self.track_ids:
            self.play_track(self.track_ids[0])
            return
        index = self.track_ids.index(self.current_id)
        if index > 0:
            self.play_track(self.track_ids[index - 1])
        elif self.repeat_button.isChecked():
            self.play_track(self.track_ids[-1])

    def on_state(self, state):
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        paused = state == QMediaPlayer.PlaybackState.PausedState
        self.visualizer.set_playing(playing)
        self.play_button.glyph = "pause" if playing else "play"
        self.play_button.update()
        status = "Playing" if playing else "Paused" if paused else "Stopped"
        self.playback_display.set_values(status=status)

    def on_position(self, position):
        if not self.seeking:
            self.seek_slider.setValue(position)
        duration = self.player.duration()
        self.duration_label.setText(f"{format_time(position)} / {format_time(duration)}")
        self.playback_display.set_values(time=format_time(position))

    def on_duration(self, duration):
        self.seek_slider.setRange(0, max(0, duration))

    def on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.play_next()
        elif status == QMediaPlayer.MediaStatus.BufferingMedia:
            self.playback_display.set_values(status="Buffering...")

    def on_player_error(self, error, message):
        if error != QMediaPlayer.Error.NoError:
            self.playback_display.set_values(status="Error")

    def on_seek_pressed(self):
        self.seeking = True

    def on_seek_released(self):
        self.player.setPosition(self.seek_slider.value())
        self.seeking = False

    def set_visualization(self, mode):
        self.visualizer.set_mode(mode)
        self.playback_display.set_values(status=f"Visualization: {mode}")

    def toggle_playlist(self, checked):
        self.playlist_panel.setVisible(checked)

    def toggle_equalizer(self, checked):
        self.equalizer.setVisible(checked and not self.mini_mode)

    def show_skin_mode(self, checked=True):
        if not checked and self.mini_mode:
            return
        self.mini_mode = True
        self.normal_size = self.size()
        self.menu_bar.hide()
        self.workspace.hide()
        self.equalizer.hide()
        self.mode_label.setText("SKIN MODE")
        self.resize(550, 176)
        self.full_mode_action.setChecked(False)
        self.skin_mode_action.setChecked(True)

    def show_full_mode(self, checked=True):
        if not checked and not self.mini_mode:
            return
        self.mini_mode = False
        self.menu_bar.show()
        self.workspace.show()
        self.equalizer.setVisible(self.equalizer_action.isChecked())
        self.mode_label.setText(PAGE_LABELS[self.current_page].upper())
        self.resize(self.normal_size)
        self.full_mode_action.setChecked(True)
        self.skin_mode_action.setChecked(False)

    def apply_skin(self):
        selected = self.skin_list.currentItem().text()
        if selected in ("Compact", "Miniplayer"):
            self.show_skin_mode()
        else:
            self.playback_display.set_values(status=f"Skin applied: {selected}")

    def sync_shuffle_from_menu(self, checked):
        self.shuffle_button.setChecked(checked)

    def sync_shuffle_from_button(self, checked):
        self.shuffle_menu_action.setChecked(checked)

    def sync_repeat_from_menu(self, checked):
        self.repeat_button.setChecked(checked)

    def sync_repeat_from_button(self, checked):
        self.repeat_menu_action.setChecked(checked)

    def change_volume(self, delta):
        self.volume_slider.setValue(max(0, min(100, self.volume_slider.value() + delta)))

    def toggle_mute(self):
        self.mute_button.setChecked(not self.mute_button.isChecked())

    def sort_playlist(self):
        self.playlist.sortItems()
        self.track_ids = [
            self.playlist.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.playlist.count())
        ]

    def clear_playlist(self):
        self.playlist.clear()
        self.track_ids = []
        self.playback_display.set_values(status="Now Playing list cleared")

    def play_station(self, name):
        self.playback_display.set_values(title=name, status="Connecting to station...", time="0:00")
        XPMessageBox.information(
            self, "Windows Media Player",
            f"Windows Media Player cannot connect to '{name}'.\n\n"
            "The station requires a broadband connection, a Passport, and confidence in Internet radio.")

    def copy_cd(self):
        XPMessageBox.information(
            self, "Copy from CD",
            "Windows Media Player cannot copy the tracks because no audio CD is in drive D:.\n\n"
            "The drive made a noise anyway, to remain involved.")

    def copy_to_cd(self):
        XPMessageBox.information(
            self, "Copy to CD or Device",
            "No writable CD or portable device was detected.\n\n"
            "The blank disc on your desk has not been detected because it is on your desk.")

    def show_options(self):
        XPMessageBox.information(
            self, "Options",
            "Network buffering: 5 seconds\nPrivacy: Acquire licenses automatically\n"
            "Player ID: Sent to content providers with tremendous optimism")

    def show_help(self):
        XPMessageBox.information(
            self, "Windows Media Player Help",
            "Choose a topic:\n\nPlaying media\nOrganizing your library\nCopying CDs\n"
            "Explaining codecs to a relative\n\nTopic selection is not installed.")

    def check_updates(self):
        XPMessageBox.information(
            self, "Windows Media Player",
            "You are running the newest version available in October 2001.\n\n"
            "Time has been asked not to interfere.")

    def about(self):
        XPMessageBox.information(
            self, "About Windows Media Player",
            "Windows Media Player for Windows XP\n"
            "Version 8.00.00.4487\n\n"
            "© 1992-2001 Microsoft Corporation. All rights reserved.\n"
            "Portions of this product are protected by codec licensing agreements nobody has read.")

    def not_available(self, label):
        clean = label.replace("&", "").rstrip(".")
        XPMessageBox.information(
            self, "Windows Media Player",
            f"Windows Media Player cannot complete {clean}.\n\n"
            "The required component is not installed, or is installed but prefers not to discuss it.")
