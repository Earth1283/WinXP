from __future__ import annotations

from PyQt6.QtCore import QSize, QUrl
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextBrowser, QToolBar, QVBoxLayout,
)

from ..window_manager import XPWindow

HOME_URL = "http://www.msn.com/"

PAGES = {
    "http://www.msn.com/": (
        "MSN.com - Home",
        """
        <body style="font-family: Tahoma; background:#ffffff; margin:0;">
        <div style="background:linear-gradient(#0b3d91,#173f8a); padding:14px 20px;">
        <span style="color:white; font-size:26px; font-weight:bold;">MSN</span>
        <span style="color:#bcd7ff; font-size:13px;"> &nbsp; Home&nbsp;&nbsp;News&nbsp;&nbsp;Sports&nbsp;&nbsp;Money</span>
        </div>
        <div style="padding:20px;">
        <h2>Welcome back!</h2>
        <p>Top headlines from around the simulated web:</p>
        <ul>
        <li><a href="http://xphome.local/">Set your homepage to XP Home</a></li>
        <li><a href="http://www.example.com/">Visit Example.com</a></li>
        <li><a href="http://www.google.com/">Search the web with Google</a></li>
        </ul>
        <p style="color:#888;">This is a simulated offline page inside Windows XP (Simulated Edition).</p>
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
        </body>
        """,
    ),
    "http://www.google.com/": (
        "Google",
        """
        <body style="font-family: Tahoma; text-align:center; padding-top:80px;">
        <h1 style="font-size:52px;"><span style="color:#4285F4;">G</span><span style="color:#EA4335;">o</span>
        <span style="color:#FBBC05;">o</span><span style="color:#4285F4;">g</span>
        <span style="color:#34A853;">l</span><span style="color:#EA4335;">e</span></h1>
        <p style="color:#888;">(simulated search - no network access in this sandbox)</p>
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
        title, html = PAGES.get(url, (url, ERROR_PAGE.format(url=url)))
        self.browser.setHtml(html)
        self.address.setText(url)
        self.setWindowTitle(f"{title} - Windows Internet Explorer")
        if record:
            self.history = self.history[: self.hist_index + 1]
            self.history.append(url)
            self.hist_index = len(self.history) - 1

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
