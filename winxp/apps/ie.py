from __future__ import annotations

import re

from PyQt6.QtCore import QSize, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QToolBar, QVBoxLayout,
)

from .. import theme
from ..window_manager import XPWindow

HOME_URL = "http://www.msn.com/"
USER_AGENT = b"Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1)"

PAGES = {
    "http://www.msn.com/": (
        "MSN.com - Home",
        """
        <body style="font-family: Tahoma; background:#ffffff; margin:0;">
        <div style="background:#123a7a; padding:14px 20px;">
        <span style="color:white; font-size:26px; font-weight:bold;">MSN</span>
        <span style="color:#bcd7ff; font-size:13px;"> &nbsp; Home&nbsp;&nbsp;News&nbsp;&nbsp;Sports&nbsp;&nbsp;Money</span>
        </div>
        <div style="padding:20px;">
        <h2>Welcome back!</h2>
        <p>Top headlines:</p>
        <ul>
        <li><a href="http://xphome.local/">Set your homepage to XP Home</a></li>
        <li><a href="http://www.example.com/">Visit Example.com</a></li>
        <li><a href="http://www.google.com/">Search the web with Google</a></li>
        <li><a href="http://www.apple.com/">Apple.com</a> -- 1,000 songs. In your pocket.</li>
        <li><a href="http://www.wikipedia.org/">Wikipedia, the free encyclopedia</a></li>
        <li><a href="http://www.macrohard.com/">MacroHard Corporation</a> -- Where do you want to
        go embarrassingly overboard today?</li>
        <li><a href="http://www.geocities.local/xp_fan_page/">Visit Steve's Windows XP Fan Page!</a></li>
        <li><a href="http://xphome.local/changelog.html">What's new in Windows XP</a></li>
        </ul>
        </div>
        </body>
        """,
    ),
    "http://xphome.local/": (
        "Windows XP Home",
        """
        <body style="font-family: Tahoma; background:#a6c8ff; margin:0; padding:24px;">
        <h1 style="color:#123a7a;">Welcome to Windows XP</h1>
        <p>This computer is protected and running smoothly.</p>
        <p><a href="http://www.msn.com/">Go to MSN.com</a></p>
        <p><a href="http://xphome.local/changelog.html">View Windows XP update history</a></p>
        </body>
        """,
    ),
    "http://xphome.local/changelog.html": (
        "Windows XP Update History",
        """
        <body style="font-family: Tahoma; background:#ffffff; margin:0;">
        <div style="background:#123a7a; padding:14px 20px;">
        <span style="color:white; font-size:22px; font-weight:bold;">Windows Update</span>
        <span style="color:#bcd7ff; font-size:13px;"> &nbsp; Update History</span>
        </div>
        <div style="padding:20px;">
        <h2>Recently installed updates</h2>
        <table cellpadding="6" style="border-collapse:collapse; width:100%;">
        <tr style="background:#e8eefc;"><td><b>KB899901</b></td>
        <td>Windows Task Manager is now available from the taskbar and Ctrl+Shift+Esc.</td></tr>
        <tr><td><b>KB899884</b></td>
        <td>Fixed an issue where selecting a desktop icon shortly after creating a new
        file could cause Explorer to stop responding.</td></tr>
        <tr style="background:#e8eefc;"><td><b>KB899867</b></td>
        <td>Menu bars in Notepad, WordPad, Paint, Internet Explorer, and Minesweeper
        now render correctly within the application window on all configurations.</td></tr>
        <tr><td><b>KB899850</b></td>
        <td>Updated message boxes and dialogs throughout the shell to use the Luna
        visual style.</td></tr>
        <tr style="background:#e8eefc;"><td><b>KB899833</b></td>
        <td>The All Programs menu now opens correctly from the Start menu.</td></tr>
        <tr><td><b>KB899812</b></td>
        <td>Added rounded window corners and drop shadows for improved visual
        consistency with the Luna theme.</td></tr>
        <tr style="background:#e8eefc;"><td><b>KB899795</b></td>
        <td>Improved system stability. Ending certain critical system processes
        from Task Manager may still result in a Stop error.</td></tr>
        </table>
        <p style="margin-top:16px;"><a href="http://www.msn.com/">Back to MSN.com</a></p>
        </div>
        </body>
        """,
    ),
    "http://www.google.com/": (
        "Google",
        """
        <body style="font-family: Tahoma; text-align:center; padding-top:60px;">
        <h1 style="font-size:52px;"><span style="color:#4285F4;">G</span><span style="color:#EA4335;">o</span>
        <span style="color:#FBBC05;">o</span><span style="color:#4285F4;">g</span>
        <span style="color:#34A853;">l</span><span style="color:#EA4335;">e</span></h1>
        <p style="color:#888;">About 4,150,000,000 results (0.42 seconds)</p>
        <div style="text-align:left; width:420px; margin:20px auto;">
        <p><a href="http://www.apple.com/">Apple</a><br>
        <span style="color:green;">www.apple.com/</span> -- 1,000 songs. In your pocket.</p>
        <p><a href="http://www.wikipedia.org/">Wikipedia, the free encyclopedia</a><br>
        <span style="color:green;">www.wikipedia.org/</span></p>
        <p><a href="http://www.macrohard.com/">MacroHard Corporation - Home</a><br>
        <span style="color:green;">www.macrohard.com/</span></p>
        <p><a href="http://www.example.com/">Example Domain</a><br>
        <span style="color:green;">www.example.com/</span></p>
        </div>
        <p><a href="http://www.msn.com/">Back to MSN</a></p>
        </body>
        """,
    ),
    "http://www.example.com/": (
        "Example Domain",
        """
        <body style="font-family: Tahoma; padding:24px;">
        <h1>Example Domain</h1>
        <p>This domain is for use in illustrative examples inside documents.</p>
        <p><a href="http://www.msn.com/">Back to MSN</a></p>
        </body>
        """,
    ),
    "http://www.apple.com/": (
        "Apple",
        """
        <body style="font-family: Tahoma; background:#ffffff; margin:0; text-align:center;">
        <div style="background:#f4f4f4; padding:8px; font-size:11px; color:#555;">
        Store &nbsp;|&nbsp; Mac &nbsp;|&nbsp; iPod &nbsp;|&nbsp; QuickTime &nbsp;|&nbsp; Support
        </div>
        <div style="padding:60px 20px;">
        <h1 style="font-size:40px; margin-bottom:4px;">iPod</h1>
        <p style="font-size:20px; color:#444; margin-top:0;">1,000 songs. In your pocket.</p>
        <div style="width:120px; height:200px; background:#e5e5e5; border:2px solid #ccc;
        border-radius:14px; margin:20px auto;"></div>
        <p style="font-size:12px; color:#888;">Requires a Mac. Or a PC. We're flexible now.</p>
        </div>
        <p><a href="http://www.msn.com/">Back to MSN</a></p>
        </body>
        """,
    ),
    "http://www.wikipedia.org/": (
        "Wikipedia, the free encyclopedia",
        """
        <body style="font-family: Georgia, serif; background:#ffffff; margin:0;">
        <div style="background:#f0f0f0; padding:10px 20px; border-bottom:1px solid #ccc;">
        <span style="font-size:22px; font-weight:bold;">Wikipedia</span>
        <span style="font-size:11px; color:#555;"> &nbsp;The Free Encyclopedia</span>
        </div>
        <div style="padding:20px;">
        <h3>From today's featured article</h3>
        <p>The <b>Luna</b> visual style is the default theme of Windows XP, characterized by
        rounded window corners, drop shadows, and a blue taskbar. It replaced the
        Windows Classic theme used since Windows 95. <i>(Full article...)</i></p>
        <h3>Did you know...</h3>
        <ul>
        <li>...that ending <b>csrss.exe</b> in Task Manager will crash the entire operating system?</li>
        <li>...that the Recycle Bin can, in fact, be deleted?</li>
        </ul>
        <p><a href="http://www.msn.com/">Back to MSN</a></p>
        </div>
        </body>
        """,
    ),
    "http://www.macrohard.com/": (
        "MacroHard Corporation",
        """
        <body style="font-family: Tahoma; background:#ffffff; margin:0;">
        <div style="background:#2d5c1f; padding:14px 20px;">
        <span style="color:white; font-size:24px; font-weight:bold;">MacroHard</span>
        <span style="color:#c8e6b8; font-size:12px;"> &nbsp;Corporation</span>
        </div>
        <div style="padding:20px;">
        <h2>Where do you want to go embarrassingly overboard today?</h2>
        <ul>
        <li>MacroHard Office XXL -- now with 4 paperclip assistants</li>
        <li>MacroHard Bob 2: Bob Harder</li>
        <li>MacroHard Windows ME2 -- Millennium Edition Two</li>
        <li>Clippy Enterprise Edition -- "It looks like you're writing a resignation letter."</li>
        </ul>
        <p style="color:#888; font-size:11px;">Not affiliated with any other software company,
        real or imagined.</p>
        <p><a href="http://www.msn.com/">Back to MSN</a></p>
        </div>
        </body>
        """,
    ),
    "http://www.geocities.local/xp_fan_page/": (
        "Steve's Windows XP Fan Page",
        """
        <body style="font-family: Comic Sans MS, Tahoma; background:#000080; color:#00ff00; margin:0; padding:20px;">
        <h1 style="color:#ffff00; text-align:center;">*~*~* WELCOME TO STEVE'S WINDOWS XP FAN PAGE *~*~*</h1>
        <p style="text-align:center; color:#ff00ff;">[ UNDER CONSTRUCTION -- BEST VIEWED AT 800x600 ]</p>
        <hr>
        <p>Hi and welcome!!! This site is dedicated 2 the best OS ever made, Windows XP!!!
        Luna theme 4 life. Sign my guestbook plz.</p>
        <p>Cool links:</p>
        <ul>
        <li><a href="http://www.msn.com/">MSN.com</a></li>
        <li><a href="http://xphome.local/changelog.html">XP Update History</a></li>
        </ul>
        <p style="color:#ffff00;">You are visitor number: <b>001337</b></p>
        <p style="text-align:center; color:#ff00ff;">Site last updated: never</p>
        </body>
        """,
    ),
    "about:blank": ("about:blank", "<body></body>"),
}

