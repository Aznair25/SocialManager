#!/usr/bin/env python3
"""render.py — deck.json -> 1080x1350 slide PNGs + contact sheet + caption.txt

Usage: python src/render.py decks/<dir>/deck.json
Pipeline: brand/tokens.json -> CSS vars -> HTML template per slide -> headless
Chromium (Playwright) screenshot. Fonts: brand/fonts/*.woff2 if vendored,
otherwise Google Fonts at render time.

Setup (once): pip install -r requirements.txt && playwright install chromium
"""
import base64
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import validate_deck  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOKENS = json.loads((ROOT / "brand" / "tokens.json").read_text(encoding="utf-8"))
BASE_CSS = (ROOT / "templates" / "base.css").read_text(encoding="utf-8")
FONT_DIR = ROOT / "brand" / "fonts"
WEIGHTS = (300, 400, 500, 600)

esc = lambda s: html.escape(str(s), quote=True)  # noqa: E731


def rich(s):
    """Escape, then **word** -> accent span."""
    return re.sub(r"\*\*(.+?)\*\*", r'<span class="hl">\1</span>', esc(s))


def font_head():
    """Local vendored fonts if present, else Google Fonts link."""
    files = {w: FONT_DIR / f"poppins-latin-{w}-normal.woff2" for w in WEIGHTS}
    if all(p.exists() for p in files.values()):
        faces = "".join(
            "@font-face{font-family:'Poppins';font-style:normal;font-weight:%d;"
            "src:url('file://%s') format('woff2');}" % (w, p) for w, p in files.items()
        )
        return "<style>%s</style>" % faces
    return (
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
        '<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">'
    )


def logo_url():
    """The logotype mask as a data URI — set_content() pages have an about:blank
    origin and cannot load file:// subresources (same reason as the contact sheet)."""
    p = ROOT / "brand" / TOKENS["identity"]["logo"]
    if not p.exists():
        raise RenderError(f"logo asset missing: {p.relative_to(ROOT)}")
    return "url(data:image/png;base64,%s)" % base64.b64encode(p.read_bytes()).decode("ascii")


def css_vars(palette):
    c = TOKENS["color"]
    dark = palette == "dark"
    v = {
        "--bg": c["bgDark"] if dark else c["bgLight"],
        "--fg": c["fgOnDark"] if dark else c["fgOnLight"],
        "--soft": c["fgSoftOnDark"] if dark else c["fgSoftOnLight"],
        "--muted": c["fgMutedOnDark"] if dark else c["fgMutedOnLight"],
        "--numeral": c["numeralOnDark"] if dark else c["numeralOnLight"],
        "--accent": c["accentPurple"],
        "--hl": c["accentLavender"] if dark else c["accentPurple"],
        "--chip-border": c["borderOnDark"] if dark else c["borderOnLight"],
        "--chip-bg": c["chipBgOnDark"] if dark else c["chipBgOnLight"],
        "--glow": c["glowPurple"],
        "--glow-2": c["glowLavender"],
        "--arc": c["arcOnDark"] if dark else c["arcOnLight"],
        "--pill-bg": c["fgOnDark"] if dark else c["fgOnLight"],
        "--pill-fg": c["bgDark"] if dark else c["bgLight"],
        "--r-card": TOKENS["radius"]["card"],
        "--r-pill": TOKENS["radius"]["pill"],
        "--pad": "%dpx" % TOKENS["canvas"]["pad"],
        "--logo": logo_url(),
    }
    return ":root{%s}" % ";".join("%s:%s" % kv for kv in v.items())


def slide_html(deck, slide, i, total):
    tpl = (ROOT / "templates" / ("%s.html" % slide["role"])).read_text(encoding="utf-8")
    ident = TOKENS["identity"]
    data = {
        "paletteClass": deck["palette"],
        "wordmark": esc(ident["wordmark"]),
        "handle": esc(ident["handle"]),
        "site": esc(ident["site"]),
        "email": esc(ident["email"]),
        "index": "%02d/%02d" % (i + 1, total),
        "kicker": esc(slide.get("kicker", "")),
        "hook": rich(slide.get("hook", "")),
        "value": rich(slide.get("value", "")),
        "valueLen": str(len(str(slide.get("value", "")).replace("**", ""))),
        "label": rich(slide.get("label", "")),
        "context": rich(slide.get("context", "")),
        "title": rich(slide.get("title", "")),
        "body": rich(slide.get("body", "")),
        "myth": rich(slide.get("myth", "")),
        "fact": rich(slide.get("fact", "")),
        "line": rich(slide.get("line", "")),
        "button": esc(slide.get("button") or ident["defaultButton"]),
    }
    filled = re.sub(r"\{\{(\w+)\}\}", lambda m: data.get(m.group(1), ""), tpl)
    return (
        '<!doctype html><html><head><meta charset="utf-8">%s<style>%s\n%s</style></head><body>%s</body></html>'
        % (font_head(), css_vars(deck["palette"]), BASE_CSS, filled)
    )


