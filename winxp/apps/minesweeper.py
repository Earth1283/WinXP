from __future__ import annotations

import random

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import theme
from ..window_manager import XPWindow

DIFFICULTIES = {
    "Beginner": (9, 9, 10),
    "Intermediate": (16, 16, 40),
    "Expert": (30, 16, 99),
}

NUMBER_COLORS = {
    1: "#0000ff", 2: "#008000", 3: "#ff0000", 4: "#000080",
    5: "#800000", 6: "#008080", 7: "#000000", 8: "#808080",
}


class Cell(QPushButton):
    revealed_click = pyqtSignal(int, int)
    flag_click = pyqtSignal(int, int)
    chord_click = pyqtSignal(int, int)

    def __init__(self, x, y):
        super().__init__()
        self.x, self.y = x, y
        self.setFixedSize(20, 20)
        self.is_mine = False
        self.is_flagged = False
        self.is_revealed = False
        self.adjacent = 0
        self._update_style()

    def _update_style(self):
        if self.is_revealed:
            self.setStyleSheet(
                "background: #c0c0c0; border: 1px solid #808080;"
            )
        else:
            self.setStyleSheet(
                "QPushButton { background: #c0c0c0; border: 2px outset #ffffff; }"
                "QPushButton:pressed { border: 1px solid #808080; }"
            )

    def paintEvent(self, ev):
        super().paintEvent(ev)
        if not self.is_revealed:
            if self.is_flagged:
                p = QPainter(self)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                p.setPen(QPen(QColor("black"), 1))
                p.setBrush(QColor("red"))
                p.drawLine(10, 4, 10, 16)
                p.drawPolygon(QPolygon([self._pt(10, 4), self._pt(4, 7), self._pt(10, 10)]))
                p.setBrush(QColor("black"))
                p.drawRect(6, 16, 8, 2)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.is_mine:
            p.setBrush(QColor("black"))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(4, 4, 12, 12)
        elif self.adjacent:
            p.setPen(QColor(NUMBER_COLORS.get(self.adjacent, "#000")))
            f = QFont("Tahoma", 10)
            f.setBold(True)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(self.adjacent))

    @staticmethod
    def _pt(x, y):
        from PyQt6.QtCore import QPoint
        return QPoint(x, y)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.revealed_click.emit(self.x, self.y)
        elif ev.button() == Qt.MouseButton.RightButton:
            self.flag_click.emit(self.x, self.y)
        elif ev.button() == Qt.MouseButton.MiddleButton:
            self.chord_click.emit(self.x, self.y)


class MinesweeperWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Minesweeper", icon_key="minesweeper", size=QSize(300, 380), resizable=False)
        self.w = self.h = self.mines = 0
        self.cells: dict[tuple, Cell] = {}
        self.first_click = True
        self.game_over = False
        self.flags_used = 0
        self.elapsed = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setMenuBar(self._build_menu())

        panel = QWidget()
        panel.setStyleSheet("background: #c0c0c0; border: 2px inset #808080;")
        panel_l = QHBoxLayout(panel)
        panel_l.setContentsMargins(6, 6, 6, 6)

        self.mine_counter = QLabel("010")
        self.mine_counter.setStyleSheet(
            "background: black; color: red; font: bold 16px 'Courier New'; padding: 2px 6px;"
        )
        panel_l.addWidget(self.mine_counter)
        panel_l.addStretch(1)

        self.smiley = QPushButton("🙂")
        self.smiley.setFixedSize(28, 28)
        self.smiley.clicked.connect(lambda: self.new_game(self.w, self.h, self.mines))
        panel_l.addWidget(self.smiley)
        panel_l.addStretch(1)

        self.timer_label = QLabel("000")
        self.timer_label.setStyleSheet(
            "background: black; color: red; font: bold 16px 'Courier New'; padding: 2px 6px;"
        )
        panel_l.addWidget(self.timer_label)

        outer.addWidget(panel)

        self.grid_holder = QWidget()
        self.grid_holder.setStyleSheet("background: #c0c0c0;")
        self.grid_layout = QGridLayout(self.grid_holder)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setContentsMargins(6, 6, 6, 6)
        outer.addWidget(self.grid_holder)
        outer.addStretch(1)

        self.set_content_layout(outer)
        self.new_game(*DIFFICULTIES["Beginner"])

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        theme.style_menubar(bar)
        game_menu = bar.addMenu("&Game")
        for label in DIFFICULTIES:
            act = QAction(label, self)
            act.triggered.connect(lambda _, l=label: self.new_game(*DIFFICULTIES[l]))
            game_menu.addAction(act)
        game_menu.addSeparator()
        new_act = QAction("New", self)
        new_act.triggered.connect(lambda: self.new_game(self.w, self.h, self.mines))
        game_menu.addAction(new_act)
        return bar

    def new_game(self, w, h, mines):
        self.w, self.h, self.mines = w, h, mines
        for c in self.cells.values():
            self.grid_layout.removeWidget(c)
            c.deleteLater()
        self.cells.clear()
        self.first_click = True
        self.game_over = False
        self.flags_used = 0
        self.elapsed = 0
        self.timer.stop()
        self.timer_label.setText("000")
        self.mine_counter.setText(f"{mines:03d}")
        self.smiley.setText("🙂")

        for y in range(h):
            for x in range(w):
                cell = Cell(x, y)
                cell.revealed_click.connect(self._on_reveal)
                cell.flag_click.connect(self._on_flag)
                cell.chord_click.connect(self._on_chord)
                self.grid_layout.addWidget(cell, y, x)
                self.cells[(x, y)] = cell

        self.resize(max(240, w * 20 + 40), h * 20 + 120)

    def _place_mines(self, safe_x, safe_y):
        positions = [(x, y) for x in range(self.w) for y in range(self.h)
                     if abs(x - safe_x) > 1 or abs(y - safe_y) > 1]
        random.shuffle(positions)
        for (x, y) in positions[:self.mines]:
            self.cells[(x, y)].is_mine = True
        for (x, y), cell in self.cells.items():
            cell.adjacent = sum(
                1 for nx, ny in self._neighbors(x, y) if self.cells[(nx, ny)].is_mine
            )

    def _neighbors(self, x, y):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.w and 0 <= ny < self.h:
                    yield nx, ny

    def _tick(self):
        self.elapsed = min(999, self.elapsed + 1)
        self.timer_label.setText(f"{self.elapsed:03d}")

    def _on_reveal(self, x, y):
        if self.game_over:
            return
        cell = self.cells[(x, y)]
        if cell.is_flagged or cell.is_revealed:
            return
        if self.first_click:
            self._place_mines(x, y)
            self.first_click = False
            self.timer.start(1000)
        if cell.is_mine:
            self._lose(cell)
            return
        self._flood(x, y)
        self._check_win()

    def _flood(self, x, y):
        stack = [(x, y)]
        seen = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in seen:
                continue
            seen.add((cx, cy))
            cell = self.cells[(cx, cy)]
            if cell.is_revealed or cell.is_flagged:
                continue
            cell.is_revealed = True
            cell._update_style()
            cell.update()
            if cell.adjacent == 0:
                for nx, ny in self._neighbors(cx, cy):
                    stack.append((nx, ny))

    def _on_flag(self, x, y):
        if self.game_over:
            return
        cell = self.cells[(x, y)]
        if cell.is_revealed:
            return
        cell.is_flagged = not cell.is_flagged
        self.flags_used += 1 if cell.is_flagged else -1
        self.mine_counter.setText(f"{max(0, self.mines - self.flags_used):03d}")
        cell.update()

    def _on_chord(self, x, y):
        cell = self.cells[(x, y)]
        if not cell.is_revealed or cell.adjacent == 0:
            return
        neighbors = list(self._neighbors(x, y))
        flagged = sum(1 for nx, ny in neighbors if self.cells[(nx, ny)].is_flagged)
        if flagged == cell.adjacent:
            for nx, ny in neighbors:
                self._on_reveal(nx, ny)

    def _lose(self, exploded):
        self.game_over = True
        self.timer.stop()
        self.smiley.setText("😵")
        for cell in self.cells.values():
            if cell.is_mine:
                cell.is_revealed = True
                cell._update_style()
                cell.update()

    def _check_win(self):
        total = self.w * self.h
        revealed = sum(1 for c in self.cells.values() if c.is_revealed)
        if revealed == total - self.mines:
            self.game_over = True
            self.timer.stop()
            self.smiley.setText("😎")
            for cell in self.cells.values():
                if cell.is_mine and not cell.is_flagged:
                    cell.is_flagged = True
                    cell.update()
            self.mine_counter.setText("000")