ERROR_PAGE = """
<body style="font-family: Tahoma; padding:24px;">
<h2>The page cannot be displayed</h2>
<p>The page you are looking for is not available. It might be temporarily unavailable,
or the connection may have timed out.</p>
<p style="color:#555;">Address: {url}</p>
<p><a href="http://www.msn.com/">Return to MSN.com</a></p>
</body>
"""


class IEWindow(XPWindow):
    def __init__(self, wm):
        super().__init__(wm, title="Windows Internet Explorer", icon_key="ie", size=QSize(760, 560))
        self.history = []
        self.hist_index = -1
        self.net = QNetworkAccessManager(self)
        self._pending_reply = None

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setMenuBar(self._build_menu())
        layout.addWidget(self._build_toolbar())

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.anchorClicked.connect(self._on_link)
        self.browser.setStyleSheet("background: white; border: none;")
        layout.addWidget(self.browser, 1)
        self.set_content_layout(layout)

        self.navigate(HOME_URL)

    def _build_menu(self):
        from PyQt6.QtWidgets import QMenuBar
        bar = QMenuBar()
        theme.style_menubar(bar)
        bar.addMenu("&File")
        bar.addMenu("&Edit")
        bar.addMenu("&View")
        bar.addMenu("&Favorites")
        bar.addMenu("&Tools")
        bar.addMenu("&Help")
        return bar

    def _build_toolbar(self):
        bar = QToolBar()
        bar.setMovable(False)
        self.back_btn = QPushButton("◀ Back")
        self.fwd_btn = QPushButton("Forward ▶")
        home_btn = QPushButton("Home")
        go_btn = QPushButton("Go")
        self.back_btn.clicked.connect(self.go_back)
        self.fwd_btn.clicked.connect(self.go_forward)
        home_btn.clicked.connect(lambda: self.navigate(HOME_URL))
        bar.addWidget(self.back_btn)
        bar.addWidget(self.fwd_btn)
        bar.addWidget(home_btn)

        self.address = QLineEdit()
        self.address.returnPressed.connect(lambda: self.navigate(self.address.text().strip()))
        go_btn.clicked.connect(lambda: self.navigate(self.address.text().strip()))

        return self._wrap(bar, self.address, go_btn)

    def _wrap(self, left_bar, address_edit, go_btn):
        from PyQt6.QtWidgets import QWidget
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(4, 4, 4, 4)
        l.addWidget(left_bar)
        l.addWidget(QLabel("Address"))
        l.addWidget(address_edit, 1)
        l.addWidget(go_btn)
        return w

    def navigate(self, url, record=True):
        if not url:
            return
        if not url.startswith(("http://", "https://", "about:")):
            url = "http://" + url

        if url in PAGES:
            title, html = PAGES[url]
            self._render(url, title, html, record)
            return

        if url.startswith("about:"):
            self._render(url, url, "<body></body>", record)
            return

        self._fetch(url, record)

    def _render(self, url, title, html, record):
        self.browser.setHtml(html)
        self.address.setText(url)
        self.setWindowTitle(f"{title} - Windows Internet Explorer")
        if record:
            self.history = self.history[: self.hist_index + 1]
            self.history.append(url)
            self.hist_index = len(self.history) - 1

    def _fetch(self, url, record):
        self.address.setText(url)
        self.setWindowTitle(f"Connecting to {url}... - Windows Internet Explorer")
        self.browser.setHtml(
            f"<body style=\"font-family:Tahoma;padding:24px;\">"
            f"<p>Opening page http://{QUrl(url).host()} ...</p></body>"
        )
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", USER_AGENT)
        if hasattr(request, "setTransferTimeout"):
            request.setTransferTimeout(15000)
        reply = self.net.get(request)
        self._pending_reply = reply
        reply.finished.connect(lambda: self._on_fetch_done(reply, url, record))

    def _on_fetch_done(self, reply, url, record):
        reply.deleteLater()
        if self._pending_reply is reply:
            self._pending_reply = None
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._render(url, url, ERROR_PAGE.format(url=url), record)
            return

        raw = bytes(reply.readAll())
        html = raw.decode("utf-8", errors="replace")
        html = re.sub(r"<script\b.*?</script>", "", html, flags=re.I | re.S)
        html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = match.group(1).strip() if match else url
        self._render(url, title, html, record)

    def _on_link(self, qurl: QUrl):
        self.navigate(qurl.toString())

    def go_back(self):
        if self.hist_index > 0:
            self.hist_index -= 1
            self.navigate(self.history[self.hist_index], record=False)

    def go_forward(self):
        if self.hist_index < len(self.history) - 1:
            self.hist_index += 1
            self.navigate(self.history[self.hist_index], record=False)
