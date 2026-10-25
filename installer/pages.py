"""The Setup pages that were not in the original four-step wizard.

Text-mode splash, the licence agreement, the product key, Typical/Custom,
and Select Components. Each page is a plain QWidget that exposes what it
collected; wizard.py owns the flow.

Pages come in the two Wizard97 shapes: interior pages with the white header
band (title, indented subtitle, icon on the right) over an etched line, and
exterior pages -- Welcome and Completing -- with the tall watermark down the
left and a white content area.
"""
from __future__ import annotations

import os
import random

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPalette
from PyQt6.QtWidgets import (
    QButtonGroup, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QRadioButton, QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import components as comps
from artwork import HeaderIcon, KeySticker, Watermark
from style import (
    ERROR_RED, GRAY_TEXT, HILIGHT, MONO_FONT_FAMILY, SHADOW, TEXT_COLOR,
    TITLE_FONT_FAMILY, VGA_BLUE, VGA_GRAY, VGA_WHITE, VGA_YELLOW, ui_font,
)


class Etched(QWidget):
    """The two-pixel groove Wizard97 puts under the header and above the
    buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(0, 0, self.width(), 1, QColor(SHADOW))
        p.fillRect(0, 1, self.width(), 1, QColor(HILIGHT))
        p.end()


def _paint_white(widget):
    widget.setAutoFillBackground(True)
    pal = widget.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
    widget.setPalette(pal)


def titled_page(title: str, subtitle: str = ""):
    """An interior page: white header band, etched line, grey body. The
    returned widget keeps ``heading`` and ``subheading`` so the wizard can
    retitle a page it reuses."""
    w = QWidget()
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    header = QWidget()
    _paint_white(header)
    header.setFixedHeight(58)
    row = QHBoxLayout(header)
    row.setContentsMargins(21, 4, 5, 4)
    texts = QVBoxLayout()
    texts.setContentsMargins(0, 6, 0, 0)
    texts.setSpacing(3)
    w.heading = QLabel(title)
    w.heading.setFont(ui_font(11, bold=True))
    w.subheading = QLabel(subtitle)
    w.subheading.setWordWrap(True)
    w.subheading.setContentsMargins(16, 0, 0, 0)
    w.subheading.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
    texts.addWidget(w.heading)
    texts.addWidget(w.subheading, 1)
    row.addLayout(texts, 1)
    row.addWidget(HeaderIcon(), 0, Qt.AlignmentFlag.AlignVCenter)
    outer.addWidget(header)
    outer.addWidget(Etched())

    layout = QVBoxLayout()
    layout.setContentsMargins(36, 12, 24, 8)
    layout.setSpacing(8)
    outer.addLayout(layout, 1)
    return w, layout


def exterior_page(title: str):
    """A Welcome/Completing page: watermark on the left, white on the right,
    the title in Verdana Bold."""
    w = QWidget()
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    row.addWidget(Watermark())
    content = QWidget()
    _paint_white(content)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(18, 16, 16, 10)
    layout.setSpacing(8)
    w.heading = QLabel(title)
    w.heading.setFont(ui_font(16, bold=True, family=TITLE_FONT_FAMILY))
    w.heading.setWordWrap(True)
    layout.addWidget(w.heading)
    layout.addSpacing(6)
    row.addWidget(content, 1)
    return w, layout


def body_label(text, wrap=True, indent=0):
    label = QLabel(text)
    label.setWordWrap(wrap)
    if indent:
        label.setContentsMargins(indent, 0, 0, 0)
    return label


# ------------------------------------------------------------- text mode ---

LOADING_LINES = [
    ("Press F6 if you need to install a third party SCSI or RAID driver...", 1300),
    ("Setup is loading files (Windows Executive)...", 450),
    ("Setup is loading files (Hardware Abstraction Layer)...", 400),
    ("Setup is loading files (Configuration Data)...", 350),
    ("Setup is loading files (Fat File System)...", 300),
    ("Setup is loading files (Microsloth Windows Setup)...", 450),
    ("Setup is starting Windows...", 800),
]

COPY_FILES = [
    "ntoskrnl.exe", "hal.dll", "ntdll.dll", "kernel32.dll", "user32.dll",
    "gdi32.dll", "win32k.sys", "comctl32.dll", "shell32.dll", "explorer.exe",
    "winlogon.exe", "msgina.dll", "logonui.exe", "notepad.exe", "mspaint.exe",
    "calc.exe", "winmine.exe", "wmplayer.exe", "iexplore.exe", "photochp.exe",
    "winword.exe", "excell.exe", "clippy.acs", "bliss.bmp", "tada.wav",
    "startup.wav", "luna.msstyles", "tahoma.ttf",
]

COLS, ROWS = 80, 25


class TextModePage(QWidget):
    """The 80x25 VGA screens before the wizard: hardware inspection on black,
    the file-loading status line, the Welcome to Setup menu, and the yellow
    file-copy bar. Loading can be skipped with any key; the Welcome screen
    waits for ENTER like the real one did."""
    done = pyqtSignal(str)          # "" or the action asked for ("repair")
    quit_requested = pyqtSignal()

    INSPECT, LOADING, WELCOME, QUIT, COPYING = range(5)

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.state = self.INSPECT
        self.status = ""
        self._index = 0
        self._choice = ""
        self._copy_pct = 0.0
        self._copy_file = COPY_FILES[0]
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)
        self._copy_timer = QTimer(self)
        self._copy_timer.timeout.connect(self._copy_tick)
        self._font_for = None
        self._font = None

    def start(self):
        self._choice = ""
        self._set(self.INSPECT, "")
        self._timer.start(900)

    def _set(self, state, status):
        self.state = state
        self.status = status
        self.update()

    def _advance(self):
        if self.state == self.INSPECT:
            self._index = 0
        else:
            self._index += 1
        if self._index >= len(LOADING_LINES):
            self._show_welcome()
            return
        text, delay = LOADING_LINES[self._index]
        self._set(self.LOADING, text)
        self._timer.start(delay)

    def _show_welcome(self):
        self._timer.stop()
        self._set(self.WELCOME, "ENTER=Continue  R=Repair  F3=Quit")

    def _begin_copy(self, choice):
        self._timer.stop()
        self._choice = choice
        self._copy_pct = 0.0
        self._set(self.COPYING, "")
        self._copy_tick()
        self._copy_timer.start(40)

    def _copy_tick(self):
        self._copy_pct = min(100.0, self._copy_pct + random.uniform(0.8, 3.2))
        self._copy_file = random.choice(COPY_FILES)
        self.status = f"Copying: {self._copy_file}"
        self.update()
        if self._copy_pct >= 100:
            self._finish()

    def _finish(self):
        self._timer.stop()
        self._copy_timer.stop()
        self.done.emit(self._choice)

    def skip(self):
        """Any key or click while Setup is just loading jumps ahead to the
        next place it would wait for you."""
        if self.state in (self.INSPECT, self.LOADING, self.QUIT):
            self._show_welcome()
        elif self.state == self.WELCOME:
            self._begin_copy("")
        elif self.state == self.COPYING:
            self._finish()

    def mousePressEvent(self, ev):
        self.skip()

    def keyPressEvent(self, ev):
        key = ev.key()
        if self.state == self.WELCOME:
            if key == Qt.Key.Key_R:
                self._begin_copy("repair")
            elif key == Qt.Key.Key_F3:
                self._set(self.QUIT, "F3=Quit  ENTER=Continue")
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._begin_copy("")
            return
        if self.state == self.QUIT:
            if key == Qt.Key.Key_F3:
                self.quit_requested.emit()
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
                self.skip()
            return
        self.skip()

    # -- painting on an 80x25 character grid -----------------------------

    def _grid_font(self, cw, ch):
        if self._font_for != (cw, ch):
            font = QFont(MONO_FONT_FAMILY)
            font.setStyleHint(QFont.StyleHint.TypeWriter)
            px = int(ch * 0.75)
            font.setPixelSize(px)
            while px > 6 and QFontMetricsF(font).horizontalAdvance("M") > cw:
                px -= 1
                font.setPixelSize(px)
            # pad each character out to exactly one cell
            spare = cw - QFontMetricsF(font).horizontalAdvance("M")
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spare)
            self._font, self._font_for = font, (cw, ch)
        return self._font

    def paintEvent(self, ev):
        p = QPainter(self)
        cw, ch = self.width() / COLS, self.height() / ROWS
        p.setFont(self._grid_font(cw, ch))
        fm = QFontMetricsF(p.font())
        baseline = (ch + fm.ascent() - fm.descent()) / 2

        def put(row, col, text, color=VGA_GRAY):
            p.setPen(QColor(color))
            p.drawText(QPointF(col * cw, row * ch + baseline), text)

        def centre(row, text, color=VGA_GRAY):
            put(row, (COLS - len(text)) // 2, text, color)

        def box(top, left, bottom, right, double=False):
            """Box-drawing characters, drawn as lines so they meet exactly."""
            p.setPen(QColor(VGA_GRAY))
            offsets = (-2, 2) if double else (0,)
            x0, x1 = left * cw + cw / 2, right * cw + cw / 2
            y0, y1 = top * ch + ch / 2, bottom * ch + ch / 2
            for d in offsets:
                p.drawRect(QRectF(x0 + d, y0 + d, x1 - x0 - 2 * d, y1 - y0 - 2 * d))

        if self.state == self.INSPECT:
            p.fillRect(self.rect(), QColor("#000000"))
            put(1, 1, "Setup is inspecting your computer's hardware configuration...")
            p.end()
            return

        p.fillRect(self.rect(), QColor(VGA_BLUE))
        title = "Windows Setup" if self.state == self.LOADING \
            else "Windows XP Professional Setup"
        put(0, 1, title, VGA_WHITE)
        put(1, 0, "═" * (len(title) + 2), VGA_WHITE)

        if self.state == self.WELCOME:
            put(4, 3, "Welcome to Setup.", VGA_WHITE)
            put(6, 3, "This portion of the Setup program prepares Microsloth(R)")
            put(7, 3, "Windows(R) XP to run on this computer.")
            put(10, 6, "•  To set up Windows XP now, press ENTER.")
            put(12, 6, "•  To repair a Windows XP installation, press R.")
            put(14, 6, "•  To quit Setup without installing Windows XP, press F3.")
        elif self.state == self.QUIT:
            box(6, 9, 17, 70, double=True)
            for i, line in enumerate((
                    "Windows XP is not completely set up on your",
                    "computer. If you quit Setup now, you will need",
                    "to run Setup again to set up Windows XP.")):
                put(8 + i, 13, line, VGA_WHITE)
            put(12, 15, "•  To continue Setup, press ENTER.", VGA_WHITE)
            put(14, 15, "•  To quit Setup, press F3.", VGA_WHITE)
        elif self.state == self.COPYING:
            centre(6, "Please wait while Setup copies files")
            centre(7, "to the Windows installation folders.")
            centre(8, "This might take several minutes to complete.")
            box(11, 13, 17, 66)
            centre(12, "Setup is copying files...")
            centre(14, f"{int(self._copy_pct)}%")
            bar_cells = 48
            filled = int(bar_cells * self._copy_pct / 100)
            p.fillRect(QRectF(16 * cw, 15.2 * ch, filled * cw, ch * 0.6),
                       QColor(VGA_YELLOW))

        # status strip along the bottom
        p.fillRect(QRectF(0, (ROWS - 1) * ch, self.width(), ch), QColor(VGA_GRAY))
        if self.status:
            put(ROWS - 1, 2, self.status, "#000000")
        p.end()


# --------------------------------------------------------------- licence ---

EULA = """END-USER LICENCE AGREEMENT FOR MICROSLOTH WINDOWS XP

IMPORTANT -- READ CAREFULLY: This End-User Licence Agreement ("Agreement") is a legal agreement between you and nobody in particular for the software product identified above, which is a simulation and is not an operating system.

1. GRANT OF LICENCE.

You may install and use one copy of the Software on one computer. You may also install it on several computers, and we will not find out, because there is no mechanism by which we could.

2. DESCRIPTION OF OTHER RIGHTS AND LIMITATIONS.

2.1  You may not reverse engineer, decompile, or disassemble the Software, except that the Software ships as readable source code, so this clause is decorative.

2.2  You may not rent, lease, or lend the Software. You may absolutely lend the Software.

2.3  You agree not to use the Software to produce anything you would be proud of.

3. ADOBO PHOTOCHOP 7.0.

The Software includes Adobo PhotoChop 7.0 Professional, licensed separately under terms substantially identical to these, printed in a smaller typeface, inside a box you no longer own.

4. UPGRADES.

There will be no upgrades. This is the last one. It came out in 2001 and it is still here.

5. NO WARRANTIES.

THE SOFTWARE IS PROVIDED "AS IS", WHICH IN THIS CASE MEANS "AS A JOKE". TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, THE AUTHORS DISCLAIM ALL WARRANTIES, INCLUDING ANY IMPLIED WARRANTY THAT THE BLUE SCREEN IS DECORATIVE.

6. LIMITATION OF LIABILITY.

In no event shall anyone be liable for any damages whatsoever arising out of the use of or inability to use the Software, including but not limited to loss of unsaved work, which is traditional.

7. SCRATCH DISKS.

You acknowledge that the scratch disk will be full. You acknowledge that it will be full at the moment least convenient to you. You accept this.

8. TERMINATION.

Without prejudice to any other rights, this Agreement terminates when you close the window.

By selecting "I accept this agreement" you confirm that you did not read any of the above, which puts you in the company of every person who has ever installed anything.
"""


class LicensePage(QWidget):
    accepted_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        page, layout = titled_page(
            "Licence Agreement",
            "Please read the following licence agreement. To continue with "
            "Setup, you must accept the agreement.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label(
            "Press the PAGE DOWN key to see the rest of the agreement."))

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(EULA)
        layout.addWidget(self.text, 1)

        self.group = QButtonGroup(self)
        self.accept_radio = QRadioButton("I &accept this agreement")
        self.decline_radio = QRadioButton("I &don't accept this agreement")
        self.decline_radio.setChecked(True)
        for radio in (self.accept_radio, self.decline_radio):
            self.group.addButton(radio)
            layout.addWidget(radio)
        self.accept_radio.toggled.connect(lambda _: self.accepted_changed.emit())

    def is_accepted(self) -> bool:
        return self.accept_radio.isChecked()

    def keyPressEvent(self, ev):
        # Text-mode Setup accepted the agreement with F8, and muscle memory
        # from 2003 is a real thing.
        if ev.key() == Qt.Key.Key_F8:
            self.accept_radio.setChecked(True)
            return
        super().keyPressEvent(ev)


# ----------------------------------------------------------- product key ---

CD_SLEEVE_KEY = ["FCKGW", "RHQQ2", "YXRKT", "8TG6W", "2B7Q8"]


class ProductKeyPage(QWidget):
    key_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        page, layout = titled_page(
            "Your Product Key",
            "Your Product Key uniquely identifies your copy of Windows XP.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        intro = QHBoxLayout()
        intro.setSpacing(14)
        intro.addWidget(KeySticker(), 0, Qt.AlignmentFlag.AlignTop)
        intro.addWidget(body_label(
            "The 25-character Product Key appears on the yellow sticker on "
            "the back of your Windows CD folder.\n\n"
            "Type the Product Key below:"), 1)
        layout.addLayout(intro)
        layout.addSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(4)
        key_label = body_label("Product &Key:", wrap=False)
        row.addWidget(key_label)
        row.addSpacing(6)
        self.boxes = []
        for i in range(5):
            box = QLineEdit()
            box.setMaxLength(5)
            box.setFixedWidth(52)
            box.textEdited.connect(lambda text, idx=i: self._on_edit(idx, text))
            self.boxes.append(box)
            row.addWidget(box)
            if i < 4:
                row.addWidget(QLabel("-"))
        key_label.setBuddy(self.boxes[0])
        row.addStretch(1)
        layout.addLayout(row)
        layout.addSpacing(10)

        self.hint = body_label(
            "The Product Key is on the back of the CD sleeve, which you have "
            "already thrown away.")
        layout.addWidget(self.hint)

        sleeve = QPushButton("&Use the key from the CD sleeve")
        sleeve.setAutoDefault(False)
        sleeve.clicked.connect(self._fill_sleeve_key)
        layout.addWidget(sleeve, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)

    def _on_edit(self, index, text):
        upper = "".join(ch for ch in text.upper() if ch.isalnum())
        box = self.boxes[index]
        if upper != text:
            box.setText(upper)
        if len(upper) == 5 and index < 4:
            self.boxes[index + 1].setFocus()
            self.boxes[index + 1].selectAll()
        self.key_changed.emit()

    def _fill_sleeve_key(self):
        for box, part in zip(self.boxes, CD_SLEEVE_KEY):
            box.setText(part)
        self.hint.setText("Found it. It was under the couch.")
        self.key_changed.emit()

    def key(self) -> str:
        return "-".join(box.text() for box in self.boxes)

    def is_complete(self) -> bool:
        return all(len(box.text()) == 5 for box in self.boxes)


# ------------------------------------------------------------ setup type ---

class SetupTypePage(QWidget):
    type_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        page, layout = titled_page(
            "Setup Type", "Choose the setup type that best suits your needs.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label("Click the type of Setup you prefer, then click Next."))
        layout.addSpacing(4)
        self.group = QButtonGroup(self)
        self._value = "typical"
        for key, title, desc in (
                ("typical", "&Typical",
                 "Installs the most common components. Recommended for most users."),
                ("custom", "&Custom",
                 "Choose which components to install. Recommended for advanced users."),
                ("complete", "C&omplete",
                 "Installs every component, including the ones nobody has ever used.")):
            radio = QRadioButton(title)
            radio.toggled.connect(
                lambda checked, k=key: self._pick(k) if checked else None)
            if key == "typical":
                radio.setChecked(True)
            self.group.addButton(radio)
            layout.addWidget(radio)
            layout.addWidget(body_label(desc, indent=19))
            layout.addSpacing(6)
        layout.addStretch(1)

    def _pick(self, key):
        self._value = key
        self.type_changed.emit()

    def value(self) -> str:
        return self._value


# ------------------------------------------------------- select components -

class ComponentsPage(QWidget):
    selection_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        page, layout = titled_page(
            "Windows Components",
            "You can add or remove components of Windows XP.")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label(
            "To add or remove a component, click the checkbox. A shaded box "
            "means that only part of the component will be installed. To see "
            "what's included in a component, click the plus sign beside it."))

        self.tree = QTreeWidget()
        components_label = body_label("&Components:", wrap=False)
        components_label.setBuddy(self.tree)
        layout.addWidget(components_label)
        self.tree.setColumnCount(2)
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(
            0, self.tree.header().ResizeMode.Stretch)
        self.tree.setColumnWidth(1, 70)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.tree, 1)

        desc_row = QHBoxLayout()
        desc_row.setSpacing(8)
        desc_title = body_label("Description:", wrap=False)
        desc_title.setAlignment(Qt.AlignmentFlag.AlignTop)
        desc_row.addWidget(desc_title, 0, Qt.AlignmentFlag.AlignTop)
        self.description = body_label("")
        self.description.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.description.setFixedHeight(28)
        desc_row.addWidget(self.description, 1)
        layout.addLayout(desc_row)

        space = QGridLayout()
        space.setHorizontalSpacing(12)
        space.setVerticalSpacing(2)
        space.addWidget(body_label("Total disk space required:", wrap=False), 0, 0)
        space.addWidget(body_label("Space available on disk:", wrap=False), 1, 0)
        self.space_required = body_label("", wrap=False)
        self.space_available = body_label("", wrap=False)
        for row, label in enumerate((self.space_required, self.space_available)):
            label.setAlignment(Qt.AlignmentFlag.AlignRight)
            label.setMinimumWidth(80)
            space.addWidget(label, row, 1)
        space.setColumnStretch(2, 1)
        layout.addLayout(space)

        self._items = {}
        self._loading = False
        self._build()

    def _build(self):
        self._loading = True
        self.tree.clear()
        for root in comps.CATALOGUE:
            self.tree.addTopLevelItem(self._make_item(root))
        self.tree.expandAll()
        self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self._loading = False

    def _make_item(self, component):
        item = QTreeWidgetItem([component.label, _mb(component.total_size())])
        item.setData(0, Qt.ItemDataRole.UserRole, component.id)
        item.setTextAlignment(1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if component.required:
            # Real Setup shows required components checked and greyed rather
            # than hiding them, so you can see what you are getting.
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(0, Qt.CheckState.Checked)
            for column in (0, 1):
                item.setForeground(column, QColor(GRAY_TEXT))
        else:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked
                               if component.default else Qt.CheckState.Unchecked)
        self._items[component.id] = item
        for child in component.children:
            item.addChild(self._make_item(child))
        return item

    def _on_item_changed(self, item, column):
        if self._loading or column != 0:
            return
        self._loading = True
        state = item.checkState(0)
        # a parent drags its optional children with it, both ways
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(0, state)
                self._cascade(child, state)
        self._refresh_parents(item.parent())
        self._loading = False
        self._refresh_space()
        self.selection_changed.emit()

    def _cascade(self, item, state):
        for i in range(item.childCount()):
            child = item.child(i)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(0, state)
                self._cascade(child, state)

    def _refresh_parents(self, item):
        while item is not None:
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable and item.childCount():
                states = {item.child(i).checkState(0) for i in range(item.childCount())}
                if states == {Qt.CheckState.Checked}:
                    item.setCheckState(0, Qt.CheckState.Checked)
                elif states == {Qt.CheckState.Unchecked}:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    item.setCheckState(0, Qt.CheckState.PartiallyChecked)
            item = item.parent()

    def _on_current_changed(self, current, _previous):
        if current is None:
            self.description.setText("")
            return
        cid = current.data(0, Qt.ItemDataRole.UserRole)
        component = comps.BY_ID.get(cid)
        if component is None:
            return
        note = component.note or f"{component.label}."
        if component.required:
            note += "  This component is required."
        self.description.setText(note)

    def set_selection(self, selected):
        self._loading = True
        for cid, item in self._items.items():
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(0, Qt.CheckState.Checked if cid in selected
                                   else Qt.CheckState.Unchecked)
        for cid, item in self._items.items():
            self._refresh_parents(item)
        self._loading = False
        self._refresh_space()

    def selection(self) -> set:
        chosen = set()
        for cid, item in self._items.items():
            if item.checkState(0) != Qt.CheckState.Unchecked:
                chosen.add(cid)
        # a child only counts as installed if its parent is
        for root in comps.CATALOGUE:
            _prune_orphans(root, chosen)
        return chosen

    def _refresh_space(self):
        chosen = self.selection()
        for cid, item in self._items.items():
            component = comps.BY_ID[cid]
            size = sum(c.size_mb for c in component.walk() if c.id in chosen)
            item.setText(1, _mb(size if size else component.total_size()))
        required = comps.selected_size_mb(chosen)
        available = comps.available_mb(os.path.dirname(
            os.path.expanduser("~/WindowsXP")))
        self.space_required.setText(f"{required:,} MB")
        self.space_available.setText(f"{available:,} MB")
        short = required > available
        self.space_available.setStyleSheet(
            f"color: {ERROR_RED if short else TEXT_COLOR};")

    def has_enough_space(self) -> bool:
        return comps.selected_size_mb(self.selection()) <= comps.available_mb()


def _prune_orphans(component, chosen):
    if component.id not in chosen:
        for child in component.walk():
            chosen.discard(child.id)
        return
    for child in component.children:
        _prune_orphans(child, chosen)


def _mb(value) -> str:
    return f"{value:,} MB" if value else ""
