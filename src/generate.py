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

ENGAGEMENT = (
    "THIS IS A SCROLLING FEED, NOT A DOCUMENT. Every slide has to earn the next swipe.\n\n"
    "THE COVER HOOK is the single most important line — most people read only this.\n"
    "- 3-8 words. Aim under 45 characters; 55 is a hard failure. Fewest words wins.\n"
    "- NEVER restate the topic, the source title, or the deck's subject. If the topic is "
    "'Agentic AI: Orchestrating Enterprise Operations', a hook like 'Orchestrating agentic AI "
    "operations' is a FAILURE — it is a label, not a hook.\n"
    "- Make it land one of these: a claim the reader will argue with; the expensive mistake they "
    "are probably making; a number that stops them; a sharp tension between what they believe and "
    "what is true.\n"
    "- Banned openings: 'How to', 'A guide to', 'Understanding', 'The importance of', 'Why you "
    "should', 'Everything about', and any 'Subject: subtitle' colon construction.\n"
    "- Write it as something a person would say out loud, not a heading. Fragments are good. "
    "Two short sentences are good. 'Your AI pilot is not a strategy.' beats 'AI strategy "
    "considerations for enterprises'.\n\n"
    "CONTENT SLIDES must be reframed for a reader, not summarised for a file:\n"
    "- Titles are claims, not labels. 'Governance arrives too late' beats 'Governance'.\n"
    "- Address the reader as 'you' and 'your'. Name the cost of getting it wrong, or the specific "
    "thing that changes when they get it right.\n"
    "- Be concrete: the actual workflow, the actual role, the actual failure. No abstractions "
    "that could apply to any company.\n"
    "- Each body ends somewhere the reader wants the next slide. Do not close the loop early.\n"
    "- Vary the rhythm across slides — do not write eight sentences with the same shape."
)

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


ZYLO = (
    "You write Instagram carousel deck specs for Zylo, an AI consultancy for enterprises "
    "(wearezylo.com, @wearezylotech). What Zylo actually sells:\n"
    "- Workshops that get organisations adopting AI — practical, run with the teams who will use it.\n"
    "- Capacity building: training people and leaders so AI capability stays in-house after Zylo leaves.\n"
    "- AI governance: policy, risk, oversight and safe-use frameworks for regulated enterprises.\n"
    "- An in-house AI development team building custom agents, automation systems and software.\n"
    "Write for the buyer of those services: an executive or transformation lead who needs their "
    "organisation to use AI well, not a developer looking for tools. Adoption, capability, "
    "governance and delivered systems are the themes — never generic AI commentary."
)

SOURCE_RULES = (
    "SOURCE MATERIAL — the operator supplied the text below as raw input. Treat it as research "
    "notes, not as copy.\n"
    "1. Extract the underlying POINTS, then write every slide from scratch in your own words. "
    "Never reuse a sentence, clause or distinctive phrase from it. If a line you wrote could be "
    "found by searching the source, rewrite it.\n"
    "2. Never mention, name, quote, credit or allude to the source, its author, or their company. "
    "The deck must read as Zylo's own thinking.\n"
    "3. Keep only points that stand on their own for an enterprise audience. Drop personal "
    "anecdotes, hiring notices, engagement bait, self-promotion and anything specific to the author.\n"
    "4. Keep the substance honest: do not invent statistics. Use a number only if the source "
    "supports it or it is one of Zylo's own figures. If the source has no numbers, use none.\n"
    "5. Reframe toward what Zylo does — adoption, capacity building, governance, custom builds. "
    "If the source is about something Zylo does not sell, keep the insight and drop the pitch.\n"
    "6. A deck is 5-8 points, not a summary. Choose the strongest ideas and cut the rest.\n"
    "7. The source's headline is NOT your hook. Write a fresh one that would stop the scroll even "
    "for someone who never saw the original."
)


def source_block(source):
    body = (source.get("text") or "").strip()
    head = f"Title: {source['title']}\n" if source.get("title") else ""
    return f"{SOURCE_RULES}\n\n{head}<<<SOURCE\n{body}\nSOURCE>>>"


