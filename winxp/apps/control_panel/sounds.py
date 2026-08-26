from __future__ import annotations

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout,
)

from ... import audio
from ...settings import SOUND_SCHEMES, settings
from ...window_manager import XPWindow

EVENTS = [("startup", "Windows Startup"), ("shutdown", "Windows Shutdown"), ("error", "Critical Stop")]


class SoundsWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Sounds and Audio Devices Properties", icon_key="volume",
                          size=QSize(420, 340), resizable=False)

        root = QVBoxLayout()
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        vol_title = QLabel("Volume")
        vol_title.setStyleSheet("font-weight: bold;")
        root.addWidget(vol_title)

        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("Low"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(settings.volume)
        self.slider.valueChanged.connect(settings.set_volume)
        vol_row.addWidget(self.slider, 1)
        vol_row.addWidget(QLabel("High"))
        root.addLayout(vol_row)

        self.mute_check = QCheckBox("Mute")
        self.mute_check.setChecked(settings.muted)
        self.mute_check.toggled.connect(settings.set_muted)
        root.addWidget(self.mute_check)

        scheme_title = QLabel("Sound Scheme")
        scheme_title.setStyleSheet("font-weight: bold; margin-top: 6px;")
        root.addWidget(scheme_title)

        self.scheme_combo = QComboBox()
        self.scheme_combo.addItems(list(SOUND_SCHEMES))
        self.scheme_combo.setCurrentText(settings.sound_scheme)
        self.scheme_combo.currentTextChanged.connect(settings.set_sound_scheme)
        root.addWidget(self.scheme_combo)

        events_title = QLabel("Program Events")
        events_title.setStyleSheet("font-weight: bold; margin-top: 6px;")
        root.addWidget(events_title)

        for key, label in EVENTS:
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            test_btn = QPushButton("Test")
            test_btn.setFixedWidth(60)
            test_btn.clicked.connect(lambda _, k=key: audio.sounds.play(k))
            row.addWidget(test_btn)
            root.addLayout(row)

        root.addStretch(1)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(self.close)
        btn_row.addWidget(close)
        root.addLayout(btn_row)

        self.set_content_layout(root)
