from html import escape
from pathlib import Path


HOME_URL = "http://www.msn.com/"
PAGES_DIR = Path(__file__).with_name("ie_pages")


def load_page(filename):
    return (PAGES_DIR / filename).read_text(encoding="utf-8")


PAGES = {
    HOME_URL: ("MSN.com", "msn.html"),
    "http://xphome.local/": ("Welcome to Windows XP", "xp_home.html"),
    "http://xphome.local/changelog.html": ("Windows Update", "windows_update.html"),
    "http://www.google.com/": ("Google", "google.html"),
    "http://www.example.com/": ("Example Web Site", "example.html"),
    "http://www.apple.com/": ("Apple", "apple.html"),
    "http://www.wikipedia.org/": ("Wikipedia, the free encyclopedia", "wikipedia.html"),
    "http://www.microsoft.com/": ("Microsoft.com Home Page", "microsoft.html"),
    "http://www.geocities.local/xp_fan_page/": ("Steve's Windows XP Fan Page", "geocities.html"),
    "about:blank": ("about:blank", "blank.html"),
}


def static_page(url):
    title, filename = PAGES[url]
    return title, load_page(filename)


def error_page(detail):
    detail_html = f"<p><font color='#777'>{escape(detail)}</font></p>"
    return load_page("error.html").replace("{{detail}}", detail_html)


def search_results(query):
    safe_query = escape(query)
    return (load_page("search_results.html")
            .replace("{{query}}", safe_query)
            .replace("{{QUERY}}", safe_query.upper()))
