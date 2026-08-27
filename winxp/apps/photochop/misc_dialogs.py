"""The rest of the dialogs: Preferences, Color Settings, Save for Web,
Print with Preview, Page Setup, File Info, Histogram, Preset Manager, Help.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QPlainTextEdit, QPushButton, QRadioButton, QSlider,
    QSpinBox, QStackedWidget, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from ... import theme
from ...xp_dialog import XPMessageBox
from . import imageops as ops
from .adjust_dialogs import HistogramView
from .dialogs import PCDialog, PreviewBox, SliderRow, _lbl, _size_text, _spin, group_box


# ------------------------------------------------------------ preferences --

PREF_PAGES = ["General", "File Handling", "Display & Cursors",
              "Transparency & Gamut", "Units & Rulers", "Guides, Grid & Slices",
              "Plug-Ins & Scratch Disks", "Memory & Image Cache"]


class PreferencesDialog(PCDialog):
    def __init__(self, parent, page="General"):
        super().__init__(parent, "Preferences")
        self.win = parent
        row = QHBoxLayout()
        self.page_combo = QComboBox()
        self.page_combo.addItems(PREF_PAGES)
        self.page_combo.setFixedWidth(220)
        row.addWidget(self.page_combo)
        row.addStretch(1)
        self.content.addLayout(row)

        self.stack = QStackedWidget()
        for name in PREF_PAGES:
            self.stack.addWidget(getattr(self, "_page_" + _slug(name))())
        self.content.addWidget(self.stack, 1)
        self.page_combo.currentIndexChanged.connect(self.stack.setCurrentIndex)
        if page in PREF_PAGES:
            self.page_combo.setCurrentIndex(PREF_PAGES.index(page))

        self.add_ok_cancel()
        self.add_button("Prev", lambda: self._step(-1))
        self.add_button("Next", lambda: self._step(1))
        self.finish_side()
        self.setFixedWidth(520)

    def _step(self, delta):
        idx = (self.page_combo.currentIndex() + delta) % len(PREF_PAGES)
        self.page_combo.setCurrentIndex(idx)

    def _page_general(self):
        panel, box = _page()
        grid = QGridLayout()
        for r, (label, choices) in enumerate((
                ("Color Picker:", ("Adobo", "Windows")),
                ("Interpolation:", ("Nearest Neighbor (faster)", "Bilinear",
                                    "Bicubic (better)")),
                ("Redo Key:", ("Ctrl+Z (Toggles Undo/Redo)",
                               "Ctrl+Shift+Z (Toggles Undo/Redo)",
                               "Ctrl+Y (Repeat Redo)")),
                ("History States:", ("1", "5", "20", "50", "100")))):
            grid.addWidget(_lbl(label), r, 0)
            combo = QComboBox()
            combo.addItems(choices)
            combo.setCurrentIndex(len(choices) - 1 if r in (1, 3) else 0)
            if r == 3:
                combo.setCurrentText("20")
                combo.currentTextChanged.connect(self._history_states)
            grid.addWidget(combo, r, 1)
        box.addLayout(grid)
        frame, opts = group_box("Options")
        for label, checked in (("Export Clipboard", True), ("Show Tool Tips", True),
                               ("Zoom Resizes Windows", False),
                               ("Auto-update open documents", False),
                               ("Show Asian Text Options", False),
                               ("Beep When Done", False),
                               ("Dynamic Color Sliders", True),
                               ("Save Palette Locations", True),
                               ("Show Font Names in English", True),
                               ("Use Shift Key for Tool Switch", True),
                               ("Use Smart Quotes", True)):
            cb = QCheckBox(label)
            cb.setChecked(checked)
            cb.setStyleSheet("background: transparent;")
            opts.addWidget(cb)
        box.addWidget(frame)
        reset = QPushButton("Reset All Warning Dialogs")
        reset.clicked.connect(lambda: XPMessageBox.information(
            self, "PhotoChop", "All warning dialogs will now be shown again. "
                               "All of them. Constantly."))
        box.addWidget(reset)
        box.addStretch(1)
        return panel

    def _history_states(self, text):
        try:
            self.win.doc.history.max_states = int(text)
        except ValueError:
            pass

    def _page_file_handling(self):
        panel, box = _page()
        frame, opts = group_box("File Saving Options")
        row = QHBoxLayout()
        row.addWidget(_lbl("Image Previews:"))
        combo = QComboBox()
        combo.addItems(["Always Save", "Never Save", "Ask When Saving"])
        row.addWidget(combo, 1)
        opts.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("File Extension:"))
        ext = QComboBox()
        ext.addItems(["Use Lower Case", "Use Upper Case"])
        row2.addWidget(ext, 1)
        opts.addLayout(row2)
        box.addWidget(frame)
        frame2, opts2 = group_box("File Compatibility")
        for label, checked in (("Ignore EXIF sRGB tag", False),
                               ("Ask Before Saving Layered TIFF Files", True),
                               ("Always Maximize Compatibility for Photoshop (PSD) Files",
                                True),
                               ("Enable Workgroup Functionality", False)):
            cb = QCheckBox(label)
            cb.setChecked(checked)
            cb.setStyleSheet("background: transparent;")
            opts2.addWidget(cb)
        box.addWidget(frame2)
        row3 = QHBoxLayout()
        row3.addWidget(_lbl("Recent file list contains:"))
        row3.addWidget(_spin(0, 30, 10, " files"))
        row3.addStretch(1)
        box.addLayout(row3)
        box.addStretch(1)
        return panel

    def _page_display_cursors(self):
        panel, box = _page()
        frame, opts = group_box("Display")
        for label, checked in (("Color Channels in Color", False),
                               ("Use Diffusion Dither", False),
                               ("Use Pixel Doubling", False)):
            cb = QCheckBox(label)
            cb.setChecked(checked)
            cb.setStyleSheet("background: transparent;")
            opts.addWidget(cb)
        box.addWidget(frame)
        frame2, opts2 = group_box("Painting Cursors")
        self.cursor_group = QButtonGroup(self)
        for i, label in enumerate(("Standard", "Precise", "Brush Size")):
            rb = QRadioButton(label)
            rb.setChecked(i == 2)
            rb.setStyleSheet("background: transparent;")
            self.cursor_group.addButton(rb, i)
            opts2.addWidget(rb)
        box.addWidget(frame2)
        frame3, opts3 = group_box("Other Cursors")
        for i, label in enumerate(("Standard", "Precise")):
            rb = QRadioButton(label)
            rb.setChecked(i == 0)
            rb.setStyleSheet("background: transparent;")
            opts3.addWidget(rb)
        box.addWidget(frame3)
        box.addStretch(1)
        return panel

    def _page_transparency_gamut(self):
        panel, box = _page()
        frame, opts = group_box("Transparency Settings")
        row = QHBoxLayout()
        row.addWidget(_lbl("Grid Size:"))
        size = QComboBox()
        size.addItems(["None", "Small", "Medium", "Large"])
        size.setCurrentText("Medium")
        row.addWidget(size, 1)
        opts.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Grid Colors:"))
        colours = QComboBox()
        colours.addItems(["Light", "Medium", "Dark", "Custom"])
        row2.addWidget(colours, 1)
        opts.addLayout(row2)
        box.addWidget(frame)
        frame2, opts2 = group_box("Gamut Warning")
        row3 = QHBoxLayout()
        row3.addWidget(_lbl("Opacity:"))
        row3.addWidget(_spin(0, 100, 100, "%"))
        row3.addStretch(1)
        opts2.addLayout(row3)
        box.addWidget(frame2)
        box.addStretch(1)
        return panel

    def _page_units_rulers(self):
        panel, box = _page()
        frame, opts = group_box("Units")
        for label, choices, default in (
                ("Rulers:", ("pixels", "inches", "cm", "mm", "points", "picas",
                             "percent"), "pixels"),
                ("Type:", ("pixels", "points", "mm"), "points")):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            combo = QComboBox()
            combo.addItems(choices)
            combo.setCurrentText(default)
            row.addWidget(combo, 1)
            opts.addLayout(row)
        box.addWidget(frame)
        frame2, opts2 = group_box("Column Size")
        for label, value, suffix in (("Width:", 180, " points"),
                                     ("Gutter:", 12, " points")):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            row.addWidget(_spin(1, 1000, value, suffix))
            row.addStretch(1)
            opts2.addLayout(row)
        box.addWidget(frame2)
        frame3, opts3 = group_box("New Document Preset Resolutions")
        for label, value in (("Print Resolution:", 300), ("Screen Resolution:", 72)):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            row.addWidget(_spin(1, 2400, value, " pixels/inch"))
            row.addStretch(1)
            opts3.addLayout(row)
        box.addWidget(frame3)
        box.addStretch(1)
        return panel

    def _page_guides_grid_slices(self):
        panel, box = _page()
        frame, opts = group_box("Guides")
        for label, choices in (("Color:", ("Light Blue", "Cyan", "Magenta", "Custom")),
                               ("Style:", ("Lines", "Dashed Lines"))):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            combo = QComboBox()
            combo.addItems(choices)
            row.addWidget(combo, 1)
            opts.addLayout(row)
        box.addWidget(frame)
        frame2, opts2 = group_box("Grid")
        row = QHBoxLayout()
        row.addWidget(_lbl("Gridline every:"))
        row.addWidget(_spin(1, 1000, 25, " pixels"))
        row.addStretch(1)
        opts2.addLayout(row)
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Subdivisions:"))
        row2.addWidget(_spin(1, 100, 4, ""))
        row2.addStretch(1)
        opts2.addLayout(row2)
        box.addWidget(frame2)
        frame3, opts3 = group_box("Slices")
        show = QCheckBox("Show Slice Numbers")
        show.setChecked(True)
        show.setStyleSheet("background: transparent;")
        opts3.addWidget(show)
        box.addWidget(frame3)
        box.addStretch(1)
        return panel

    def _page_plug_ins_scratch_disks(self):
        panel, box = _page()
        frame, opts = group_box("Additional Plug-Ins Directory")
        row = QHBoxLayout()
        row.addWidget(QLineEdit("C:\\Program Files\\Adobo\\PhotoChop 7.0\\Plug-Ins"))
        row.addWidget(QPushButton("Choose..."))
        opts.addLayout(row)
        box.addWidget(frame)
        frame2, opts2 = group_box("Scratch Disks")
        for i, (label, value) in enumerate((("First:", "C:\\  Startup  (39.4M free)"),
                                            ("Second:", "None"),
                                            ("Third:", "None"),
                                            ("Fourth:", "None"))):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            combo = QComboBox()
            combo.addItems([value, "None", "C:\\", "A:\\  (probably empty)"])
            row.addWidget(combo, 1)
            opts2.addLayout(row)
        note = QLabel("Scratch disks will remain in use until you quit PhotoChop, and "
                      "for some time after that.")
        note.setWordWrap(True)
        note.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        opts2.addWidget(note)
        box.addWidget(frame2)
        box.addStretch(1)
        return panel

    def _page_memory_image_cache(self):
        panel, box = _page()
        frame, opts = group_box("Cache Settings")
        row = QHBoxLayout()
        row.addWidget(_lbl("Cache Levels:"))
        row.addWidget(_spin(1, 8, 4, ""))
        row.addStretch(1)
        opts.addLayout(row)
        cb = QCheckBox("Use cache for histograms")
        cb.setChecked(True)
        cb.setStyleSheet("background: transparent;")
        opts.addWidget(cb)
        box.addWidget(frame)
        frame2, opts2 = group_box("Memory Usage")
        opts2.addWidget(_lbl("Available RAM:  256MB"))
        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Maximum Used by PhotoChop:"))
        row2.addWidget(_spin(5, 100, 50, "%"))
        row2.addStretch(1)
        opts2.addLayout(row2)
        note = QLabel("Changes will take effect the next time you start PhotoChop, "
                      "which is sooner than you think.")
        note.setWordWrap(True)
        note.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        opts2.addWidget(note)
        box.addWidget(frame2)
        box.addStretch(1)
        return panel


def _page():
    panel = QWidget()
    box = QVBoxLayout(panel)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(8)
    return panel, box


def _slug(name):
    return (name.lower().replace(" & ", "_").replace(" ", "_")
            .replace("-", "_").replace(",", ""))


# --------------------------------------------------------- color settings --

class ColorSettingsDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "Color Settings")
        row = QHBoxLayout()
        row.addWidget(_lbl("Settings:"))
        combo = QComboBox()
        combo.addItems(["Custom", "Color Management Off", "ColorSync Workflow",
                        "Emulate Photoshop 4", "Europe Prepress Defaults",
                        "Japan Prepress Defaults", "Photoshop 5 Default Spaces",
                        "U.S. Prepress Defaults", "Web Graphics Defaults"])
        row.addWidget(combo, 1)
        self.content.addLayout(row)

        frame, box = group_box("Working Spaces")
        for label, choices in (("RGB:", ("sRGB IEC61966-2.1", "Adobo RGB (1998)",
                                         "Apple RGB", "ColorMatch RGB")),
                               ("CMYK:", ("U.S. Web Coated (SWOP) v2",
                                          "Euroscale Coated v2", "Japan Standard v2")),
                               ("Gray:", ("Dot Gain 20%", "Gray Gamma 2.2")),
                               ("Spot:", ("Dot Gain 20%",))):
            r = QHBoxLayout()
            r.addWidget(_lbl(label))
            c = QComboBox()
            c.addItems(choices)
            r.addWidget(c, 1)
            box.addLayout(r)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Color Management Policies")
        for label in ("RGB:", "CMYK:", "Gray:"):
            r = QHBoxLayout()
            r.addWidget(_lbl(label))
            c = QComboBox()
            c.addItems(["Preserve Embedded Profiles", "Convert to Working RGB", "Off"])
            r.addWidget(c, 1)
            box2.addLayout(r)
        for label in ("Profile Mismatches: Ask When Opening",
                      "Profile Mismatches: Ask When Pasting",
                      "Missing Profiles: Ask When Opening"):
            cb = QCheckBox(label)
            cb.setChecked(True)
            cb.setStyleSheet("background: transparent;")
            box2.addWidget(cb)
        self.content.addWidget(frame2)

        note = QLabel("Description: hover over any item to read a paragraph that will "
                      "not help.")
        note.setWordWrap(True)
        note.setStyleSheet("background: transparent; color: #555; font-size: 10px;")
        self.content.addWidget(note)

        self.add_ok_cancel()
        self.add_button("Load...")
        self.add_button("Save...")
        self.finish_side()
        self.setFixedWidth(500)


# ---------------------------------------------------------- save for web ---

class SaveForWebDialog(PCDialog):
    def __init__(self, parent, image: QImage):
        super().__init__(parent, "Save For Web")
        self.source = image
        tabs = QHBoxLayout()
        for label in ("Original", "Optimized", "2-Up", "4-Up"):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setChecked(label == "2-Up")
            b.setFixedHeight(20)
            tabs.addWidget(b)
        tabs.addStretch(1)
        self.content.addLayout(tabs)

        panes = QHBoxLayout()
        panes.setSpacing(6)
        self.left = _WebPane("Original", image, None)
        self.right = _WebPane("Optimized", image, self._optimize)
        panes.addWidget(self.left)
        panes.addWidget(self.right)
        self.content.addLayout(panes)

        settings = QHBoxLayout()
        settings.addWidget(_lbl("Settings:"))
        self.preset = QComboBox()
        self.preset.addItems(["[Unnamed]", "GIF 128 Dithered", "GIF 128 No Dither",
                              "GIF 32 Dithered", "JPEG Low", "JPEG Medium", "JPEG High",
                              "PNG-8 128 Dithered", "PNG-24"])
        self.preset.setCurrentText("JPEG Medium")
        self.preset.currentTextChanged.connect(lambda _: self._refresh())
        settings.addWidget(self.preset, 1)
        self.content.addLayout(settings)

        row = QHBoxLayout()
        row.addWidget(_lbl("Quality:"))
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(0, 100)
        self.quality.setValue(60)
        self.quality.valueChanged.connect(lambda _: self._refresh())
        row.addWidget(self.quality, 1)
        self.content.addLayout(row)

        self.add_ok_cancel("Save")
        self.add_button("Done", self.accept)
        self.finish_side()
        self._refresh()

    def _optimize(self):
        quality = self.quality.value()
        preset = self.preset.currentText()
        img = self.source
        if preset.startswith("GIF") or preset.startswith("PNG-8"):
            colours = 128 if "128" in preset else 32
            img = ops.posterize(img, max(2, int(colours ** (1 / 3))))
            if "Dithered" in preset:
                img = ops.add_noise(img, 4, monochromatic=True)
        else:
            blocks = max(1, int((100 - quality) / 12))
            if blocks > 1:
                img = ops.mosaic(img, blocks)
                img = ops.gaussian_blur(img, blocks / 3.0)
        return img

    def _refresh(self):
        optimized = self._optimize()
        self.right.set_image(optimized)
        kb = self.source.width() * self.source.height() * 3 / 1024
        quality = max(1, self.quality.value())
        est = kb * (0.02 + quality / 900.0)
        self.left.set_caption(f"Original\n{_size_text(kb)}")
        self.right.set_caption(
            f"{self.preset.currentText()}\n{_size_text(est)}   "
            f"{max(1, int(est / 4.5))} sec @ 56.6 Kbps")


class _WebPane(QWidget):
    def __init__(self, title, image, optimizer):
        super().__init__()
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
        self.view = QLabel()
        self.view.setFixedSize(190, 150)
        self.view.setStyleSheet("border: 1px solid #808080; background: white;")
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.view)
        self.caption = QLabel(title)
        self.caption.setStyleSheet("background: transparent; font-size: 10px;")
        box.addWidget(self.caption)
        self.set_image(image)

    def set_image(self, img):
        self.view.setPixmap(QPixmap.fromImage(img.scaled(
            188, 148, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)))

    def set_caption(self, text):
        self.caption.setText(text)


# ----------------------------------------------------------------- print ---

class PrintDialog(PCDialog):
    def __init__(self, parent, image: QImage):
        super().__init__(parent, "Print")
        self.image = image
        row = QHBoxLayout()
        self.preview = _PrintPreview(image)
        row.addWidget(self.preview)

        col = QVBoxLayout()
        frame, box = group_box("Position")
        grid = QGridLayout()
        for r, label in enumerate(("Top:", "Left:")):
            grid.addWidget(_lbl(label), r, 0)
            grid.addWidget(_spin(0, 100, 1, " inches"), r, 1)
        box.addLayout(grid)
        centre = QCheckBox("Center Image")
        centre.setChecked(True)
        centre.setStyleSheet("background: transparent;")
        box.addWidget(centre)
        col.addWidget(frame)

        frame2, box2 = group_box("Scaled Print Size")
        grid2 = QGridLayout()
        for r, (label, value, suffix) in enumerate((("Scale:", 100, "%"),
                                                    ("Height:", 5, " inches"),
                                                    ("Width:", 7, " inches"))):
            grid2.addWidget(_lbl(label), r, 0)
            grid2.addWidget(_spin(1, 1000, value, suffix), r, 1)
        box2.addLayout(grid2)
        fit = QCheckBox("Scale to Fit Media")
        fit.setStyleSheet("background: transparent;")
        box2.addWidget(fit)
        col.addWidget(frame2)

        show = QCheckBox("Show More Options")
        show.setStyleSheet("background: transparent;")
        col.addWidget(show)
        col.addStretch(1)
        row.addLayout(col, 1)
        self.content.addLayout(row)

        self.add_button("Print...", self._print, default=True)
        self.add_button("Cancel", self.reject)
        self.add_button("Done", self.accept)
        self.add_button("Page Setup...", lambda: PageSetupDialog(self).exec())
        self.finish_side()

    def _print(self):
        XPMessageBox.critical(
            self, "PhotoChop",
            "Could not print because no printer is installed.\n\n"
            "Windows will now offer to install a printer and then not do that.")


class _PrintPreview(QWidget):
    def __init__(self, image):
        super().__init__()
        self.image = image
        self.setFixedSize(180, 232)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#c0c0c0"))
        page = QRect(10, 10, self.width() - 20, self.height() - 20)
        p.fillRect(page, QColor("white"))
        p.setPen(QPen(QColor("#606060"), 1))
        p.drawRect(page)
        scaled = self.image.scaled(page.width() - 24, page.height() - 24,
                                   Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        p.drawImage(page.center().x() - scaled.width() // 2,
                    page.center().y() - scaled.height() // 2, scaled)
        p.end()


class PageSetupDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "Page Setup")
        frame, box = group_box("Paper")
        for label, choices in (("Size:", ("Letter", "Legal", "A4", "A3", "Executive")),
                               ("Source:", ("Automatically Select", "Manual Feed",
                                            "Tray 1", "Tray 2 (does not exist)"))):
            row = QHBoxLayout()
            row.addWidget(_lbl(label))
            combo = QComboBox()
            combo.addItems(choices)
            row.addWidget(combo, 1)
            box.addLayout(row)
        self.content.addWidget(frame)

        frame2, box2 = group_box("Orientation")
        row = QHBoxLayout()
        for i, label in enumerate(("Portrait", "Landscape")):
            rb = QRadioButton(label)
            rb.setChecked(i == 0)
            rb.setStyleSheet("background: transparent;")
            row.addWidget(rb)
        box2.addLayout(row)
        self.content.addWidget(frame2)

        frame3, box3 = group_box("Margins (inches)")
        grid = QGridLayout()
        for i, label in enumerate(("Left:", "Right:", "Top:", "Bottom:")):
            grid.addWidget(_lbl(label), i // 2, (i % 2) * 2)
            grid.addWidget(_spin(0, 10, 1, '"'), i // 2, (i % 2) * 2 + 1)
        box3.addLayout(grid)
        self.content.addWidget(frame3)

        self.add_ok_cancel()
        self.add_button("Printer...", lambda: XPMessageBox.warning(
            self, "Page Setup", "No printers are installed."))
        self.finish_side()


# ------------------------------------------------------------- file info ---

class FileInfoDialog(PCDialog):
    SECTIONS = ["General", "Keywords", "Categories", "Credits", "Origin",
                "History", "Advanced"]

    def __init__(self, parent, doc):
        super().__init__(parent, "File Info")
        self.doc = doc
        row = QHBoxLayout()
        row.addWidget(_lbl("Section:"))
        self.section = QComboBox()
        self.section.addItems(self.SECTIONS)
        row.addWidget(self.section, 1)
        self.content.addLayout(row)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._general())
        for name in self.SECTIONS[1:]:
            self.stack.addWidget(self._simple(name))
        self.content.addWidget(self.stack, 1)
        self.section.currentIndexChanged.connect(self.stack.setCurrentIndex)

        self.add_ok_cancel()
        self.add_button("Load...")
        self.add_button("Save...")
        self.add_button("Append...")
        self.finish_side()
        self.setFixedWidth(460)

    def _general(self):
        panel, box = _page()
        grid = QGridLayout()
        fields = (("Title:", self.doc.name), ("Author:", ""),
                  ("Author's Position:", ""), ("Description:", ""),
                  ("Description Writer:", ""), ("Copyright Notice:", ""),
                  ("Copyright Info URL:", ""))
        for r, (label, value) in enumerate(fields):
            grid.addWidget(_lbl(label), r, 0)
            grid.addWidget(QLineEdit(value), r, 1)
        box.addLayout(grid)
        row = QHBoxLayout()
        row.addWidget(_lbl("Copyright Status:"))
        combo = QComboBox()
        combo.addItems(["Unmarked", "Copyrighted Work", "Public Domain"])
        row.addWidget(combo, 1)
        box.addLayout(row)
        box.addStretch(1)
        return panel

    def _simple(self, name):
        panel, box = _page()
        box.addWidget(_lbl(name))
        edit = QPlainTextEdit()
        edit.setFixedHeight(180)
        if name == "History":
            edit.setPlainText("\n".join(
                f"{i + 1}. {state.name}"
                for i, state in enumerate(self.doc.history.states)))
            edit.setReadOnly(True)
        box.addWidget(edit)
        box.addStretch(1)
        return panel


# ------------------------------------------------------------- histogram ---

class HistogramDialog(PCDialog):
    def __init__(self, parent, image: QImage):
        super().__init__(parent, "Histogram")
        self.image = image
        row = QHBoxLayout()
        row.addWidget(_lbl("Channel:"))
        self.channel = QComboBox()
        self.channel.addItems(["Luminosity", "Red", "Green", "Blue", "Colors"])
        self.channel.currentIndexChanged.connect(self._refresh)
        row.addWidget(self.channel, 1)
        self.content.addLayout(row)

        self.view = HistogramView(130)
        self.content.addWidget(self.view)
        self.stats = QLabel()
        self.stats.setStyleSheet("background: transparent; font-size: 10px;")
        self.content.addWidget(self.stats)

        self.add_button("OK", self.accept, default=True)
        self.finish_side()
        self._hists = ops.histogram(image)
        self._refresh()

    def _refresh(self):
        idx = self.channel.currentIndex()
        hist = self._hists[min(idx, 3)]
        tint = ("#404040", "#c02020", "#20a020", "#2040c0", "#404040")[idx]
        self.view.set_hist(hist, tint)
        total = sum(hist) or 1
        mean = sum(i * v for i, v in enumerate(hist)) / total
        variance = sum((i - mean) ** 2 * v for i, v in enumerate(hist)) / total
        cumulative = 0
        median = 0
        for i, v in enumerate(hist):
            cumulative += v
            if cumulative >= total / 2:
                median = i
                break
        self.stats.setText(
            f"Mean: {mean:.2f}          Level:\n"
            f"Std Dev: {math.sqrt(variance):.2f}       Count:\n"
            f"Median: {median}          Percentile:\n"
            f"Pixels: {total}       Cache Level: 1")


# ------------------------------------------------------- preset manager ----

class PresetManagerDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "Preset Manager")
        row = QHBoxLayout()
        row.addWidget(_lbl("Preset Type:"))
        self.kind = QComboBox()
        self.kind.addItems(["Brushes", "Swatches", "Gradients", "Styles", "Patterns",
                            "Contours", "Custom Shapes", "Tools"])
        self.kind.currentTextChanged.connect(self._refresh)
        row.addWidget(self.kind, 1)
        self.content.addLayout(row)
        self.list = QListWidget()
        self.list.setFixedHeight(200)
        self.content.addWidget(self.list)
        self.add_button("Done", self.accept, default=True)
        self.add_button("Load...")
        self.add_button("Save Set...")
        self.add_button("Rename...")
        self.add_button("Delete")
        self.finish_side()
        self._refresh()

    def _refresh(self):
        from . import brushes as be
        from .canvas import CUSTOM_SHAPES, GRADIENT_PRESETS
        from .palettes import PRESET_STYLES, SWATCH_COLORS
        kind = self.kind.currentText()
        items = {
            "Brushes": [name for name, _, _ in be.BRUSH_PRESETS],
            "Swatches": SWATCH_COLORS,
            "Gradients": list(GRADIENT_PRESETS),
            "Styles": [name for name, _ in PRESET_STYLES],
            "Patterns": ["Checkerboard", "Diagonal Lines", "Bubbles", "Woven"],
            "Contours": ["Linear", "Cone", "Gaussian", "Half Round", "Ring",
                         "Rolling Slope Descending", "Sawtooth 1", "Shallow Slope"],
            "Custom Shapes": CUSTOM_SHAPES,
            "Tools": ["Crop 4 x 6", "Magnetic Lasso 24 pixels", "Type Tahoma 24 pt"],
        }.get(kind, [])
        self.list.clear()
        self.list.addItems(items)


# ------------------------------------------------------------------ help ---

HELP_HTML = """
<h2>PhotoChop 7.0 Help</h2>
<p><b>Contents</b></p>
<ul>
<li>Getting Started
  <ul><li>Installing PhotoChop &mdash; done, apparently</li>
      <li>Activating PhotoChop &mdash; see the dialog you already dismissed</li></ul></li>