def system_prompt(archetype):
    return (
        ZYLO + "\n\n"
        + ENGAGEMENT + "\n\n"
        + VOICE + "\n\n"
        "Archetype '" + archetype + "': " + ARCHETYPE_GUIDE[archetype] + "\n\n"
        "HARD character limits per field (counted after removing ** markers) — exceeding any limit is a failure:\n"
        + json.dumps({r: s["fields"] for r, s in LIMITS.items()}, indent=2) + "\n"
        "These are CHARACTERS, not words — letters, spaces and punctuation all count. Models "
        "routinely overshoot these, so write to roughly 85% of each limit and leave yourself margin: "
        "aim for ~170 characters on a 200 limit, ~38 on a 44 limit. Count each field before you "
        "answer. One tight sentence beats two padded ones; if a body needs a second clause to make "
        "sense, cut the idea down instead of stretching the box.\n\n"
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


NGRAM = 7  # consecutive words; slide bodies cap at 200 chars (~30 words), so 7 is a real lift


def _words(s):
    return re.findall(r"[a-z0-9]+", str(s).lower())


def verbatim_hits(deck, source_text, n=NGRAM):
    """Slide/caption text sharing an n-word run with the source — i.e. copied, not rewritten.

    The prompt asks for original wording; this is what makes it stick. Hits are fed
    back into the same correction loop the validator uses.
    """
    src = _words(source_text)
    if len(src) < n:
        return []
    grams = {tuple(src[i:i + n]) for i in range(len(src) - n + 1)}

    hits = []
    fields = ("hook", "kicker", "value", "label", "context", "title", "body", "myth", "fact", "line")
    targets = [(f"slide {i} ({s.get('role')}).{f}", s[f])
               for i, s in enumerate(deck.get("slides", []), 1) for f in fields if s.get(f)]
    targets.append(("caption", deck.get("caption", "")))

    for where, text in targets:
        w = _words(text)
        for i in range(max(0, len(w) - n + 1)):
            if tuple(w[i:i + n]) in grams:
                hits.append(f'{where}: copied wording from the source — "{" ".join(w[i:i + n])}…". '
                            f"Rewrite this in your own words, keeping the point.")
                break
    return hits


def length_targets(deck, margin=25):
    """Concrete rewrite targets for over-long fields.

    '203 chars > 200' leaves the model trying to shave exactly 3 characters, which
    it cannot count reliably — it lands 1-3 over again. Naming a target well under
    the limit converges instead.
    """
    out = []
    for i, s in enumerate(deck.get("slides", []), 1):
        spec = LIMITS.get(s.get("role"))
        if not spec:
            continue
        for f, mx in spec["fields"].items():
            if f not in s:
                continue
            n = len(str(s[f]).replace("**", ""))
            if n > mx:
                out.append(f'slide {i} ({s["role"]}).{f} is {n} characters. Rewrite it to at most '
                           f"{max(20, mx - margin)} characters — cut a clause, keep the point.")
    return out


def slugify(topic, override=None):
    if override:
        return override
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s[:40].rstrip("-") or "deck"


class GenerationError(RuntimeError):
    """Raised when the model cannot produce a valid deck. Callers (CLI, API) decide how to surface it."""


def generate(topic, archetype, palette, slug=None, pillar=None, notes=None, max_attempts=3,
             on_event=None, source=None):
    """Return a validated deck dict. on_event(str) receives progress lines (defaults to print).

    source: optional {url, title, text} from extract.py (or pasted text). Used as
    reference material only — the deck is written fresh and checked for copied wording.
    """
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

    src_text = (source or {}).get("text", "")
    # With source material the topic is optional: fall back to the page title, then to
    # the opening line of the text (pasted posts have no title at all).
    topic = (topic or "").strip() or (source or {}).get("title", "").strip()
    if not topic and src_text:
        first = next((l.strip() for l in src_text.splitlines() if len(l.strip()) > 25), "")
        topic = re.split(r"(?<=[.!?])\s", first)[0][:120].strip() or "source material"
    if not topic:
        raise GenerationError("Give a topic, or a source URL/text to draw one from")
    deck_id = f"{today}_{slugify(topic, slug)}"

    user_msg = f"Topic: {topic}\nPalette: {palette} (affects tone of visuals only, not copy)."
    if notes:
        user_msg += f"\nDirection notes: {notes}"
    if src_text:
        user_msg += "\n\n" + source_block(source)
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
        if source and source.get("url"):
            deck["source_url"] = source["url"]   # provenance only; never rendered on a slide

        errors, warnings = validate_deck(deck)
        for w in warnings:
            emit(f"  WARN  {w}")
        # Copied wording is a rejection, exactly like a char-limit breach.
        copied = verbatim_hits(deck, src_text) if src_text else []
        if copied:
            emit(f"  attempt {attempt}: {len(copied)} passage(s) copied from the source")
        errors = errors + copied

        if not errors:
            emit(f"  ✓ valid on attempt {attempt}" + (" (original wording confirmed)" if src_text else ""))
            return deck
        if not copied:
            emit(f"  attempt {attempt}: {len(errors)} validation error(s)")
        fix = errors + length_targets(deck)
        messages += [{"role": "assistant", "content": raw},
                     {"role": "user", "content":
                      "Rejected:\n- " + "\n- ".join(fix)
                      + "\n\nFix every issue listed. Where a target length is given, hit it by "
                        "deleting words — cut a clause or an example, do not reword at the same "
                        "length. Leave every field that was not listed exactly as it is. Return the "
                        "full corrected JSON object only."}]

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
    ap = argparse.ArgumentParser(description="Generate a validated Zylo deck.json from a topic or a source URL")
    ap.add_argument("topic", nargs="?", default="", help="omit if using --url/--source-file")
    ap.add_argument("--archetype", required=True, choices=sorted(ARCHETYPE_GUIDE))
    ap.add_argument("--palette", default="dark", choices=["dark", "light"])
    ap.add_argument("--slug", help="override the auto slug")
    ap.add_argument("--pillar", help="content pillar tag (reserved for sourcing)")
    ap.add_argument("--notes", help="extra direction for the model")
    ap.add_argument("--url", help="blog or LinkedIn post URL to draw the points from")
    ap.add_argument("--source-file", help="text file to draw the points from (use when a site blocks the fetch)")
    ap.add_argument("--render", action="store_true", help="render immediately after generating")
    args = ap.parse_args()

    load_env()
    source = None
    if args.url:
        from extract import ExtractError, extract_from_url
        try:
            source = extract_from_url(args.url)
        except ExtractError as e:
            sys.exit(f"✗ {e}")
    elif args.source_file:
        text = Path(args.source_file).read_text(encoding="utf-8").strip()
        if not text:
            sys.exit(f"✗ {args.source_file} is empty")
        source = {"url": "", "title": "", "text": text}
    elif not args.topic:
        sys.exit("✗ give a topic, or --url / --source-file")

    try:
        deck = generate(args.topic, args.archetype, args.palette, args.slug, args.pillar,
                        args.notes, source=source)
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
