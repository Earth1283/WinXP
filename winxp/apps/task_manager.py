from __future__ import annotations

import random

from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..app_registry import APPS, BY_ID
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox

CRITICAL_PROCS = {"csrss.exe", "winlogon.exe", "smss.exe", "services.exe", "lsass.exe", "System"}
PROTECTED_PROCS = {"System Idle Process"}
PRIORITIES = ("Realtime", "High", "Above Normal", "Normal", "Below Normal", "Low")

END_PROCESS_WARNING = (
    "WARNING: Terminating a process can cause undesired results including\n"
    "loss of data and system instability. The process will not be given\n"
    "the chance to save its state or data before it is terminated.\n\n"
    "Are you sure you want to terminate the process {name}?"
)

SYSTEM_PROCS = [
    ("System Idle Process", "0", "98", "24 K"),
    ("System", "4", "00", "212 K"),
    ("smss.exe", "512", "00", "364 K"),
    ("csrss.exe", "600", "00", "3,116 K"),
    ("winlogon.exe", "624", "00", "2,204 K"),
    ("services.exe", "668", "00", "3,432 K"),
    ("lsass.exe", "680", "00", "1,392 K"),
    ("svchost.exe", "852", "00", "4,108 K"),
    ("svchost.exe", "928", "00", "2,516 K"),
    ("spoolsv.exe", "1156", "00", "3,984 K"),
    ("explorer.exe", "1400", "01", "14,244 K"),
]

# Legacy/alternate names not implied by an AppSpec's id or exe() — e.g. WordPad's
# executable is historically "write.exe", and Explorer isn't in the app registry
# since it's core shell chrome rather than a launchable "app".
EXTRA_NEW_TASK_ALIASES = {
    "write.exe": "wordpad", "write": "wordpad",
    "explorer.exe": "explorer:root", "explorer": "explorer:root",
}


def _build_new_task_map():
    mapping = dict(EXTRA_NEW_TASK_ALIASES)
    for spec in APPS:
        mapping[spec.id] = spec.id
        mapping[spec.exe()] = spec.id
    return mapping


NEW_TASK_MAP = _build_new_task_map()


