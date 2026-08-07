#!/usr/bin/env python3
"""validate.py — enforces schema/deck.schema.json rules on a deck.json.

Usage: python src/validate.py decks/<dir>/deck.json
Also imported by render.py. Char limits count AFTER stripping ** markers.
"""
import json
import re
import sys
from pathlib import Path

LIMITS = {
    # hook is capped hard at 55: the cover is a scroll-stopper, not a summary.
    "cover":    {"required": ["hook"], "fields": {"hook": 55, "kicker": 24}},
    "stat":     {"required": ["value", "label"], "fields": {"value": 8, "label": 60, "context": 110, "kicker": 24}},
    "content":  {"required": ["title", "body"], "fields": {"kicker": 24, "title": 44, "body": 200}},
    "mythfact": {"required": ["myth", "fact"], "fields": {"myth": 90, "fact": 160}},
    "cta":      {"required": ["line"], "fields": {"line": 60, "button": 24}},
}
MIDDLE_ROLES = {"stat": ["stat", "content"], "insight": ["content"], "mythfact": ["mythfact", "content"]}
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}_[a-z0-9-]+$")
# A hook that OPENS with a small number is a counted promise ("5 signs ..."), and the
# deck must deliver exactly that many. Guard against 3x / 40% / 2026, which are figures,
# not counts.
COUNT_PROMISE_RE = re.compile(r"^\s*(\d{1,2})(?![%×xX\d])\s+\S")
SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def _strip(s):
    return str(s).replace("**", "")


def validate_deck(deck):
    errors, warnings = [], []
    err, warn = errors.append, warnings.append

    if not isinstance(deck, dict):
        return ["deck.json is not an object"], warnings

    if not ID_RE.match(deck.get("id") or ""):
        warn(f'id "{deck.get("id")}" should match YYYY-MM-DD_slug')
    if deck.get("archetype") not in ("stat", "insight", "mythfact"):
        err(f'archetype "{deck.get("archetype")}" invalid')
    if deck.get("palette") not in ("dark", "light"):
        err(f'palette "{deck.get("palette")}" invalid')

    slides = deck.get("slides") or []
    if len(slides) < 5:
        err(f"needs >=5 slides (cover + content + cta), got {len(slides)}")
    if len(slides) > 20:
        err(f"Instagram cap is 20 slides, got {len(slides)}")
    elif len(slides) > 10:
        warn(f"{len(slides)} slides — 6-10 recommended")
    if slides and slides[0].get("role") != "cover":
        err('slides[0] must be role "cover"')
    if slides and slides[-1].get("role") != "cta":
        err('last slide must be role "cta"')

    for i, s in enumerate(slides, start=1):
        role = s.get("role")
        spec = LIMITS.get(role)
        if not spec:
            err(f'slide {i}: unknown role "{role}"')
            continue
        allowed = MIDDLE_ROLES.get(deck.get("archetype"))
        if 1 < i < len(slides) and allowed and role not in allowed:
            err(f'slide {i}: role "{role}" not allowed in archetype "{deck.get("archetype")}"')
        for f in spec["required"]:
            if not str(s.get(f) or "").strip():
                err(f'slide {i} ({role}): missing required field "{f}"')
        for f, mx in spec["fields"].items():
            if f not in s:
                continue
            text = _strip(s[f])
            if len(text) > mx:
                err(f"slide {i} ({role}).{f}: {len(text)} chars > {mx} — rewrite the copy, never shrink the type")
            if str(s[f]).count("**") % 2 != 0:
                err(f"slide {i} ({role}).{f}: unbalanced ** highlight markers")
            if EMOJI_RE.search(text):
                err(f"slide {i} ({role}).{f}: emojis are forbidden on slides")
            if "!" in text:
                err(f"slide {i} ({role}).{f}: exclamation marks are forbidden on slides")
        if role == "stat" and len(_strip(s.get("value", ""))) > 6:
            warn(f'slide {i}: stat value "{s.get("value")}" >6 chars renders smaller')

    # Reusing one of Zylo's figures for a second, different claim is how invented statistics
    # get in ("+85% operational efficiency" quietly becomes "85% of AI pilots stall").
    seen_values = {}
    for i, s in enumerate(slides, start=1):
        if s.get("role") != "stat" or not s.get("value"):
            continue
        core = re.sub(r"[^0-9]", "", _strip(s["value"]))
        if not core:
            continue
        if core in seen_values:
            j, prev = seen_values[core]
            err(f'slides {j} and {i} both use the figure "{core}" for different claims '
                f'("{prev}" vs "{_strip(s.get("label", ""))}") — a figure belongs to one claim. '
                f"Drop the invented one; never reuse a real number for a second statistic")
        else:
            seen_values[core] = (i, _strip(s.get("label", "")))

    # A count on the cover is a promise the reader can check — deliver it exactly, no padding.
    if slides and slides[0].get("role") == "cover":
        m = COUNT_PROMISE_RE.match(_strip(slides[0].get("hook", "")))
        if m:
            promised, delivered = int(m.group(1)), max(0, len(slides) - 2)
            if 1 < promised <= 20 and promised != delivered:
                err(f'cover promises {promised} but the deck delivers {delivered} — '
                    f"make the counts match exactly (add or cut slides, or change the number)")

    # One ask on the cta, not three. A setup plus an ask ("Two of these true? Let's talk.")
    # is one ask and stays legal; three clauses is a stacked cta.
    if slides and slides[-1].get("role") == "cta":
        line = _strip(slides[-1].get("line", "")).strip()
        if len(SENTENCE_END_RE.findall(line)) > 2:
            err(f'slide {len(slides)} (cta).line stacks multiple asks — a cta makes ONE ask '
                f"(a single setup clause before it is fine)")

    if not str(deck.get("caption") or "").strip():
        err("caption is required")
    elif len(deck["caption"]) > 2200:
        err(f'caption {len(deck["caption"])} chars > 2200 (Instagram limit)')
    tags = deck.get("hashtags") or []
    if not (5 <= len(tags) <= 10):
        warn(f"hashtags: {len(tags)} — aim for 5-10")
    if len(tags) > 30:
        err("hashtags exceed Instagram limit of 30")

    return errors, warnings


def run(file):
    deck = json.loads(Path(file).read_text(encoding="utf-8"))
    errors, warnings = validate_deck(deck)
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    name = Path(file).parent.name
    print(f"\n✗ {name}: {len(errors)} error(s)" if errors else f"\n✓ {name}: valid ({len(warnings)} warning(s))")
    return not errors


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/validate.py decks/<dir>/deck.json")
        sys.exit(1)
    sys.exit(0 if run(sys.argv[1]) else 1)