def contact_sheet_html(deck, png_paths):
    cols, thumb_w, gap, pad, header = 4, 250, 20, 32, 88
    thumb_h = round(thumb_w * 1350 / 1080)
    rows = -(-len(png_paths) // cols)
    width = pad * 2 + cols * thumb_w + (cols - 1) * gap
    height = header + pad + rows * thumb_h + (rows - 1) * gap + pad + pad // 2
    # Inline as data URIs: set_content() pages have an about:blank origin, from
    # which Chromium refuses to load file:// subresources (thumbnails come out broken).
    figs = "".join(
        '<figure><img src="data:image/png;base64,%s" width="%d" height="%d"><figcaption>%02d</figcaption></figure>'
        % (base64.b64encode(p.read_bytes()).decode("ascii"), thumb_w, thumb_h, i + 1)
        for i, p in enumerate(png_paths)
    )
    css = (
        "*{margin:0;box-sizing:border-box}body{width:%dpx;background:%s;font-family:'Poppins',sans-serif;padding:%dpx}"
        ".bar{height:%dpx;display:flex;align-items:center;justify-content:space-between;color:#fff}"
        ".bar .t{font-size:26px;font-weight:600}.bar .m{font-size:20px;color:%s}"
        ".grid{display:grid;grid-template-columns:repeat(%d,%dpx);gap:%dpx;margin-top:%dpx}"
        "figure{position:relative}img{display:block;border-radius:8px}"
        "figcaption{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.55);color:#fff;font-size:16px;padding:2px 10px;border-radius:999px}"
        % (width, TOKENS["color"]["bgDarkSection"], pad, header - pad, TOKENS["color"]["fgMutedOnDark"], cols, thumb_w, gap, pad // 2)
    )
    body = (
        '<div class="bar"><span class="t">%s</span><span class="m">%s · %s · %d slides · review before upload</span></div><div class="grid">%s</div>'
        % (esc(deck["id"]), deck["archetype"], deck["palette"], len(png_paths), figs)
    )
    html_doc = '<!doctype html><html><head><meta charset="utf-8">%s<style>%s</style></head><body>%s</body></html>' % (font_head(), css, body)
    return html_doc, width, height


class RenderError(RuntimeError):
    """Raised when a deck cannot be rendered. Callers (CLI, API) decide how to surface it."""


def render_deck(deck_path, on_event=None):
    """Render deck.json -> slides/NN.png + contact-sheet.png + caption.txt.

    Returns the list of slide PNG paths. on_event(str) receives progress lines.
    """
    emit = on_event or (lambda m: print(m))
    deck_path = Path(deck_path).resolve()
    deck_dir = deck_path.parent
    deck = json.loads(deck_path.read_text(encoding="utf-8"))

    errors, warnings = validate_deck(deck)
    for w in warnings:
        emit(f"  WARN  {w}")
    if errors:
        for e in errors:
            emit(f"  ERROR {e}")
        raise RenderError("validation failed — not rendering: " + "; ".join(errors))

    slides_dir = deck_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    total = len(deck["slides"])
    pngs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": TOKENS["canvas"]["width"], "height": TOKENS["canvas"]["height"]}, device_scale_factor=1)
        for i, slide in enumerate(deck["slides"]):
            page.set_content(slide_html(deck, slide, i, total), wait_until="load")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(120)
            out = slides_dir / ("%02d.png" % (i + 1))
            page.screenshot(path=str(out))
            pngs.append(out)
            emit(f"  ✓ slide {i + 1}/{total} ({slide['role']})")

        sheet_html, w, h = contact_sheet_html(deck, pngs)
        page.set_viewport_size({"width": w, "height": h})
        page.set_content(sheet_html, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)  # let file:// thumbnails decode
        page.screenshot(path=str(deck_dir / "contact-sheet.png"), full_page=True)
        emit("  ✓ contact-sheet.png")
        browser.close()

    tags = " ".join(t if t.startswith("#") else "#" + t for t in deck.get("hashtags", []))
    (deck_dir / "caption.txt").write_text(deck["caption"].strip() + "\n\n" + tags + "\n", encoding="utf-8")
    emit("  ✓ caption.txt")
    emit(f"\n✓ {deck['id']}: {total} slides rendered to {slides_dir.relative_to(ROOT)}")
    return pngs


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/render.py decks/<dir>/deck.json")
        sys.exit(1)
    try:
        render_deck(sys.argv[1])
    except RenderError as e:
        sys.exit(f"\n✗ {e}")


if __name__ == "__main__":
    main()
