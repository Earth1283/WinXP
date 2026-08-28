"""MacroHard Internet Explorer 6 for the Windows XP simulator."""
from __future__ import annotations

import re
from html import escape
from urllib.parse import parse_qs, quote_plus, urlparse

from PyQt6.QtCore import QSize, Qt, QUrl
from PyQt6.QtGui import QAction, QImage, QKeySequence, QTextDocument
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QMenuBar, QProgressBar,
    QStatusBar, QTextBrowser, QToolButton,
    QVBoxLayout, QWidget,
)

from .. import theme
from ..window_manager import XPWindow
from ..xp_dialog import XPMessageBox
from . import ie_icons
from .ie_sites import HOME_URL, PAGES, error_page, search_results, static_page
from .ie_widgets import BrandPanel, ExplorerBar, RebarGrip


USER_AGENT = b"Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"

REBAR_QSS = """
QWidget#ieRebar { background: #ece9d8; border-bottom: 1px solid #aca899; }
QToolButton { background: transparent; border: 1px solid transparent; border-radius: 2px;
              padding: 2px 3px; color: #111111; }
QToolButton:hover { background: #f4f3ee; border-color: #b6b2a4; }
QToolButton:pressed, QToolButton:checked { background: #d8d5c8; border-color: #716f64; }
QToolButton:disabled { color: #8a897f; }
QLineEdit { background: white; border: 1px solid #7f9db9; padding: 2px 3px; }
QLabel { background: transparent; }
"""

STATUS_QSS = """
QStatusBar { background: #ece9d8; border-top: 1px solid white; }
QLabel#statusPanel { border-left: 1px solid #aca899; padding: 1px 7px; }
QProgressBar { border: 1px solid #7f9db9; background: white; }
QProgressBar::chunk { background: #36a735; }
"""

class _ImageTextBrowser(QTextBrowser):
    def __init__(self, ie_window):
        super().__init__()
        self._ie = ie_window

    def loadResource(self, resource_type, name):
        if resource_type == QTextDocument.ResourceType.ImageResource:
            return self._ie._load_image(name)
        return super().loadResource(resource_type, name)


class IEWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Microsoft Internet Explorer", icon_key="ie", size=QSize(900, 650))
        self.history = []
        self.hist_index = -1
        self.net = QNetworkAccessManager(self)
        self._pending_reply = None
        self.image_cache = {}
        self._pending_images = set()
        self._current_html = ""
        self._current_title = ""
        self._loading = False
        self.work_offline = False

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.setMenuBar(self.build_menu())
        self.standard_bar = self.build_standard_bar()
        self.address_bar = self.build_address_bar()
        self.links_bar = self.build_links_bar()
        root.addWidget(self.standard_bar)
        root.addWidget(self.address_bar)
        root.addWidget(self.links_bar)

        self.browser = _ImageTextBrowser(self)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self.open_link)
        self.browser.highlighted.connect(self.hover_link)
        self.browser.setStyleSheet("QTextBrowser{background:white;border:0;padding:0}")
        self.explorer_bar = ExplorerBar(self)
        self.explorer_bar.hide()
        self.explorer_bar.closed.connect(self.explorer_bar.hide)
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self.explorer_bar)
        body_layout.addWidget(self.browser, 1)
        root.addWidget(body, 1)
        self.status_bar = self.build_status_bar()
        root.addWidget(self.status_bar)
        self.set_content_layout(root)
        self.navigate(HOME_URL)

    def add_action(self, menu, text, slot=None, shortcut=None, checkable=False, checked=False, enabled=True):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            self.addAction(action)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        action.setEnabled(enabled)
        callback = slot or (lambda _=False, label=text: self.not_available(label))
        action.triggered.connect(callback)
        menu.addAction(action)
        return action

    def build_menu(self):
        bar = QMenuBar()
        theme.style_menubar(bar)
        menu = bar.addMenu("&File")
        self.add_action(menu, "&New Window", self.new_window, "Ctrl+N")
        self.add_action(menu, "&Open...", self.focus_address, "Ctrl+O")
        self.add_action(menu, "&Edit with MacroHard Word")
        self.add_action(menu, "&Save", self.save_page, "Ctrl+S")
        self.add_action(menu, "Save &As...", self.save_page)
        menu.addSeparator()
        self.add_action(menu, "Page Set&up...")
        self.add_action(menu, "&Print...", self.print_page, "Ctrl+P")
        self.add_action(menu, "Print Pre&view...")
        send = menu.addMenu("Sen&d")
        for text in ("Page by E-mail...", "Link by E-mail...", "Shortcut to Desktop"):
            self.add_action(send, text)
        menu.addSeparator()
        self.add_action(menu, "&Import and Export...")
        self.add_action(menu, "P&roperties", self.page_properties)
        self.offline_action = self.add_action(menu, "Work &Offline", self.toggle_offline, checkable=True)
        menu.addSeparator()
        self.add_action(menu, "&Close", self.close)

        menu = bar.addMenu("&Edit")
        self.add_action(menu, "Cu&t", enabled=False)
        self.add_action(menu, "&Copy", lambda: self.browser.copy(), "Ctrl+C")
        self.add_action(menu, "&Paste", enabled=False)
        menu.addSeparator()
        self.add_action(menu, "Select &All", lambda: self.browser.selectAll(), "Ctrl+A")
        self.add_action(menu, "&Find (on This Page)...", self.find_on_page, "Ctrl+F")

        menu = bar.addMenu("&View")
        toolbars = menu.addMenu("&Toolbars")
        self.add_action(toolbars, "&Standard Buttons", lambda checked: self.standard_bar.setVisible(checked),
                        checkable=True, checked=True)
        self.add_action(toolbars, "&Address Bar", lambda checked: self.address_bar.setVisible(checked),
                        checkable=True, checked=True)
        self.add_action(toolbars, "&Links", lambda checked: self.links_bar.setVisible(checked),
                        checkable=True, checked=True)
        self.add_action(toolbars, "Lock the &Toolbars", checkable=True, checked=True)
        self.add_action(menu, "&Status Bar", lambda checked: self.status_bar.setVisible(checked),
                        checkable=True, checked=True)
        explorer = menu.addMenu("E&xplorer Bar")
        self.add_action(explorer, "&Search", lambda: self.show_explorer("Search"), "Ctrl+E")
        self.add_action(explorer, "&Favorites", lambda: self.show_explorer("Favorites"), "Ctrl+I")
        self.add_action(explorer, "&History", lambda: self.show_explorer("History"), "Ctrl+H")
        explorer.addSeparator()
        self.add_action(explorer, "&Folders")
        menu.addSeparator()
        go = menu.addMenu("&Go To")
        self.add_action(go, "&Back", self.go_back, "Alt+Left")
        self.add_action(go, "&Forward", self.go_forward, "Alt+Right")
        self.add_action(go, "&Home Page", lambda: self.navigate(HOME_URL), "Alt+Home")
        self.add_action(menu, "&Stop", self.stop, "Esc")
        self.add_action(menu, "&Refresh", self.refresh, "F5")
        menu.addSeparator()
        text_size = menu.addMenu("Text Si&ze")
        for label in ("Largest", "Larger", "Medium", "Smaller", "Smallest"):
            self.add_action(text_size, label, lambda _=False, value=label: self.set_text_size(value),
                            checkable=True, checked=label == "Medium")
        encoding = menu.addMenu("&Encoding")
        self.add_action(encoding, "Auto-Select", checkable=True, checked=True)
        self.add_action(encoding, "Western European (Windows)", checkable=True, checked=True)
        self.add_action(menu, "Sour&ce", self.view_source)
        menu.addSeparator()
        self.add_action(menu, "&Full Screen", self.toggle_maximize, "F11")

        menu = bar.addMenu("F&avorites")
        self.add_action(menu, "&Add to Favorites...", self.add_favorite, "Ctrl+D")
        self.add_action(menu, "&Organize Favorites...")
        menu.addSeparator()
        self.add_action(menu, "MSN.com", lambda: self.navigate(HOME_URL))
        self.add_action(menu, "MacroHard Corporation", lambda: self.navigate("http://www.macrohard.com/"))
        self.add_action(menu, "Steve's XP Fan Page!!!", lambda: self.navigate("http://www.geocities.local/xp_fan_page/"))

        menu = bar.addMenu("&Tools")
        mail = menu.addMenu("&Mail and News")
        for text in ("Read Mail", "New Message...", "Send a Link...", "Send Page..."):
            self.add_action(mail, text)
        self.add_action(menu, "S&ynchronize...")
        self.add_action(menu, "Windows &Update", lambda: self.navigate("http://xphome.local/changelog.html"))
        self.add_action(menu, "Show &Related Links")
        menu.addSeparator()
        self.add_action(menu, "&Internet Options...", self.internet_options)

        menu = bar.addMenu("&Help")
        self.add_action(menu, "&Contents and Index")
        self.add_action(menu, "&Tip of the Day", self.tip_of_day)
        self.add_action(menu, "For &Netscape Users", self.netscape_help)
        self.add_action(menu, "Online Support")
        self.add_action(menu, "Send Feedback")
        menu.addSeparator()
        self.add_action(menu, "&About Internet Explorer", self.about)
        return bar

    def make_rebar(self, height):
        bar = QWidget()
        bar.setObjectName("ieRebar")
        bar.setFixedHeight(height)
        bar.setStyleSheet(REBAR_QSS)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(1)
        layout.addWidget(RebarGrip())
        return bar, layout

    def separator(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedWidth(7)
        return line

    def tool_button(self, name, text, slot, tooltip, width, menu=None):
        button = QToolButton()
        button.setAutoRaise(True)
        button.setIcon(ie_icons.icon(name, 24))
        button.setIconSize(QSize(24, 24))
        button.setText(text)
        if text:
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setToolTip(tooltip)
        button.setStatusTip(tooltip)
        button.setFixedWidth(width)
        if menu:
            button.setMenu(menu)
            button.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
        button.clicked.connect(slot)
        return button

    def build_standard_bar(self):
        bar, row = self.make_rebar(41)
        self.back_btn = self.tool_button("back", "Back", self.go_back, "Back", 76, QMenu())
        self.forward_btn = self.tool_button("forward", "", self.go_forward, "Forward", 35)
        self.stop_btn = self.tool_button("stop", "", self.stop, "Stop", 34)
        row.addWidget(self.back_btn)
        row.addWidget(self.forward_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.tool_button("refresh", "", self.refresh, "Refresh", 34))
        row.addWidget(self.tool_button("home", "", lambda: self.navigate(HOME_URL), "Home", 34))
        row.addWidget(self.separator())
        row.addWidget(self.tool_button("search", "Search", lambda: self.show_explorer("Search"), "Search", 76))
        row.addWidget(self.tool_button("favorites", "Favorites", lambda: self.show_explorer("Favorites"), "Favorites", 86))
        row.addWidget(self.tool_button("media", "Media", lambda: self.not_available("Media Bar"), "Media", 72))
        row.addWidget(self.separator())
        mail_menu = QMenu()
        for text in ("Read Mail", "New Message...", "Send a Link...", "Send Page..."):
            self.add_action(mail_menu, text)
        row.addWidget(self.tool_button("mail", "", lambda: self.not_available("Read Mail"), "Mail", 39, mail_menu))
        row.addWidget(self.tool_button("print", "", self.print_page, "Print", 36))
        row.addWidget(self.tool_button("edit", "", lambda: self.not_available("Edit with MacroHard Word"), "Edit", 36))
        row.addStretch(1)
        self.brand = BrandPanel()
        row.addWidget(self.brand)
        self.back_btn.setEnabled(False)
        self.forward_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        return bar

    def build_address_bar(self):
        bar, row = self.make_rebar(27)
        label = QLabel("Address")
        label.setFixedWidth(48)
        row.addWidget(label)
        icon_label = QLabel()
        icon_label.setPixmap(ie_icons.icon("ie_small", 16).pixmap(16, 16))
        icon_label.setFixedSize(19, 21)
        icon_label.setStyleSheet("background:white;border:1px solid #7f9db9;border-right:0")
        row.addWidget(icon_label)
        self.address = QLineEdit()
        self.address.returnPressed.connect(self.open_address)
        row.addWidget(self.address, 1)
        go = self.tool_button("go", "Go", self.open_address, "Go to the address", 54)
        go.setIconSize(QSize(18, 18))
        row.addWidget(go)
        return bar

    def build_links_bar(self):
        bar, row = self.make_rebar(25)
        label = QLabel("Links")
        label.setFixedWidth(40)
        row.addWidget(label)
        links = [
            ("Customize Links", "http://xphome.local/"), ("Free Hotmail", HOME_URL),
            ("Windows", "http://xphome.local/"), ("Windows Media", "http://www.macrohard.com/"),
            ("Steve's XP Page!!!", "http://www.geocities.local/xp_fan_page/"),
        ]
        for text, url in links:
            button = QToolButton()
            button.setAutoRaise(True)
            button.setText(text)
            button.clicked.connect(lambda _=False, target=url: self.navigate(target))
            row.addWidget(button)
        row.addStretch(1)
        more = QToolButton()
        more.setText("»")
        more.setFixedWidth(20)
        more.setToolTip("More Links")
        row.addWidget(more)
        return bar

    def build_status_bar(self):
        bar = QStatusBar()
        bar.setSizeGripEnabled(True)
        bar.setFixedHeight(23)
        bar.setStyleSheet(STATUS_QSS)
        self.status_text = QLabel("Done")
        self.status_text.setMinimumWidth(250)
        bar.addWidget(self.status_text, 1)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(105, 15)
        self.progress.hide()
        bar.addPermanentWidget(self.progress)
        zone_icon = QLabel()
        zone_icon.setObjectName("statusPanel")
        zone_icon.setPixmap(ie_icons.icon("globe", 16).pixmap(16, 16))
        bar.addPermanentWidget(zone_icon)
        self.zone_label = QLabel("Internet")
        self.zone_label.setObjectName("statusPanel")
        self.zone_label.setMinimumWidth(108)
        bar.addPermanentWidget(self.zone_label)
        return bar

    def open_address(self):
        self.navigate(self.address.text().strip())

    def navigate(self, url, record=True):
        if not url:
            return
        url = url.strip()
        if url.startswith(("file:", "javascript:")):
            self.render_error(url, "Active content was restricted. Internet Explorer feels powerful.", record)
            return
        if not url.startswith(("http://", "https://", "about:")):
            if " " in url:
                self.search_web(url)
                return
            url = "http://" + url
        if url + "/" in PAGES:
            url += "/"
        if url.startswith("http://www.google.com/search?"):
            query = parse_qs(urlparse(url).query).get("q", [""])[0]
            self.render(url, f"{query} - Google Search", search_results(query), record)
        elif url in PAGES:
            title, html = static_page(url)
            self.render(url, title, html, record)
        elif url.startswith("about:"):
            self.render(url, url, "<body></body>", record)
        elif self.work_offline:
            self.render_error(url, "Internet Explorer cannot display this page while Work Offline is selected.", record)
        else:
            self.fetch(url, record)

    def render(self, url, title, html, record):
        self._current_html = html
        self._current_title = title
        self.browser.document().setBaseUrl(QUrl(url))
        self.browser.setHtml(html)
        self.address.setText(url)
        self.setWindowTitle(f"{title} - Microsoft Internet Explorer")
        zone = "My Computer" if url.startswith("about:") else "Local intranet" if ".local" in url else "Internet"
        self.zone_label.setText(zone)
        if record:
            self.history = self.history[:self.hist_index + 1]
            self.history.append(url)
            self.hist_index = len(self.history) - 1
        self.set_loading(False)
        self.update_nav_buttons()
        if self.explorer_bar.isVisible() and self.explorer_bar.kind == "History":
            self.explorer_bar.show_kind("History")

    def render_error(self, url, detail, record):
        self.render(url, "Cannot find server", error_page(detail), record)
        self.status_text.setText("Error on page.")

    def fetch(self, url, record):
        if self._pending_reply:
            self._pending_reply.abort()
        host = urlparse(url).netloc
        self.address.setText(url)
        self.setWindowTitle(f"Connecting to site {host} - Microsoft Internet Explorer")
        self.browser.setHtml(f"<body style='font-family:Tahoma;font-size:11px;padding:18px'>Opening page <b>{escape(host)}</b>...</body>")
        self.set_loading(True, f"Opening page {host}...")
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", USER_AGENT)
        if hasattr(request, "setTransferTimeout"):
            request.setTransferTimeout(15000)
        reply = self.net.get(request)
        self._pending_reply = reply
        reply.downloadProgress.connect(self.update_progress)
        reply.finished.connect(lambda: self.finish_fetch(reply, url, record))

    def finish_fetch(self, reply, url, record):
        reply.deleteLater()
        if self._pending_reply is not reply:
            return
        self._pending_reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.render_error(url, reply.errorString(), record)
            return
        raw = bytes(reply.readAll())
        content_type = bytes(reply.rawHeader(b"Content-Type")).decode("ascii", "ignore")
        match = re.search(r"charset=([\w-]+)", content_type, re.I)
        charset = match.group(1) if match else "utf-8"
        try:
            html = raw.decode(charset, errors="replace")
        except LookupError:
            html = raw.decode("utf-8", errors="replace")
        html = re.sub(r"<script\b.*?</script>", "", html, flags=re.I | re.S)
        html = re.sub(r"<iframe\b.*?</iframe>", "", html, flags=re.I | re.S)
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = re.sub(r"<[^>]+>", "", match.group(1)).strip() if match else url
        self.render(url, title or url, html, record)

    def update_progress(self, received, total):
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(received * 100 / total))
        else:
            self.progress.setRange(0, 0)

    def set_loading(self, loading, message="Done"):
        self._loading = loading
        self.stop_btn.setEnabled(loading)
        self.brand.set_active(loading)
        self.status_text.setText(message)
        self.progress.setVisible(loading)
        if loading:
            self.progress.setRange(0, 0)
        self.update_nav_buttons()

    def update_nav_buttons(self):
        self.back_btn.setEnabled(self.hist_index > 0)
        forward_enabled = self.hist_index < len(self.history) - 1
        self.forward_btn.setEnabled(forward_enabled)
        icon_name = "forward_active" if forward_enabled else "forward"
        self.forward_btn.setIcon(ie_icons.icon(icon_name, 24))
        menu = self.back_btn.menu()
        menu.clear()
        for index in range(self.hist_index - 1, max(-1, self.hist_index - 8), -1):
            action = menu.addAction(self.history[index])
            action.triggered.connect(lambda _=False, target=index: self.go_history(target))

    def go_history(self, index):
        if 0 <= index < len(self.history):
            self.hist_index = index
            self.navigate(self.history[index], record=False)

    def go_back(self):
        if self.hist_index > 0:
            self.go_history(self.hist_index - 1)

    def go_forward(self):
        if self.hist_index < len(self.history) - 1:
            self.go_history(self.hist_index + 1)

    def refresh(self):
        if 0 <= self.hist_index < len(self.history):
            self.navigate(self.history[self.hist_index], record=False)

    def stop(self):
        if self._pending_reply:
            reply = self._pending_reply
            self._pending_reply = None
            reply.abort()
            reply.deleteLater()
        self.set_loading(False, "Stopped")
        title = self._current_title or "Microsoft Internet Explorer"
        self.setWindowTitle(f"{title} - Microsoft Internet Explorer")

    def open_link(self, url):
        self.navigate(url.toString())

    def hover_link(self, value):
        url = value.toString() if isinstance(value, QUrl) else str(value)
        self.status_text.setText(url or ("Opening page..." if self._loading else "Done"))

    def _load_image(self, name):
        url = name.toString()
        if not url.startswith(("http://", "https://")):
            url = QUrl(self.address.text()).resolved(name).toString()
        if url in self.image_cache:
            return self.image_cache[url]
        if url not in self._pending_images and not self.work_offline:
            request = QNetworkRequest(QUrl(url))
            request.setRawHeader(b"User-Agent", USER_AGENT)
            reply = self.net.get(request)
            self._pending_images.add(url)
            reply.finished.connect(lambda: self.finish_image(reply, url))
        return QImage()

    def finish_image(self, reply, url):
        reply.deleteLater()
        self._pending_images.discard(url)
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return
        image = QImage()
        if image.loadFromData(bytes(reply.readAll())):
            self.image_cache[url] = image
            self.browser.document().addResource(QTextDocument.ResourceType.ImageResource, QUrl(url), image)
            self.browser.viewport().update()

    def show_explorer(self, kind):
        if self.explorer_bar.isVisible() and self.explorer_bar.kind == kind:
            self.explorer_bar.hide()
        else:
            self.explorer_bar.show_kind(kind)
            self.explorer_bar.show()

    def search_web(self, query):
        if query.strip():
            self.navigate(f"http://www.google.com/search?q={quote_plus(query.strip())}")

    def focus_address(self):
        self.address.setFocus()
        self.address.selectAll()

    def find_on_page(self):
        self.focus_address()
        XPMessageBox.information(self, "Internet Explorer",
                                 "Find focused the Address bar instead. This is not what you asked for, "
                                 "but it is where the text box budget went.")

    def set_text_size(self, value):
        size = {"Largest": 16, "Larger": 14, "Medium": 12, "Smaller": 10, "Smallest": 8}[value]
        self.browser.setStyleSheet(f"QTextBrowser{{background:white;border:0;padding:0;font-size:{size}px}}")
        self.status_text.setText(f"Text size: {value}")

    def view_source(self):
        XPMessageBox.information(self, "Notepad", "Internet Explorer tried to open the source in Notepad, "
                                 "but Notepad is holding an unsaved copy of Untitled.txt.")

    def new_window(self):
        from . import launch
        launch(self.wm, "ie")

    def save_page(self):
        XPMessageBox.information(self, "Save Web Page", "Internet Explorer could not save this Web page.\n\n"
                                 "It contains 73 files, four transparent GIFs, and a table wider than disk space.")

    def print_page(self):
        XPMessageBox.information(self, "Internet Explorer", "Internet Explorer cannot print because no printer is installed.\n\n"
                                 "The page has nevertheless been sent to the printer that is not installed.")

    def page_properties(self):
        protocol = urlparse(self.address.text()).scheme or "Unknown Protocol"
        XPMessageBox.information(self, "Properties", f"Title:  {self._current_title or '(None)'}\n"
                                 f"Address (URL):  {self.address.text()}\nProtocol:  {protocol}\n"
                                 "Type:  HTML Document\nSize:  Unknown (the server became evasive)")

    def toggle_offline(self, checked):
        self.work_offline = checked
        self.status_text.setText("Working Offline" if checked else "Done")

    def add_favorite(self):
        XPMessageBox.information(self, "Add Favorite", f"'{self._current_title}' has been added to Favorites.\n\n"
                                 "It will remain there until the Favorites database remembers it is simulated.")

    def internet_options(self):
        XPMessageBox.information(self, "Internet Options", "Security level for this zone: Medium\n\n"
                                 "Medium permits cookies, ActiveX controls, pop-ups, animated cursors, and personal growth.")

    def tip_of_day(self):
        XPMessageBox.information(self, "Tip of the Day", "Press Alt+Home to return to your home page.\n\n"
                                 "Your home page can also return to you. Clear your cookies occasionally.")

    def netscape_help(self):
        XPMessageBox.information(self, "For Netscape Users", "Welcome. Bookmarks are called Favorites now. "
                                 "Your browser choice has been moved somewhere you cannot immediately see.")

    def about(self):
        XPMessageBox.information(self, "About Internet Explorer", "MacroHard® Internet Explorer\n"
                                 "Version: 6.0.2600.0000.xpclient.010817-1148\nCipher Strength: 128-bit\n"
                                 "Product ID: 55274-OEM-0011903-00102\nUpdate Versions: 0; untouched by history\n\n"
                                 "© 1995-2001 MacroHard Corporation. All rights reserved, especially yours.")

    def not_available(self, label):
        clean = label.replace("&", "").rstrip(".")
        XPMessageBox.information(self, "Internet Explorer", f"Internet Explorer was unable to complete {clean}.\n\n"
                                 "A required component is not installed, is damaged, or has become a toolbar.")
