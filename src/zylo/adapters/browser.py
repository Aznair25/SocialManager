"""Playwright implementations of the screenshot and page-fetch ports.

Both share the same headless Chromium that `playwright install chromium` puts in
place. Pages are fetched plainly, as a normal browser would; nothing here works
around a login wall or a paywall.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..domain.errors import ExtractError

USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Containers most publishing platforms use for the body copy, best first.
CONTENT_SELECTORS = [
    "article", "main", "[role='main']",
    ".post-content", ".entry-content", ".article-content", ".article-body",
    ".post-body", ".blog-post", "#content", ".content",
]

_PAGE_SCRIPT = r"""(sels) => {
  const meta = n => (document.querySelector(`meta[property='${n}'], meta[name='${n}']`) || {}).content || '';
  document.querySelectorAll('script,style,noscript,nav,header,footer,aside,form,svg').forEach(e => e.remove());
  // Score candidates on their text with whitespace collapsed, but keep the original.
  // Single-page app shells are mostly newlines and indentation, and a raw-length
  // comparison lets that padding beat the container that holds the actual copy.
  let best = '', bestScore = 0;
  for (const s of sels) {
    for (const el of document.querySelectorAll(s)) {
      const raw = (el.innerText || '').trim();
      const score = raw.replace(/\s+/g, ' ').length;
      if (score > bestScore) { best = raw; bestScore = score; }
    }
  }
  const body = (document.body ? document.body.innerText : '') || '';
  return { title: (document.title || '').trim(), ogTitle: meta('og:title'),
           ogDesc: meta('og:description'), desc: meta('description'),
           best, body, url: location.href };
}"""


@dataclass(frozen=True)
class RawPage:
    """What a fetch yields, before any cleaning or judgement about usefulness."""

    url: str
    title: str = ""
    og_title: str = ""
    og_description: str = ""
    description: str = ""
    best: str = ""
    body: str = ""

    @classmethod
    def from_evaluation(cls, data: dict) -> "RawPage":
        return cls(url=data.get("url", ""), title=data.get("title", ""),
                   og_title=data.get("ogTitle", ""), og_description=data.get("ogDesc", ""),
                   description=data.get("desc", ""), best=data.get("best", ""),
                   body=data.get("body", ""))


class PlaywrightScreenshotSession:
    """A live page. HTML goes in, PNGs come out."""

    def __init__(self, page):
        self._page = page

    def resize(self, width: int, height: int) -> None:
        self._page.set_viewport_size({"width": width, "height": height})

    def capture(self, html: str, path: Path, full_page: bool = False, settle_ms: int = 120) -> Path:
        self._page.set_content(html, wait_until="load")
        self._page.evaluate("document.fonts.ready")
        self._page.wait_for_timeout(settle_ms)
        self._page.screenshot(path=str(path), full_page=full_page)
        return Path(path)


class PlaywrightScreenshotEngine:
    """Implements `ScreenshotEngine`. One browser per session, closed on exit."""

    @contextmanager
    def session(self, width: int, height: int):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": width, "height": height},
                                        device_scale_factor=1)
                yield PlaywrightScreenshotSession(page)
            finally:
                browser.close()


class PlaywrightPageFetcher:
    """Implements `PageFetcher`. Renders the page, then reads the DOM.

    Most publishing platforms render their body copy with JavaScript, so a plain
    HTTP GET returns an empty shell — hence a real browser.
    """

    def __init__(self, timeout_ms: int = 30000, settle_ms: int = 1800):
        self._timeout_ms = timeout_ms
        self._settle_ms = settle_ms

    def fetch(self, url: str) -> RawPage:
        from playwright.sync_api import Error as PWError
        from playwright.sync_api import TimeoutError as PWTimeout
        from playwright.sync_api import sync_playwright

        netloc = urlparse(url).netloc
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                context = browser.new_context(user_agent=USER_AGENT,
                                              viewport={"width": 1280, "height": 2000},
                                              locale="en-GB")
                page = context.new_page()
                try:
                    response = page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
                    # An error page still has readable text; without this a 404 becomes "source material".
                    if response and response.status >= 400:
                        raise ExtractError(f"{netloc} returned HTTP {response.status} for that URL — "
                                           f"check the link is correct and public.")
                    page.wait_for_timeout(self._settle_ms)  # let client-rendered body copy settle
                except PWTimeout:
                    raise ExtractError(f"{netloc} took too long to respond. "
                                       f"Try again, or paste the text in by hand.") from None
                except PWError as exc:
                    raise ExtractError(f"Could not open that URL "
                                       f"({str(exc).splitlines()[0][:120]}).") from None
                return RawPage.from_evaluation(page.evaluate(_PAGE_SCRIPT, CONTENT_SELECTORS))
            finally:
                browser.close()
