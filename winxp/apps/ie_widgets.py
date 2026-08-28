from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QToolButton, QVBoxLayout, QWidget,
)

from . import ie_icons
from .ie_sites import HOME_URL


class RebarGrip(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(8)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(QPen(QColor("white"), 1))
        for y in range(5, self.height() - 3, 4):
            painter.drawPoint(4, y)
        painter.setPen(QPen(QColor("#878578"), 1))
        for y in range(4, self.height() - 3, 4):
            painter.drawPoint(3, y)


class BrandPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(44, 38)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_active(self, active):
        if active:
            self._timer.start(120)
        else:
            self._timer.stop()
            self._phase = 0
        self.update()

    def _tick(self):
        self._phase = (self._phase + 1) % 8
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#071b45" if self._phase % 2 else "#102d61"))
        x = 6 if self._phase in (2, 3) else 5
        painter.drawPixmap(x, 2, ie_icons.icon("branding", 34).pixmap(34, 34))
        painter.setPen(QColor("#78776d"))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class ExplorerBar(QWidget):
    closed = pyqtSignal()

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.kind = ""
        self.setFixedWidth(214)
        self.setStyleSheet("background:white;border-right:1px solid #aca899")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = QWidget()
        header.setStyleSheet("background:#0a5bc4;color:white")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(7, 3, 3, 3)
        self.title = QLabel("Search")
        self.title.setStyleSheet("color:white;font-weight:bold;background:transparent")
        header_layout.addWidget(self.title)
        header_layout.addStretch(1)
        close = QToolButton()
        close.setText("×")
        close.setFixedSize(18, 18)
        close.setStyleSheet("color:white;font-weight:bold;background:transparent;border:0")
        close.clicked.connect(self.closed)
        header_layout.addWidget(close)
        root.addWidget(header)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(8, 9, 8, 8)
        root.addWidget(self.body, 1)

    def clear_body(self):
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_kind(self, kind):
        self.kind = kind
        self.title.setText(kind)
        self.clear_body()
        if kind == "Search":
            self.show_search()
        else:
            self.show_list(kind)

    def show_search(self):
        label = QLabel("Search for Web pages containing:")
        label.setWordWrap(True)
        self.body_layout.addWidget(label)
        search_text = QLineEdit()
        self.body_layout.addWidget(search_text)
        search = QPushButton("Search")
        search.setFixedWidth(76)
        search.clicked.connect(lambda: self.owner.search_web(search_text.text()))
        search_text.returnPressed.connect(lambda: self.owner.search_web(search_text.text()))
        self.body_layout.addWidget(search, 0, Qt.AlignmentFlag.AlignRight)
        tip = QLabel("<br><b>Search Companion</b><br><br>A dog was planned for this panel, "
                     "but the dog joined the Office Assistant bargaining unit.")
        tip.setWordWrap(True)
        self.body_layout.addWidget(tip)
        self.body_layout.addStretch(1)
        search_text.setFocus()

    def show_list(self, kind):
        items = QListWidget()
        items.setStyleSheet("QListWidget{border:0;background:white} QListWidget::item{padding:3px}")
        rows = self.favorite_rows() if kind == "Favorites" else self.history_rows()
        for text, url in rows:
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, url)
            item.setIcon(ie_icons.icon("favorites" if kind == "Favorites" else "history", 16))
            items.addItem(item)
        items.itemActivated.connect(self.open_item)
        self.body_layout.addWidget(items, 1)

    @staticmethod
    def favorite_rows():
        return [
            ("Links", ""), ("MSN.com", HOME_URL),
            ("MacroHard Corporation", "http://www.macrohard.com/"),
            ("Windows Update", "http://xphome.local/changelog.html"),
            ("Steve's XP Fan Page!!!", "http://www.geocities.local/xp_fan_page/"),
        ]

    def history_rows(self):
        rows = [(urlparse(url).netloc or url, url) for url in reversed(self.owner.history)]
        return rows or [("Today", "")]

    def open_item(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            self.owner.navigate(url)
