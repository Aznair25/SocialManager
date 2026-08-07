#!/usr/bin/env python3
"""generate.py — topic -> validated deck.json via the OpenAI API.

The LLM is the content brain ONLY: it writes slides/caption/hashtags.
Identity fields (id, archetype, palette, pillar, cta_target) are set by code.
Output is validated with validate.py; on errors the model gets the errors
back and must return corrected JSON (max 3 attempts).

Usage:
  python src/generate.py "How AI agents cut support costs" --archetype insight
  python src/generate.py "AI ROI numbers" --archetype stat --palette dark --render

Setup: cp .env.example .env  (add OPENAI_API_KEY), pip install -r requirements.txt
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import LIMITS, validate_deck  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gpt-5.1"

ARCHETYPE_GUIDE = {
    "stat": (
        "Slides: 1 cover (hook + optional kicker), then 3-6 'stat' slides "
        "(value like '+85%', '3×', '−40%', '50+'; label; optional context sentence), then 1 cta. "
        "Prefer Zylo's real figures where relevant: +85% operational efficiency, 3× faster deployment, "
        "−40% manual processes, 50+ companies, 35+ engineers, founded 2021. Never invent client names."
    ),
    "insight": (
        "Slides: 1 cover (hook + optional kicker), then 4-7 'content' slides "
        "(kicker like 'sign 01' or a short series tag; title; body of 1-2 sentences), then 1 cta. "
        "One idea per slide. Bodies concrete and operational, not abstract."
    ),
    "mythfact": (
        "Slides: 1 cover (hook + optional kicker), then 3-5 'mythfact' slides "
        "(myth: short belief stated plainly; fact: the correction, specific and confident), then 1 cta."
    ),
}

VOICE = (
    "Voice: outcome-led, metric-heavy, enterprise-calm. Short declarative sentences. "
    "Numbers do the talking. Forbidden: emojis, exclamation marks, hype words "
    "('revolutionary', 'game-changing', 'unlock', 'supercharge'), rhetorical questions on every slide, "
    "clickbait. British-neutral English. Em dashes allowed."
)


def load_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def system_prompt(archetype):
    return (
        "You write Instagram carousel deck specs for Zylo, an AI consultancy for enterprises "
        "(wearezylo.com, @wearezylotech). Zylo builds custom AI agents, automation systems and software.\n\n"
        + VOICE + "\n\n"
        "Archetype '" + archetype + "': " + ARCHETYPE_GUIDE[archetype] + "\n\n"
        "HARD character limits per field (counted after removing ** markers) — exceeding any limit is a failure:\n"
        + json.dumps({r: s["fields"] for r, s in LIMITS.items()}, indent=2) + "\n\n"
        "Emphasis: you MAY wrap one key phrase in the cover hook with **double asterisks** (renders as accent color). "
        "Use at most one highlight in the whole deck.\n\n"
        "The cta slide: field 'line' (a calm closing question or statement, <=60 chars). Do not add a button field. "
        "The renderer already prints 'wearezylo.com' and 'contact@wearezylo.com' beneath the button — "
        "never repeat a URL or email address in 'line', and never invent a different one.\n\n"
        "Caption: 1 hook line, blank line, 2-3 short lines expanding the promise, blank line, "
        "one CTA line ending with 'wearezylo.com'. No emojis in the caption either.\n"
        "Hashtags: 5-10 strings, no '#' prefix, mixing niche and reach (e.g. AIConsulting, EnterpriseAI).\n\n"
        "Return ONLY a JSON object, no markdown fences, no commentary, with exactly these keys:\n"
        '{ "slides": [ {"role": "cover", ...}, ... ], "caption": "...", "hashtags": ["..."] }'
    )


def extract_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


def slugify(topic, override=None):
    if override:
        return override
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s[:40].rstrip("-") or "deck"


class GenerationError(RuntimeError):
    """Raised when the model cannot produce a valid deck. Callers (CLI, API) decide how to surface it."""


def generate(topic, archetype, palette, slug=None, pillar=None, notes=None, max_attempts=3, on_event=None):
    """Return a validated deck dict. on_event(str) receives progress lines (defaults to print)."""
    emit = on_event or (lambda m: print(m))
    try:
        from openai import OpenAI
    except ImportError:
        raise GenerationError("Missing dependency: pip install -r requirements.txt")
    if not os.environ.get("OPENAI_API_KEY"):
        raise GenerationError("OPENAI_API_KEY not set — cp .env.example .env and add your key")

    client = OpenAI()
    model = os.environ.get("ZYLO_MODEL", DEFAULT_MODEL)
    today = datetime.date.today().isoformat()
    deck_id = f"{today}_{slugify(topic, slug)}"

    user_msg = f"Topic: {topic}\nPalette: {palette} (affects tone of visuals only, not copy)."
    if notes:
        user_msg += f"\nDirection notes: {notes}"
    messages = [{"role": "system", "content": system_prompt(archetype)},
                {"role": "user", "content": user_msg}]

    for attempt in range(1, max_attempts + 1):
        raw = _complete(client, model, messages)
        try:
            partial = extract_json(raw)
        except (ValueError, json.JSONDecodeError) as e:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"Output was not parseable JSON ({e}). Return the full corrected JSON object only."}]
            emit(f"  attempt {attempt}: unparseable output, retrying")
            continue

        deck = {
            "id": deck_id,
            "archetype": archetype,
            "palette": palette,
            "topic": topic,
            "pillar": pillar or "",
            "cta_target": "wearezylo.com",
            "slides": partial.get("slides", []),
            "caption": partial.get("caption", ""),
            "hashtags": partial.get("hashtags", []),
        }
        errors, warnings = validate_deck(deck)
        for w in warnings:
            emit(f"  WARN  {w}")
        if not errors:
            emit(f"  ✓ valid on attempt {attempt}")
            return deck
        emit(f"  attempt {attempt}: {len(errors)} validation error(s)")
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content": "Validator rejected it:\n- " + "\n- ".join(errors)
                                                 + "\nFix every issue and return the full corrected JSON object only."}]

    raise GenerationError(f"still invalid after {max_attempts} attempts: " + "; ".join(errors))


def _complete(client, model, messages):
    """One chat completion returning raw text. Reasoning models (gpt-5*) reject
    `max_tokens` and only accept the default temperature, so send neither."""
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
        max_completion_tokens=8000,
    )
    return resp.choices[0].message.content or ""


def main():
    ap = argparse.ArgumentParser(description="Generate a validated Zylo deck.json from a topic")
    ap.add_argument("topic")
    ap.add_argument("--archetype", required=True, choices=sorted(ARCHETYPE_GUIDE))
    ap.add_argument("--palette", default="dark", choices=["dark", "light"])
    ap.add_argument("--slug", help="override the auto slug")
    ap.add_argument("--pillar", help="content pillar tag (reserved for sourcing)")
    ap.add_argument("--notes", help="extra direction for the model")
    ap.add_argument("--render", action="store_true", help="render immediately after generating")
    args = ap.parse_args()

    load_env()
    try:
        deck = generate(args.topic, args.archetype, args.palette, args.slug, args.pillar, args.notes)
    except GenerationError as e:
        sys.exit(f"✗ {e}")

    out_dir = ROOT / "decks" / deck["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "deck.json"
    out_file.write_text(json.dumps(deck, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ wrote {out_file.relative_to(ROOT)}")

    if args.render:
        subprocess.run([sys.executable, str(ROOT / "src" / "render.py"), str(out_file)], check=True)


if __name__ == "__main__":
    main()