<li>Working with Layers
  <ul><li>Creating a layer</li>
      <li>Why the Background layer is locked, and what that says about you</li>
      <li>Merging layers you will need again later</li></ul></li>
<li>Making Selections
  <ul><li>Marquee, Lasso, Magic Wand</li>
      <li>Feathering, and why 250 pixels was a mistake</li></ul></li>
<li>Using Filters
  <ul><li>Applying a filter</li>
      <li>Undoing a filter (see: History palette, 20 states)</li>
      <li>Filters that were only ever used once, in 1998, by everyone</li></ul></li>
<li>Troubleshooting
  <ul><li>"Could not complete your request because of a program error"</li>
      <li>"Scratch disks are full"</li>
      <li>"The file could not be opened because it is not the right kind of file"</li></ul></li>
</ul>
<p><i>Search returned 0 results. Try fewer words. Try different words. Try again
later. Try a book.</i></p>
"""


class HelpDialog(PCDialog):
    def __init__(self, parent):
        super().__init__(parent, "PhotoChop Help")
        row = QHBoxLayout()
        row.addWidget(_lbl("Search:"))
        self.search = QLineEdit()
        self.search.returnPressed.connect(self._search)
        row.addWidget(self.search, 1)
        go = QPushButton("Go")
        go.clicked.connect(self._search)
        row.addWidget(go)
        self.content.addLayout(row)

        self.browser = QTextBrowser()
        self.browser.setHtml(HELP_HTML)
        self.browser.setFixedSize(430, 300)
        self.content.addWidget(self.browser)

        self.add_button("Close", self.accept, default=True)
        self.finish_side()

    def _search(self):
        term = self.search.text().strip()
        if not term:
            return
        self.browser.setHtml(
            f"<h3>Search results for &ldquo;{term}&rdquo;</h3>"
            f"<p>0 topics found.</p>"
            f"<p>PhotoChop Help has searched 4 topics and 1 index, and suggests you "
            f"try the topic titled &ldquo;About {term}&rdquo;, which does not exist.</p>"
            f"<p><a href='#'>Back to Contents</a></p>")
