"""The Setup pages that were not in the original four-step wizard.

Text-mode splash, the licence agreement, the product key, Typical/Custom,
and Select Components. Each page is a plain QWidget that exposes what it
collected; wizard.py owns the flow.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import components as comps
from style import (
    ACCENT_BLUE, BODY_BG, BUTTON_STYLE, KEYBOX_STYLE, MONO_FONT_FAMILY,
    RULE_COLOR, SETUP_BLUE, SETUP_STATUS_BG, SUBTEXT_COLOR, TEXTBOX_STYLE,
    TEXT_COLOR, TREE_STYLE, UI_FONT_FAMILY,
)


def titled_page(title: str):
    """The heading + hairline every wizard page starts with."""
    w = QWidget()
    w.setStyleSheet(f"background: {BODY_BG}; color: {TEXT_COLOR};")
    layout = QVBoxLayout(w)
    layout.setContentsMargins(28, 22, 28, 20)
    layout.setSpacing(12)
    heading = QLabel(title)
    heading.setStyleSheet(
        f"font-weight: bold; font-size: 14px; color: {TEXT_COLOR}; border: none;")
    layout.addWidget(heading)
    rule = QWidget()
    rule.setFixedHeight(1)
    rule.setStyleSheet(f"background: {RULE_COLOR};")
    layout.addWidget(rule)
    return w, layout


def body_label(text, muted=False, wrap=True):
    label = QLabel(text)
    label.setWordWrap(wrap)
    label.setStyleSheet(
        f"color: {SUBTEXT_COLOR if muted else TEXT_COLOR}; border: none;")
    return label


# ------------------------------------------------------------- text mode ---

TEXT_MODE_LINES = [
    ("Setup is inspecting your computer's hardware configuration...", 900),
    ("Setup is loading files (Windows Executive)...", 500),
    ("Setup is loading files (Hardware Abstraction Layer)...", 400),
    ("Setup is loading files (Configuration Data)...", 400),
    ("Setup is starting Windows...", 700),
]


class TextModePage(QWidget):
    """The blue screen before the wizard: white header bar, blue field, grey
    status strip along the bottom. Runs once, then gets out of the way."""
    done = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.status = TEXT_MODE_LINES[0][0]
        self._index = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._advance)

    def start(self):
        self._index = 0
        self.status = TEXT_MODE_LINES[0][0]
        self.update()
        self._timer.start(TEXT_MODE_LINES[0][1])

    def skip(self):
        self._timer.stop()
        self.done.emit()

    def _advance(self):
        self._index += 1
        if self._index >= len(TEXT_MODE_LINES):
            self.done.emit()
            return
        self.status, delay = TEXT_MODE_LINES[self._index]
        self.update()
        self._timer.start(delay)

    def mousePressEvent(self, ev):
        self.skip()

    def keyPressEvent(self, ev):
        self.skip()

    def paintEvent(self, ev):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(SETUP_BLUE))

        # header: white strip with the product name, exactly like text mode
        p.fillRect(0, 0, w, 20, QColor(SETUP_STATUS_BG))
        p.setPen(QColor("#000000"))
        p.setFont(QFont(MONO_FONT_FAMILY, 10, QFont.Weight.Bold))
        p.drawText(8, 15, "Windows XP Professional Setup")

        p.setFont(QFont(MONO_FONT_FAMILY, 10))
        p.setPen(QColor("#c8c8c8"))
        centre = h // 2 - 40
        p.drawText(0, centre, w, 20, Qt.AlignmentFlag.AlignHCenter,
                   "Welcome to Setup.")
        p.setPen(QColor("#9fb4cf"))
        p.drawText(70, centre + 34, w - 140, 60, Qt.TextFlag.TextWordWrap,
                   "This portion of the Setup program prepares Microsloth "
                   "Windows XP to run on this computer.")

        # bottom status strip
        p.fillRect(0, h - 20, w, 20, QColor(SETUP_STATUS_BG))
        p.setPen(QColor("#000000"))
        p.setFont(QFont(MONO_FONT_FAMILY, 9))
        p.drawText(8, h - 6, self.status)
        p.setFont(QFont(MONO_FONT_FAMILY, 9))
        p.drawText(w - 150, h - 6, "ENTER=Continue")
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
        page, layout = titled_page("Licence Agreement")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label(
            "Please read the following licence agreement. Press the PAGE DOWN "
            "key to see the rest of the agreement.", muted=True))

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(EULA)
        self.text.setStyleSheet(TEXTBOX_STYLE)
        self.text.setFont(QFont(MONO_FONT_FAMILY, 8))
        layout.addWidget(self.text, 1)

        self.group = QButtonGroup(self)
        self.accept_radio = QRadioButton("I &accept this agreement")
        self.decline_radio = QRadioButton("I &don't accept this agreement")
        self.decline_radio.setChecked(True)
        for radio in (self.accept_radio, self.decline_radio):
            radio.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
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
        page, layout = titled_page("Your Product Key")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label(
            "Your Certificate of Authenticity has a 25-character Product Key "
            "printed on it. Type the Product Key below."))

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(body_label("Product Key:", wrap=False))
        self.boxes = []
        for i in range(5):
            box = QLineEdit()
            box.setMaxLength(5)
            box.setFixedWidth(58)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setStyleSheet(KEYBOX_STYLE)
            box.setFont(QFont(MONO_FONT_FAMILY, 10))
            box.textEdited.connect(lambda text, idx=i: self._on_edit(idx, text))
            self.boxes.append(box)
            row.addWidget(box)
            if i < 4:
                dash = QLabel("-")
                dash.setStyleSheet(f"color: {TEXT_COLOR}; border: none;")
                row.addWidget(dash)
        row.addStretch(1)
        layout.addLayout(row)

        self.hint = body_label(
            "The Product Key is on the back of the CD sleeve, which you have "
            "already thrown away.", muted=True)
        layout.addWidget(self.hint)

        sleeve = QPushButton("Use the key from the CD sleeve")
        sleeve.setStyleSheet(BUTTON_STYLE)
        sleeve.setMaximumWidth(240)
        sleeve.clicked.connect(self._fill_sleeve_key)
        layout.addWidget(sleeve)
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
        page, layout = titled_page("Setup Type")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label("Choose the setup type that best suits your needs.",
                                    muted=True))
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
            radio.setStyleSheet(
                f"font-weight: bold; color: {TEXT_COLOR}; border: none; padding: 2px 0;")
            radio.toggled.connect(
                lambda checked, k=key: self._pick(k) if checked else None)
            if key == "typical":
                radio.setChecked(True)
            self.group.addButton(radio)
            layout.addWidget(radio)
            sub = body_label(desc, muted=True)
            sub.setStyleSheet(
                f"color: {SUBTEXT_COLOR}; margin-left: 20px; border: none;")
            layout.addWidget(sub)
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
        page, layout = titled_page("Select Components")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        layout.addWidget(body_label(
            "Select the components you want to install; clear the components "
            "you do not want to install.", muted=True))

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Component", "Size"])
        self.tree.setStyleSheet(TREE_STYLE)
        self.tree.setRootIsDecorated(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 74)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.tree, 1)

        self.description = body_label("", muted=True)
        self.description.setFixedHeight(30)
        layout.addWidget(self.description)

        self.space_required = body_label("", wrap=False)
        self.space_available = body_label("", wrap=False)
        layout.addWidget(self.space_required)
        layout.addWidget(self.space_available)

        self._items = {}
        self._loading = False
        self._build()

    def _build(self):
        self._loading = True
        self.tree.clear()
        for root in comps.CATALOGUE:
            self.tree.addTopLevelItem(self._make_item(root))
        self.tree.expandAll()
        self._loading = False

    def _make_item(self, component):
        item = QTreeWidgetItem([component.label, _mb(component.total_size())])
        item.setData(0, Qt.ItemDataRole.UserRole, component.id)
        if component.required:
            # Real Setup shows required components checked and greyed rather
            # than hiding them, so you can see what you are getting.
            item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(0, Qt.CheckState.Checked)
            for column in (0, 1):
                item.setForeground(column, QColor("#7c7c7c"))
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
        self.space_required.setText(f"Space required on C:      {required:,} MB")
        self.space_available.setText(f"Space available on C:   {available:,} MB")
        short = required > available
        self.space_available.setStyleSheet(
            f"color: {'#c00000' if short else TEXT_COLOR}; border: none;")

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
