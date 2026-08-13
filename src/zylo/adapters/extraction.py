"""URL to reference material.

The fetching is a port (`PageFetcher`); everything here — cleaning, judging
whether a page returned an article or a sign-in wall, deciding the title — is
pure, and is where nearly all the behaviour lives. That split is what makes the
extractor testable without a browser.
"""
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from ..domain.errors import ExtractError
from ..domain.source import SourceMaterial
from ..reporting import ProgressReporter, resolve
from .browser import RawPage

# Nav/chrome lines that survive selector extraction on some templates.
JUNK_LINE = re.compile(
    r"^(sign in|sign up|join now|log ?in|register|subscribe|share|follow|menu|search|"
    r"cookie|accept all|privacy policy|terms|skip to content|home|about|contact|"
    r"\d+ (min|minute) read|share this|related posts?|comments?)\b", re.I)

WALL_MARKERS = (
    "sign in to see", "join now to see", "sign up to see", "/authwall",
    "please enable javascript", "enable cookies", "you must log in",
    "verify you are human", "checking your browser", "access denied",
    "attention required", "subscribe to read", "this content is available to",
    "may have been moved", "no longer exist", "page not found", "page doesn't exist",
)


@runtime_checkable
class PageFetcher(Protocol):
    def fetch(self, url: str) -> RawPage:
        ...


@dataclass(frozen=True)
class ExtractionLimits:
    max_chars: int = 12000
    min_usable: int = 220
    #: Prose needed to be worth a 6-9 slide deck. Set above the ~250 chars that error and
    #: directory pages produce, so "page not found" never becomes source material.
    min_prose: int = 500
    #: A line this long is a sentence regardless of how it is punctuated.
    prose_line_chars: int = 60


#: A line that closes on sentence punctuation is a sentence even when it is short.
#: LinkedIn's house style is one short line per thought — "Speed matters." — so a
#: length-only test reads a perfectly good 2,900-character post as navigation chrome.
SENTENCE_END_RE = re.compile(r"[.!?…][\"'’”)\]]?$")


def prose_chars(text: str, long_line: int = 60) -> int:
    """Characters that read as prose rather than as navigation.

    Real articles and posts are made of sentences. Directory, feed and sign-in
    pages are made of fragments and labels ("13K posts", "See all"), which survive
    line filtering but are not source material. A line counts if it is long enough
    to be a sentence, *or* if it ends like one.
    """
    total = 0
    for line in (text or "").splitlines():
        line = line.strip()
        if len(line) >= long_line or SENTENCE_END_RE.search(line):
            total += len(line)
    return total


def clean_body(text: str) -> str:
    """Collapse whitespace and drop nav/boilerplate lines."""
    lines, seen = [], set()
    for raw in (text or "").splitlines():
        line = re.sub(r"[ \t ]+", " ", raw).strip()
        if not line or JUNK_LINE.match(line):
            continue
        # Single words and stray UI labels are almost always chrome, not prose.
        if len(line) < 3 or (len(line) < 25 and " " not in line):
            continue
        if line.lower() in seen:      # repeated nav items
            continue
        seen.add(line.lower())
        lines.append(line)
    return "\n".join(lines).strip()


def clean_title(title: str, netloc: str) -> str:
    """Drop the trailing site name — 'Foo - Wikipedia' becomes 'Foo'.

    The title becomes the deck's topic and slug when no topic is given, so the
    suffix would otherwise end up in the filename. Social platforms put the whole
    post body (plus the author) in og:title, so that gets flattened too.
    """
    title = re.sub(r"\s+", " ", (title or "")).strip()
    host = re.sub(r"[^a-z0-9]", "", netloc.lower().replace("www.", ""))
    for sep in (" | ", " – ", " — ", " - ", " · "):
        if sep in title:
            head, _, tail = title.rpartition(sep)
            tag = re.sub(r"[^a-z0-9]", "", tail.lower())
            # Only strip it if the tail really is the site's name, not a real subtitle.
            if head.strip() and tag and len(tail) <= 30 and (tag in host or host.startswith(tag)):
                title = head.strip()
    # A long post-body title reduces to its opening sentence; the trailing
    # "| Author Name" that social platforms append falls away with it.
    if len(title) > 100:
        first = re.split(r"(?<=[.!?])\s", title)[0].strip()
        title = first if 15 <= len(first) <= 100 else title[:100].rsplit(" ", 1)[0]
    return title


class WebPageSourceExtractor:
    """Implements `SourceExtractor`: a URL in, usable article text out."""

    def __init__(self, fetcher: PageFetcher, limits: ExtractionLimits | None = None):
        self._fetcher = fetcher
        self._limits = limits or ExtractionLimits()

    def extract(self, url: str, reporter: ProgressReporter | None = None) -> SourceMaterial:
        report = resolve(reporter)
        requested = self._validated_url(url)

        report.emit(f"  Reading {requested.netloc}")
        page = self._fetcher.fetch(requested.geturl())

        text = self._best_text(page)
        title = clean_title(page.og_title or page.title, requested.netloc)
        text = self._merge_social_summary(page, text)

        self._reject_if_unusable(page, requested, text)
        text = self._truncate(text)

        report.emit(f"  Extracted {len(text)} characters" + (f" — “{title[:60]}”" if title else ""))
        return SourceMaterial(text=text, url=requested.geturl(), title=title)

    # -- steps --------------------------------------------------------------

    @staticmethod
    def _validated_url(url: str):
        parsed = urlparse((url or "").strip())
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ExtractError("That does not look like a web address. "
                               "Use a full http:// or https:// URL.")
        return parsed

    @staticmethod
    def _best_text(page: RawPage) -> str:
        body = clean_body(page.body)
        text = clean_body(page.best)
        # A selector that grabbed a sidebar loses to the whole body.
        return body if len(text) < len(body) / 3 else text

    @staticmethod
    def _merge_social_summary(page: RawPage, text: str) -> str:
        """og:description carries the post text on LinkedIn and most social
        platforms, and is often all that is served without an account."""
        social = clean_body(page.og_description or page.description)
        if social and social.lower() not in text.lower():
            return (social + "\n" + text).strip()
        return text

    def _reject_if_unusable(self, page: RawPage, requested, text: str) -> None:
        """Refuse pages that returned chrome rather than content.

        Length alone is not enough — a sign-in page can be long. Measuring how much
        of the text reads as sentences is what tells an article or a post apart from
        a directory listing.
        """
        prose = prose_chars(text, self._limits.prose_line_chars)
        if len(text) >= self._limits.min_usable and prose >= self._limits.min_prose:
            return

        haystack = (text[:3000] + " " + page.url).lower()
        landed = urlparse(page.url)
        redirected = landed.path.rstrip("/") != requested.path.rstrip("/")
        hit = next((m for m in WALL_MARKERS if m in haystack), None)
        why = (f" — the page says “{hit}”" if hit else
               f" — it redirected to {landed.path or '/'}" if redirected else
               " — the page returned navigation and links, not an article")
        raise ExtractError(
            f"{requested.netloc} did not return readable article text{why}. "
            "Check the link is public, or copy the text and paste it into the source box instead."
        )

    def _truncate(self, text: str) -> str:
        if len(text) <= self._limits.max_chars:
            return text
        return text[:self._limits.max_chars].rsplit("\n", 1)[0]
