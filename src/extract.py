#!/usr/bin/env python3
"""extract.py — pull the readable text out of a blog post or LinkedIn post URL.

The text is *reference material only*: generate.py mines it for points and writes
the deck from scratch in Zylo's voice. Nothing is copied through verbatim.

Uses the Chromium that Playwright already installs, because most publishing
platforms render their body copy with JavaScript. Pages are fetched plainly, as
a normal browser would; nothing here works around a login wall or paywall. When
a site refuses to serve the text (LinkedIn usually does unless the post is fully
public), the caller is told to paste the text in by hand instead.

Usage: python src/extract.py <url>
"""
import re
import sys
from urllib.parse import urlparse

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

MAX_CHARS = 12000
MIN_USABLE = 220
# Prose needed to be worth a 6-9 slide deck. Set above the ~250 chars that error and
# directory pages produce, so "page not found" never becomes source material.
MIN_PROSE = 500

# Containers most publishing platforms use for the body copy, best first.
CONTENT_SELECTORS = [
    "article", "main", "[role='main']",
    ".post-content", ".entry-content", ".article-content", ".article-body",
    ".post-body", ".blog-post", "#content", ".content",
]

WALL_MARKERS = (
    "sign in to see", "join now to see", "sign up to see", "/authwall",
    "please enable javascript", "enable cookies", "you must log in",
    "verify you are human", "checking your browser", "access denied",
    "attention required", "subscribe to read", "this content is available to",
    "may have been moved", "no longer exist", "page not found", "page doesn't exist",
)

# Nav/chrome lines that survive selector extraction on some templates.
JUNK_LINE = re.compile(
    r"^(sign in|sign up|join now|log ?in|register|subscribe|share|follow|menu|search|"
    r"cookie|accept all|privacy policy|terms|skip to content|home|about|contact|"
    r"\d+ (min|minute) read|share this|related posts?|comments?)\b", re.I)


class ExtractError(RuntimeError):
    """Raised when a URL cannot be turned into usable text."""


def _clean(text):
    """Collapse whitespace and drop nav/boilerplate lines."""
    lines, seen = [], set()
    for raw in (text or "").splitlines():
        line = re.sub(r"[ \t ]+", " ", raw).strip()
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


def _clean_title(title, netloc):
    """Drop the trailing site name — 'Foo - Wikipedia' becomes 'Foo'.

    The title becomes the deck's topic and slug when no topic is given, so the
    suffix would otherwise end up in the filename.
    """
    # Social platforms put the whole post body (plus the author) in og:title, so
    # flatten it first — this ends up as the deck's topic and slug.
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


def extract_from_url(url, on_event=None, timeout_ms=30000):
    """Return {url, title, text}. Raises ExtractError with an actionable message."""
    emit = on_event or (lambda m: print(m))

    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ExtractError("That does not look like a web address. Use a full http:// or https:// URL.")
    url = parsed.geturl()

    from playwright.sync_api import Error as PWError
    from playwright.sync_api import TimeoutError as PWTimeout
    from playwright.sync_api import sync_playwright

    emit(f"  Reading {parsed.netloc}")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 2000},
                                  locale="en-GB")
        page = ctx.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            # An error page still has readable text; without this a 404 becomes "source material".
            if resp and resp.status >= 400:
                browser.close()
                raise ExtractError(
                    f"{parsed.netloc} returned HTTP {resp.status} for that URL — check the link is correct and public."
                )
            page.wait_for_timeout(1800)  # let client-rendered body copy settle
        except PWTimeout:
            browser.close()
            raise ExtractError(f"{parsed.netloc} took too long to respond. Try again, or paste the text in by hand.")
        except PWError as e:
            browser.close()
            raise ExtractError(f"Could not open that URL ({str(e).splitlines()[0][:120]}).")

        data = page.evaluate(
            """(sels) => {
              const meta = n => (document.querySelector(`meta[property='${n}'], meta[name='${n}']`) || {}).content || '';
              document.querySelectorAll('script,style,noscript,nav,header,footer,aside,form,svg').forEach(e => e.remove());
              let best = '', bestLen = 0;
              for (const s of sels) {
                for (const el of document.querySelectorAll(s)) {
                  const t = (el.innerText || '').trim();
                  if (t.length > bestLen) { best = t; bestLen = t.length; }
                }
              }
              const body = (document.body ? document.body.innerText : '') || '';
              return { title: (document.title || '').trim(), ogTitle: meta('og:title'),
                       ogDesc: meta('og:description'), desc: meta('description'),
                       best, body, url: location.href };
            }""",
            CONTENT_SELECTORS,
        )
        browser.close()

    body_clean = _clean(data["body"])
    text = _clean(data["best"])
    if len(text) < len(body_clean) / 3:   # selector grabbed a sidebar, not the article
        text = body_clean

    title = _clean_title(data["ogTitle"] or data["title"], parsed.netloc)
    # og:description carries the post text on LinkedIn and most social platforms,
    # and is often all that is served without an account.
    social = _clean(data["ogDesc"] or data["desc"])
    if social and social.lower() not in text.lower():
        text = (social + "\n" + text).strip()

    haystack = (text[:3000] + " " + data["url"]).lower()
    # Real articles are made of paragraphs. Directory, feed and sign-in pages are made of
    # short nav fragments ("13K posts"), which survive line filtering but are not source
    # material — measuring prose separately is what tells the two apart.
    prose = "\n".join(l for l in text.splitlines() if len(l) >= 60)
    landed = urlparse(data["url"])
    redirected = landed.path.rstrip("/") != parsed.path.rstrip("/")

    if len(text) < MIN_USABLE or len(prose) < MIN_PROSE:
        hit = next((m for m in WALL_MARKERS if m in haystack), None)
        why = (f" — the page says “{hit}”" if hit else
               f" — it redirected to {landed.path or '/'}" if redirected else
               " — the page returned navigation and links, not an article")
        raise ExtractError(
            f"{parsed.netloc} did not return readable article text{why}. "
            "Check the link is public, or copy the text and paste it into the source box instead."
        )

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit("\n", 1)[0]

    emit(f"  Extracted {len(text)} characters" + (f" — “{title[:60]}”" if title else ""))
    return {"url": url, "title": title, "text": text}


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/extract.py <url>")
        sys.exit(1)
    try:
        r = extract_from_url(sys.argv[1])
    except ExtractError as e:
        sys.exit(f"✗ {e}")
    print(f"\n--- {r['title']} ---\n{r['text'][:2000]}")


if __name__ == "__main__":
    main()