class PerfGraph(QWidget):
    """Classic XP CPU-usage history graph: green trace on black grid."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.history = [0] * 60

    def push(self, value):
        self.history.append(value)
        self.history = self.history[-60:]
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("black"))
        p.setPen(QPen(QColor("#0a3a0a"), 1))
        w, h = self.width(), self.height()
        for i in range(1, 8):
            y = int(h * i / 8)
            p.drawLine(0, y, w, y)
        for i in range(1, 12):
            x = int(w * i / 12)
            p.drawLine(x, 0, x, h)
        p.setPen(QPen(QColor("#33e33d"), 1))
        n = len(self.history)
        step = w / max(1, n - 1)
        pts = [(int(i * step), int(h - (v / 100.0) * h)) for i, v in enumerate(self.history)]
        for i in range(len(pts) - 1):
            p.drawLine(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])


class TaskManagerWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Windows Task Manager", icon_key="task_manager",
                          size=QSize(460, 420), resizable=True)
        self.wm = wm
        self._cpu_hist = 8
        self._killed_fake_pids: set[str] = set()
        self._priority: dict[str, str] = {}
        self._proc_rows: list[dict] = []

        outer = QVBoxLayout()
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(4)

        self.tabs = tabs = QTabWidget()
        tabs.addTab(self._build_applications_tab(), "Applications")
        tabs.addTab(self._build_processes_tab(), "Processes")
        tabs.addTab(self._build_performance_tab(), "Performance")
        outer.addWidget(tabs, 1)

        self.status = QLabel()
        self.status.setStyleSheet("border-top: 1px solid #aca998; padding: 2px 4px;")
        outer.addWidget(self.status)

        self.set_content_layout(outer)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    # -- Applications ---------------------------------------------------
    def _build_applications_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.app_list = QListWidget()
        self.app_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.app_list.customContextMenuRequested.connect(self._app_context_menu)
        layout.addWidget(self.app_list, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        end_btn = QPushButton("End Task")
        end_btn.clicked.connect(self._end_task)
        switch_btn = QPushButton("Switch To")
        switch_btn.clicked.connect(self._switch_to)
        new_btn = QPushButton("New Task...")
        new_btn.clicked.connect(self._new_task)
        for b in (end_btn, switch_btn, new_btn):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)
        self._refresh_apps()
        return w

    def _refresh_apps(self):
        self.app_list.clear()
        for window in self.wm.windows:
            if window is self:
                continue
            item = QListWidgetItem(f"{window.windowTitle()}\tRunning")
            item.setData(Qt.ItemDataRole.UserRole, window)
            self.app_list.addItem(item)

    def _selected_window(self):
        item = self.app_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _end_task(self):
        window = self._selected_window()
        if window:
            window.close()
            self._refresh_apps()

    def _switch_to(self):
        window = self._selected_window()
        if window:
            self.wm.restore(window)

    def _new_task(self):
        text, ok = QInputDialog.getText(self, "Create New Task", "Open:")
        if not ok or not text.strip():
            return
        key = text.strip().lower()
        target = NEW_TASK_MAP.get(key)
        if target:
            from . import launch
            launch(self.wm, target)

    def _app_context_menu(self, pos):
        item = self.app_list.itemAt(pos)
        if item is None:
            return
        self.app_list.setCurrentItem(item)
        window = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        end_act = menu.addAction("End Task")
        switch_act = menu.addAction("Switch To")
        menu.addSeparator()
        goto_act = menu.addAction("Go To Process")
        chosen = menu.exec(self.app_list.viewport().mapToGlobal(pos))
        if chosen == end_act:
            self._end_task()
        elif chosen == switch_act:
            self._switch_to()
        elif chosen == goto_act:
            self._goto_process(window)

    def _goto_process(self, window):
        self.tabs.setCurrentIndex(1)
        for r, row in enumerate(self._proc_rows):
            if row["window"] is window:
                self.proc_table.selectRow(r)
                return

    # -- Processes --------------------------------------------------------
    def _build_processes_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        self.proc_table = QTableWidget(0, 4)
        self.proc_table.setHorizontalHeaderLabels(["Image Name", "PID", "CPU", "Mem Usage"])
        self.proc_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.proc_table.verticalHeader().setVisible(False)
        self.proc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proc_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.proc_table.customContextMenuRequested.connect(self._proc_context_menu)
        layout.addWidget(self.proc_table)
        self._refresh_processes()
        return w

    def _refresh_processes(self):
        self._proc_rows = []
        for name, pid, cpu, mem in SYSTEM_PROCS:
            if pid in self._killed_fake_pids:
                continue
            self._proc_rows.append({"name": name, "pid": pid, "cpu": cpu, "mem": mem, "window": None})
        for window in self.wm.windows:
            if window is self:
                continue
            key = getattr(window, "_app_key", None)
            spec = BY_ID.get(key)
            exe = spec.exe() if spec else ("explorer.exe" if key == "explorer" else "app.exe")
            self._proc_rows.append({
                "name": exe, "pid": str(2000 + id(window) % 1000),
                "cpu": f"{random.randint(0, 3):02d}",
                "mem": f"{random.randint(2000, 18000):,} K", "window": window,
            })
        self.proc_table.setRowCount(len(self._proc_rows))
        for r, row in enumerate(self._proc_rows):
            for c, val in enumerate((row["name"], row["pid"], row["cpu"], row["mem"])):
                item = QTableWidgetItem(val)
                if c > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.proc_table.setItem(r, c, item)

    def _proc_context_menu(self, pos):
        row = self.proc_table.rowAt(pos.y())
        if row < 0 or row >= len(self._proc_rows):
            return
        self.proc_table.selectRow(row)
        info = self._proc_rows[row]
        menu = QMenu(self)
        end_act = menu.addAction("End Process")
        end_tree_act = menu.addAction("End Process Tree")
        menu.addSeparator()
        prio_menu = menu.addMenu("Set Priority")
        prio_actions = {}
        for label in PRIORITIES:
            act = prio_menu.addAction(label)
            prio_actions[act] = label
        menu.addSeparator()
        debug_act = menu.addAction("Debug")
        dump_act = menu.addAction("Create Dump File")
        chosen = menu.exec(self.proc_table.viewport().mapToGlobal(pos))
        if chosen in (end_act, end_tree_act):
            self._end_process(info)
        elif chosen in prio_actions:
            self._set_priority(info, prio_actions[chosen])
        elif chosen == debug_act:
            XPMessageBox.information(
                self, "Task Manager",
                "Unable to attach a debugger.\n\nTo debug this process, install a "
                "just-in-time debugger and try again."
            )
        elif chosen == dump_act:
            XPMessageBox.information(
                self, "Task Manager",
                f"Dump file created successfully.\n\nDumpFile: C:\\WINDOWS\\Minidump\\{info['name']}.dmp"
            )

    def _set_priority(self, info, label):
        if label == "Realtime":
            proceed = XPMessageBox.confirm(
                self, "Task Manager",
                "Using Realtime priority, an operating system component or a "
                "program may stop responding, resulting in your having to restart "
                "Windows.\n\nAre you sure you want to proceed?",
                kind="warning",
            )
            if not proceed:
                return
        self._priority[info["pid"]] = label
        XPMessageBox.information(self, "Task Manager", f"Priority of {info['name']} set to {label}.")

    def _end_process(self, info):
        name = info["name"]
        if name in PROTECTED_PROCS:
            XPMessageBox.critical(self, "Task Manager", "Unable to terminate process. Access is denied.")
            return
        proceed = XPMessageBox.confirm(
            self, "Task Manager", END_PROCESS_WARNING.format(name=name), kind="warning",
        )
        if not proceed:
            return

        if name == "explorer.exe":
            self._kill_explorer()
        elif info["window"] is not None:
            info["window"].close()
        elif name == "System":
            from .bsod import crash
            crash(self.wm, "System")
            return
        elif name in CRITICAL_PROCS:
            from ..corruption import health
            health.kill(name)
            self._killed_fake_pids.add(info["pid"])
            if health.level >= len(CRITICAL_PROCS) - 1:
                from .bsod import crash
                crash(self.wm, "cascading system failure")
                return
            XPMessageBox.information(
                self, "Task Manager",
                f"{name} has stopped responding and was terminated.\n\n"
                "Some system functionality may now be impaired."
            )
        else:
            self._killed_fake_pids.add(info["pid"])

        self._refresh_processes()
        self._refresh_apps()

    def _kill_explorer(self):
        """Cursed: explorer.exe IS the shell. Killing it closes every open
        Explorer window, freezes the desktop's icon rendering in place, and
        turns any further filesystem operation into a BSOD -- see
        corruption.guard_fs(), called from desktop.py and apps/explorer.py."""
        from ..corruption import health
        health.kill("explorer.exe")
        for window in list(self.wm.windows):
            if getattr(window, "_app_key", None) == "explorer":
                window.close()
        XPMessageBox.critical(
            self, "Windows Explorer",
            "Windows Explorer has stopped working.\n\n"
            "The desktop will no longer show new files, and opening folders "
            "or performing file operations may crash the system."
        )

    # -- Performance --------------------------------------------------------
    def _build_performance_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.addWidget(QLabel("CPU Usage History"))
        self.cpu_graph = PerfGraph()
        layout.addWidget(self.cpu_graph)
        layout.addWidget(QLabel("PF Usage History"))
        self.mem_graph = PerfGraph()
        layout.addWidget(self.mem_graph)
        return w

    # -- shared tick --------------------------------------------------------
    def _tick(self):
        self._cpu_hist += random.randint(-6, 6)
        self._cpu_hist = max(3, min(95, self._cpu_hist))
        if hasattr(self, "cpu_graph"):
            self.cpu_graph.push(self._cpu_hist)
            self.mem_graph.push(max(5, min(90, self._cpu_hist + random.randint(-10, 10))))
        self._refresh_apps()
        self._refresh_processes()
        n_procs = len(SYSTEM_PROCS) + max(0, len(self.wm.windows) - 1)
        self.status.setText(
            f"Processes: {n_procs}    CPU Usage: {self._cpu_hist}%    Commit Charge: {180 + n_procs * 12}M"
        )
