# AGENT.md — Zylo Deck Agent

Rules for any agent (or human) working in this repo. Read this fully before touching anything.

## Mission

Generate **knowledge decks** — multi-slide Instagram carousels — for **Zylo** (AI consultancy, wearezylo.com, @wearezylotech). Output must be minimal, sleek, sophisticated, and *identical in spirit to the Zylo website theme*. Consistency across every deck is the product. Instagram publishing and topic sourcing are **deferred** — this repo only generates.

**What Zylo sells** (drives every deck's angle): workshops that get organisations adopting AI; capacity building so AI capability stays in-house; AI governance (policy, risk, oversight) for regulated enterprises; and an in-house AI development team building custom agents, automation and software. Write for the executive or transformation lead buying those services — never generic AI commentary, never developer-tool content.

## Non-negotiable rules

1. **Never use AI image generation to draw slides or any text.** All slides are rendered deterministically from HTML/CSS templates via headless Chromium. (AI-generated *background art* may be introduced later only with explicit owner approval, always with text composited by the renderer.)
2. **Only brand tokens.** Every color, font, radius, and spacing value comes from `brand/tokens.json`. Never hard-code a hex value inside a template; reference the CSS variables generated from tokens.
3. **Every deck must pass `python src/validate.py` before rendering.** Char limits and slide-count rules in `schema/deck.schema.json` are hard constraints, not suggestions. If copy doesn't fit, rewrite the copy — never shrink the type or widen the box.
4. **Format:** 1080×1350 px (4:5), PNG. 6–10 slides recommended, 20 max (Instagram cap). All slides in a deck share the same palette variant.
5. **Every deck gets a contact sheet** (`contact-sheet.png`) for human approval. Nothing is "done" without one. Never post/publish anywhere — a human uploads manually for now.
6. **Palette policy: dark-primary with light-card accents.** Roughly 2 of every 3 decks dark (`#07090F`), 1 light (`#FAFAFA`), so the profile grid alternates with rhythm. Never introduce new colors.
7. **Voice:** outcome-led, metric-heavy, enterprise-calm. Short declarative sentences. No hype words ("revolutionary", "game-changing"), no emojis in slide text, no exclamation marks on slides. Numbers do the talking (`+85%`, `3×`, `−40%`).
8. **Update `PROGRESS.md` at the end of every working session** — what was done, what's next, blockers. No exceptions.
9. **Never edit generated files** in `decks/*/slides/` by hand; fix the template or the deck spec and re-render.
10. **Don't restructure the repo** without updating this file and PROGRESS.md in the same session.

## Brand system (source of truth: wearezylo.com, extracted 2026-08-06)

| Token | Value | Use |
|---|---|---|
| `bg.dark` | `#07090F` | primary slide background |
| `bg.darkSection` | `#0B0B0F` | cards/panels on dark |
| `bg.light` | `#FAFAFA` | light variant background |
| `fg.onDark` | `#FFFFFF` | headlines on dark |
| `fg.onLight` | `#0A0A0A` | headlines on light |
| `fg.muted` | `#737373` | secondary text, labels |
| `accent.purple` | `#6428A0` | brand accent, gradients, emphasis |
| `accent.lavender` | `#CFD3FF` | soft highlight, on-dark emphasis |
| `border.light` | `#E5E5E5` | card borders on light |
| `radius.card` | `20px` | cards (site: 0.625rem scaled ×2 for 1080px canvas) |
| `radius.pill` | `999px` | buttons, chips |
| Font | **Poppins** | 300 display numerals · 500/600 headings · 400 body |
| `identity.email` | `contact@wearezylo.com` | contact route, printed on every cta slide |
| `identity.logo` | `brand/logo-zylo.png` | the ZYLO logotype, top-left of every slide |

**Logo (owner asset, 2026-08-07).** `brand/logo-source.png` is the original supplied artwork —
a blue-gradient app tile. `brand/logo-zylo.png` is the ZYLO logotype extracted from it as a
tight-cropped **alpha mask** (pure white pixels, transparent ground, 512×210). Templates draw it
via CSS `mask` with `background: var(--fg)`, so it renders white on dark slides and near-black on
light ones and **no colour is baked into the asset** — rule 6 (never introduce new colors) still
holds, and the blue never reaches a slide. If the logo is ever reissued, re-derive the mask from
the new source; do not paste a coloured logo into a template.

Design language: generous negative space, giant light-weight numerals with small labels, white pill buttons with arrow chips, small tag chips (`AI`, `Enterprise`, `Automation`), the logotype small at top-left of each slide, handle `@wearezylotech` in the footer. Dark slides may use a very subtle purple radial glow — never gradients that overpower text.

**Slide content is horizontally centred** (owner decision, 2026-08-07). Body copy, chips, numerals, dividers and CTA blocks all centre left-to-right; only the header (logotype / tag chip) and footer (handle / index) stay edge-aligned. A deck reads as a sequence of single focused statements, not as left-aligned page copy.

Vertical placement is unchanged and must stay that way: `.body` has always used `justify-content: center`, so content sits in the optical middle between header and footer. In a column flexbox `align-items` is the horizontal axis and `justify-content` the vertical one — don't confuse them when editing `base.css`. The cover's arrow cue is absolutely positioned precisely so it cannot push the hook off that vertical centre.

## Repo map

```
brand/          tokens.json; logo-source.png (owner's original) + logo-zylo.png (alpha mask
                used by the templates); brand/fonts/ optional vendored Poppins woff2
schema/         deck.schema.json — the contract every deck.json must satisfy
templates/      base.css (design system) + one HTML template per slide role
src/            generate.py (LLM content brain), validate.py, render.py (incl. contact sheet),
                extract.py (URL -> reference text), app.py (FastAPI: REST API + serves the web UI)
web/            index.html — single-page studio UI (vanilla JS, no build step)
decks/          output: decks/YYYY-MM-DD_slug/{deck.json, slides/*.png, contact-sheet.png, caption.txt}
.env.example    copy to .env, add OPENAI_API_KEY (generation only; rendering needs no key)
requirements.txt  playwright + openai + fastapi/uvicorn
                (setup: pip install -r requirements.txt && playwright install chromium)
AGENT.md        this file
PROGRESS.md     session log — always current
FEASIBILITY.md  original assessment (context, do not edit)
```

Backend is **Python** (owner decision, 2026-08-06); the Node stubs were deleted 2026-08-07.
LLM provider is **OpenAI** (owner decision, 2026-08-07), default model `gpt-5.1`, overridable
via `ZYLO_MODEL`. Fonts: render.py uses `brand/fonts/poppins-latin-{300,400,500,600}-normal.woff2`
if vendored, else loads Poppins from Google Fonts at render time.

## Two ways in

**Web UI (for non-technical operators)** — `python src/app.py`, then open http://127.0.0.1:8000.
Enter a topic, pick style + look, press Generate; the page shows live progress and then the
contact sheet, slides, caption, and a zip download. Same rules apply: nothing is published,
a human reviews the contact sheet and uploads manually.

**REST API** — the UI is a thin client over these:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/decks` | `{topic?, archetype, palette, notes?, source_url?, source_text?}` → `{job_id}`; runs read → generate → validate → render. Needs a topic **or** a source |
| `GET` | `/api/jobs/{job_id}` | job status, stage, streaming log lines |
| `GET` | `/api/decks` | list all decks |
| `GET` | `/api/decks/{id}` | deck.json + slide list + caption |
| `POST` | `/api/decks/{id}/render` | re-render after a hand edit to deck.json |
| `GET` | `/api/decks/{id}/slides/{n}.png`, `/contact-sheet.png`, `/caption.txt`, `/download` | artefacts |

The CLI (`src/generate.py`, `src/validate.py`, `src/render.py`) still works unchanged and
remains the reference path. Jobs are serialised behind one lock — one deck builds at a time,
because Chromium and the deck directory are shared state.

## Workflow (per deck)

0. Or skip all of this: `python src/app.py` and drive the whole pipeline from the browser UI. Steps 1–3 are exactly what it runs.
1. Generate the spec: `python src/generate.py "<topic>" --archetype <stat|insight|mythfact> [--palette dark|light] [--notes "..."]` — the LLM writes slides/caption/hashtags only; code owns id/palette/archetype. It self-corrects against the validator (3 attempts). Hand-writing deck.json is also fine.
   Instead of a topic you may pass **source material**: `--url <blog or LinkedIn post>` or `--source-file <txt>`. See "Working from a source" below.
2. `python src/validate.py decks/<dir>/deck.json` — must pass (generate.py already ran it; re-run after any manual edit).
3. `python src/render.py decks/<dir>/deck.json` — writes `slides/NN.png` + `contact-sheet.png` + `caption.txt`.
4. Visually inspect every slide (agents: actually open/Read the PNGs — check overflow, contrast, spacing).
5. Log in PROGRESS.md; present contact sheet for human approval.

## Working from a source (blog / LinkedIn post)

`src/extract.py` pulls the readable text out of a URL using the Chromium that Playwright already
installs (most platforms render body copy with JS). That text is **reference material only**.

**The deck is never a copy of the source.** Three things enforce it:

1. The generator prompt treats the text as research notes: extract the points, write every slide
   from scratch, never reuse a sentence or distinctive phrase, never name or allude to the source
   or its author, drop anecdotes and self-promotion, invent no statistics.
2. `verbatim_hits()` in `generate.py` then checks mechanically — any **7 consecutive words** shared
   with the source is a rejection, fed back into the same correction loop the validator uses. A deck
   only ships once it comes back clean, logged as *"original wording confirmed"*.
3. Char limits force compression anyway: a 200-char body cannot carry a copied paragraph.

Reframe toward what Zylo sells. If the source is about something Zylo does not offer, keep the
insight and drop the pitch.

Fetching is plain and unauthenticated — nothing here works around a login wall, paywall or bot
check, and it must stay that way. Sites that refuse (LinkedIn often does for non-public posts)
raise `ExtractError` telling the operator to paste the text instead; error pages, feeds and
directory pages are rejected by a prose-density check rather than being passed off as an article.
`deck.json` records `source_url` for provenance; it is never rendered on a slide.

## Archetypes (v1)

**stat** — Zylo-website-style giant numerals. Cover hook → 3–6 stat slides (`value` ≤ 8 chars, `label` ≤ 60, optional `context` ≤ 110) → CTA.
**insight** — the classic knowledge carousel. Cover hook (≤ 55 chars) → 4–7 content slides (title ≤ 44, body ≤ 200, optional kicker ≤ 24) → CTA.
**mythfact** — myth/fact pairs (myth ≤ 90, fact ≤ 160 per slide, 3–5 pairs) or mini case study (client, problem, solution, result slides) → CTA.

## The cover carries the whole post

Most viewers read slide 1 and nothing else, so it is written and designed differently from every other slide.

- **Fewest words in the deck.** 3–8 words, aim under 45 characters; **55 is a hard validator failure** (was 70 until 2026-08-07). Fewer words, larger type.
- **A hook, never a label.** It must never restate the topic, the deck's subject, or a source article's headline — that is the single most common failure. `Agentic AI: orchestrating operations` is a title; `Your AI pilot is a cul-de-sac` is a hook.
- It must land one of: a claim the reader will argue with, the expensive mistake they are probably making, a number that stops them, or a tension between what they believe and what is true. Banned openings are listed in `ENGAGEMENT` in `src/generate.py`.
- **A visual element, not just type.** The cover carries a large circled arrow in `--hl` plus a small `swipe` label, centred under the hook. This replaced the old footer swipe pill. The arrow is inline SVG using `currentColor`, so it stays token-driven.

Content slides are reframed for a scrolling reader too: titles are claims rather than labels, bodies address the reader as "you", name the cost of getting it wrong, and end somewhere that earns the next swipe. This is enforced by the `ENGAGEMENT` block in the system prompt — edit it there, not per-deck.

## Archetype rules

Every archetype: slide 1 is always a **cover**, last slide is always **cta**. The cta is code-owned apart from its `line` (≤ 60 chars): the renderer prints the `Book a call` pill, then `wearezylo.com`, then `contact@wearezylo.com`, from `brand/tokens.json`. The LLM never writes a URL or email — the generator prompt forbids it, so the contact route can be changed in one place. Slide numbers `01/07` bottom-right.

## Captions

Structure: 1 hook line ↵ 2–4 short lines expanding the promise ↵ CTA line ("Full breakdown: wearezylo.com") ↵ 5–10 hashtags mixing niche + reach (e.g. `#AIConsulting #AIAutomation #EnterpriseAI #AIAgents #DigitalTransformation`). No hashtag walls of 30.

## Deferred — do not build yet

Instagram Graph API publishing (needs IG Professional account, linked FB Page, Meta app + `instagram_business_content_publish`, ~2–4 wk review, images at public URLs, 100 posts/24 h). Topic sourcing/calendar automation. Both plug into `deck.json` later; reserve fields, don't implement.

## Maintenance

If wearezylo.com rebrands, re-extract tokens from the live site and bump `brand/tokens.json` (record the change in PROGRESS.md). Template changes require re-rendering one sample per archetype and updating this file if specs changed.
