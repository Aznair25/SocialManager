# PROGRESS.md — Zylo Deck Agent

> Update at the end of every working session (AGENT.md rule 8). Newest entry on top.

## Status board

| Area | State |
|---|---|
| Feasibility & brand research | ✅ Done (see FEASIBILITY.md) |
| AGENT.md / PROGRESS.md | ✅ Done |
| Brand kit (tokens.json, base.css) | ✅ Done |
| Templates: cover/stat/content/mythfact/cta | ✅ Done — visually verified in browser |
| Validator (`src/validate.py`) | ✅ Done — executed, all 3 decks pass with 0 errors |
| Renderer + contact sheet (`src/render.py`) | ✅ Done — executed, 19 slides + 3 contact sheets rendered |
| Sample decks ×3 (deck.json) | ✅ Done — validated and rendered |
| First render run (PNG output) | ✅ Done — 2026-08-07, all slides 1080×1350, visually inspected |
| Cleanup: delete deprecated `src/*.js`, `package.json` | ✅ Done |
| LLM content generator (`src/generate.py`) | ✅ Done — OpenAI `gpt-5.1`, executed, valid on attempt 1 |
| Source ingestion (`src/extract.py`) | ✅ Done — blog + real LinkedIn post verified, 0 copied phrasing |
| HTTP API (`src/app.py`) | ✅ Done — full pipeline tested end to end |
| Web UI (`web/index.html`) | ✅ Done — 3 input modes, no console errors |
| Real Zylo logo on slides | ✅ Done — owner supplied 2026-08-07, extracted to an alpha mask |
| Vendored Poppins in `brand/fonts/` | 🔲 Optional — currently Google Fonts at render time |
| IG publishing integration | ⏸ Deferred by design |
| Topic sourcing | ⏸ Deferred by design |

## Decisions locked

- Architecture: LLM writes `deck.json` → deterministic HTML/CSS → Playwright/Chromium → 1080×1350 PNG. No AI-drawn slides.
- Palette: dark-primary (`#07090F`) with light-card accent decks (`#FAFAFA`), ~2:1 rotation.
- v1 archetypes: **stat**, **insight**, **mythfact** (definition/quote cards dropped from v1).
- Review loop: contact sheet per deck, human approves before any upload; uploads manual for now.
- LLM provider: **OpenAI**, default `gpt-5.1` (owner decision, 2026-08-07). Overridable via `ZYLO_MODEL`.
- Interface: FastAPI serving a single-page UI (`web/index.html`) — no Node, no build step, so the
  repo stays Python-only. CLI remains the reference path; the API calls the same functions.
- Logo: owner's artwork is a blue-gradient tile; slides use an **alpha mask** of the logotype tinted
  from `--fg`, never the coloured tile — rule 6 forbids introducing new colors (2026-08-07).
- CTA contact route: `contact@wearezylo.com`, code-owned in `tokens.json`; the LLM is forbidden from
  writing any URL or email (2026-08-07).

- Source-derived decks must never reproduce the source: prompt rules **plus** a mechanical 7-word
  overlap check that rejects and re-prompts. Fetching stays plain — no working around login walls
  or paywalls, ever (2026-08-07).

- Layout: slide content is **horizontally centred**; only header and footer stay edge-aligned
  (owner decision, 2026-08-07). **Vertical centring was already in place and must not change** —
  `.body` keeps `justify-content: center`.
- The cover is a hook, not a title: ≤55 chars hard, 3-8 words, plus a circled-arrow visual. Never
  restates the topic or a source headline (owner decision, 2026-08-07).

- Content craft is ported from marketing frameworks into the **generator's system prompt**, not into
  `.claude/skills/` — copy is written by gpt-5.1 at runtime with no Claude in the loop, so a Claude
  skill would not change a single deck (2026-08-07).
- Zylo's six real figures each belong to one claim; the validator rejects a figure reused for a
  second claim (2026-08-07).

## Log

### 2026-08-07 — Session 3g: owner design corrections
**Done:** Three corrections from owner screenshots in `changes/`.
1. **Header tag chip removed** (`ENTERPRISE 2026` pill) — called out as irrelevant noise. Dropped
   from all five templates plus its CSS. The cover's `kicker` field no longer renders, so the
   archetype guides now say "cover (hook only)" and stop the model writing copy nothing displays.
   In-body chips stay: `kicker` on content slides, `MYTH`/`FACT` on mythfact.
2. **Cover arrow reshaped to a looping arrow.** Owner compared the plain arc against the reference
   and the difference was the loop — the stroke must cross itself once before the sweep down, which
   is what makes it read as hand-drawn. Drafted three candidates and rendered them side by side
   before picking rather than guessing.
3. **`wearezylo.com` and `contact@wearezylo.com` removed from the cta slide.** It now shows only the
   line and the `Book a call` pill. This reverses the 2026-08-07 addition — the owner has now seen it
   rendered and wants the slide cleaner. `identity.site` / `identity.email` stay in `tokens.json`,
   and the caption still carries the link, so nothing is lost. Generator prompt updated to match.
Dead CSS removed (`.tag-chip`, `.cta-site`, `.cta-email`). All 13 decks re-rendered: 108 slides,
all 1080×1350.
**Next:** Owner review of the cleaned cover and cta.
**Blockers:** None.

### 2026-08-07 — Session 3f: visual elements from owner references
**Done:** Owner supplied six Instagram screenshots in `visual_elements/` showing what "add visual
elements, not just text" meant. Three separate asks, all implemented:
1. **Background motif** (refs: waving lines, faint watermark arcs) — three oversized thin circles
   bleeding off every slide edge at a new `--arc` token (`arcOnDark` 0.055 / `arcOnLight` 0.045 in
   `tokens.json`). Drawn with CSS borders, so the colour is a token and nothing is fetched at render
   time. Same positions on all five templates, so the deck still reads as one visual template.
2. **Curved pointer arrow** (refs: hand-drawn arrows pointing at the frames) — replaced the centred
   circled arrow on the cover with a drawn curve in `--hl` pointing in at the hook.
3. **Minimal corner swipe cue** (ref: "SWIPE TO READ ⟶" bottom-right) — replaced the centred
   `SWIPE` label; on the cover it takes the slide index's place in the footer.
Two geometry bugs found by rendering and zooming rather than assuming: the arrow anchored to the
body's centre collided with the hook (hooks run 2–3 lines, so it is now anchored to the top of
`.body`), and the first arrowhead read as a kink because its wings sat collinear with the curve —
recomputed to splay ±28° about the exit tangent.
Verified on both palettes and across all three archetypes. All 13 decks re-rendered: 108 slides,
all 1080×1350.
**Next:** Owner review of the new cover treatment. `visual_elements/` is still untracked — decide
whether the references belong in the repo.
**Blockers:** None.

### 2026-08-07 — Session 3e: marketing frameworks ported into the generator
**Done:** Owner linked the `marketing-plan` skill from coreyhaines31/marketingskills. That one is
about 12-month AARRR plans and is not applicable; the useful material was
`skills/social/references/carousel-frameworks.md`, the social hook formulas and marketing-psychology.
Ported four of the five narrative frameworks into new `src/frameworks.py` — `problemproof`,
`hacklist`, `valuestack`, `callout` — as a `framework` axis orthogonal to `archetype` (archetype =
how slides look, framework = how the deck argues). Demo Walkthrough dropped (needs UI screenshots).
Consumer/growth tone stripped throughout to respect rule 7. Wired through `--framework`, the API,
and a "Story shape" selector in the UI; `auto` lets the model choose. Also folded named hook
patterns and open-loop / loss-aversion / curse-of-knowledge guidance into `ENGAGEMENT`.
Two production-checklist items are now mechanical validator rules feeding the correction loop:
the **counted promise** (a cover opening with a number must deliver exactly that many middle slides;
regex guards against `3×`, `40%`, `2026` being read as counts) and **one ask per cta**.
Raised chip and footer type to the skill's ~28px thumbnail-legibility floor (`.kicker`, `.tag-chip`,
`.mf-chip`, `.cover-swipe` 22→28, `.foot` 26→28).
**Caught a real content-integrity bug by testing rather than re-rendering:** the first Problem-Proof
deck fabricated `85% of AI pilots stall at 'interesting'`, reusing Zylo's genuine `+85% operational
efficiency` for an invented claim. Added a validator rule rejecting the same figure on two stat
slides with different labels, plus an explicit "this is the COMPLETE list of real figures, each
belongs to one claim" prompt rule. On regeneration the deck dropped the invented stat and shipped
four stat slides instead of padding to seven — the intended behaviour.
Also fixed a false positive in the first cut of the one-ask cta rule: it counted sentences, which
flagged the legitimate `"Two of these true? Let's talk."` (a setup plus one ask). Now allows two
clauses, rejects three.
**Next:** Owner review of the three framework sample decks (`fw-valuestack`, `fw-callout`,
`fw-problemproof`) to decide which shapes earn a place in the rotation. Older decks still carry
pre-framework copy and would need regenerating to benefit.
**Blockers:** None.

### 2026-08-07 — Session 3d: engagement pass (cover hooks, centring, visual)
**Done:** Four owner-reported issues, all fixed and re-rendered across every deck.
1. *Covers were echoing the title.* Added an `ENGAGEMENT` block to the system prompt: the hook must
   never restate the topic or a source headline, must be 3-8 words, and must land a contrarian
   claim / costly mistake / surprising number / sharp tension. Banned "How to", "A guide to",
   "Understanding", and `Subject: subtitle` colon constructions. Cover hook limit tightened
   **70 → 55 chars** in `validate.py` and `deck.schema.json`. Measured effect on the same source:
   `"Turn agentic AI pilots into orchestrated operations"` (55, a title) became
   `"Your AI pilot is a cul-de-sac"` (29, a hook).
2. *Content read as information, not engagement.* Same block: titles are claims not labels, bodies
   address the reader as "you", name the cost of getting it wrong, and end where the reader wants
   the next slide. Output shifted to "You shipped tech, not an operation", "Governance arrives
   after the damage", "Your people don't trust the agents".
3. *Cover needed fewest words + a visual.* Cover now carries a large circled arrow in `--hl` plus a
   small `swipe` label, centred beneath the hook (inline SVG using `currentColor`, so still
   token-driven). Replaced the old footer swipe pill; hook type up to 90px.
4. *Content sat on the left.* `.body` now centres horizontally (`align-items: center` +
   `text-align: center`); `.kicker`, `.mf-chip`, `.mf-div` and the CTA block centre too. Header and
   footer stay edge-aligned. Verified across all three archetypes.
   **Follow-up:** owner clarified only left/right centring was wanted. Vertical was never changed —
   `justify-content: center` predates this session and is absent from the diff. The one real
   regression was the cover: adding the arrow pushed the hook ~130px above centre. Fixed by taking
   the arrow cue out of flow (`.cover-cue`, absolutely positioned, `bottom: 44px` to clear the
   footer), so the hook holds the same vertical centre as every other slide.
All 9 decks validate with 0 errors and re-render clean; 73 slides, all 1080×1350.
**Next:** Owner review of the new cover treatment before the first real posting run. `decks/2026-08-07_agentic-ai-orchestrating-enterprise-ai-o/` is superseded by `agentic-ai-at-scale` (same source, pre-engagement prompt) and can be deleted. Empty `decks/2026-08-07_ai-in-real-estate/` is also stale.
**Blockers:** None.

### 2026-08-07 — Session 3c: generation live, source ingestion, company context
**Done:** Owner added `OPENAI_API_KEY`, so **the generation half ran for the first time** — the
pipeline is now proven end to end. Sharpened the company context in the prompt: Zylo sells adoption
workshops, capacity building, AI governance and in-house AI development, written for the executive
buying those services rather than for developers.
Built **source ingestion** (`src/extract.py`): give it a blog or LinkedIn post URL and it pulls the
readable text via Playwright's Chromium, then the generator mines it for points. Verified on a real
public LinkedIn post and on a long article. Guardrails found by actually testing: HTTP status is
checked (a 404 page was becoming "source material"), a prose-density floor rejects feeds/directory/
error pages that survive line filtering, redirects to `/login/` are reported as such, and page
titles are collapsed and stripped of site/author suffixes before becoming the deck slug.
**Not copying** is enforced twice: the prompt treats the text as research notes, and
`verbatim_hits()` rejects any 7-consecutive-word overlap and re-prompts. Both test decks came back
with **zero overlap even at 5-word runs** — genuinely reworded, source never named.
Fixed a real generation defect on the way: the model consistently landed 3-20 chars over the 200-char
body limit and could not self-correct, because "203 > 200" asks it to count precisely. Retries now
name an explicit target length (limit − 25) and instruct deletion rather than rewording; the system
prompt also asks for ~85% of each limit. Three decks that previously failed after 3 attempts now
pass on attempt 1.
API and UI extended: `source_url` / `source_text`, a `reading` stage, and three input modes
(topic / link / pasted text) with the paste fallback surfaced for sites that block reading.
**Next:** Ask owner which archetype/palette rotation to use for the first real posting run. Consider
vendoring Poppins into `brand/fonts/` so rendering stops depending on Google Fonts at run time.
**Blockers:** None.

### 2026-08-07 — Session 3: first execution, OpenAI port, API + UI
**Done:** Deleted deprecated `src/render.js`, `src/validate.js`, `package.json`. Installed deps and
Chromium; **ran the pipeline for the first time**. All 3 sample decks validate with 0 errors and
render clean: 19 slides total, every one 1080×1350, plus contact sheets and captions. Visually
inspected all 3 contact sheets — no overflow or clipping, chips/pills correct, purple glow subtle,
light myths deck legible, footers show handle + index.
Fixed 1 real runtime bug: contact-sheet thumbnails were all broken images because `page.set_content()`
gives the page an `about:blank` origin, from which Chromium refuses to load `file://` subresources —
thumbnails now inline as base64 data URIs (`src/render.py`). No visual values, char limits, or slide
copy were touched.
Then, per owner request: ported `generate.py` from Anthropic to **OpenAI** (`gpt-5.1`, JSON-object
response format, `max_completion_tokens`); refactored `generate()`/`render_deck()` to take an
`on_event` callback and raise `GenerationError`/`RenderError` instead of `sys.exit`, so they are
callable in-process; added `src/app.py` (FastAPI REST API: create/poll/list/fetch/re-render/download,
jobs on worker threads because Playwright's sync API refuses to run inside an asyncio loop, one
pipeline lock so Chromium is never driven concurrently) and `web/index.html` (brand-styled
single-page studio: topic form, live stage progress, contact sheet, slide thumbnails, caption copy,
zip download). Default port moved to **8777** — port 8000 is already taken by another app on this
machine — with a bind pre-check so a clash fails with a readable message.
**Next:** Owner to paste `OPENAI_API_KEY` into `.env`; then run the generation smoke test
(`python src/generate.py "How AI agents cut enterprise support costs" --archetype insight --palette dark --render`)
and one end-to-end run through the UI to confirm the validator self-correct loop passes within 3
attempts on gpt-5.1. Then ask owner for the real Zylo logo SVG.
**Blockers:** No OpenAI API key on the machine yet — the generation half of the pipeline is the one
part still unexecuted. Render half is fully verified.

### 2026-08-07 — Session 3b: real logo + CTA email
**Done:** Owner supplied the brand logo (a blue-gradient app tile, opaque raster). Kept the original
at `brand/logo-source.png` and derived `brand/logo-zylo.png` — the ZYLO logotype as a tight-cropped
512×210 **alpha mask** (background keyed out on min-channel; the source separates cleanly, ground
≤30 vs letterforms ≥240, so edges came out with no blue fringing). Templates now draw it via CSS
`mask` with `background: var(--fg)`, so it is white on dark slides and near-black on light and the
blue never reaches a slide — rule 6 (never introduce new colors) intact. The mask is injected as a
data URI, same `about:blank` constraint as the contact-sheet thumbnails. Replaced the Poppins text
wordmark in all 5 templates (`aria-label` retains the name).
Added `identity.email = contact@wearezylo.com` to `tokens.json`; every cta slide now prints the
button, then `wearezylo.com`, then the email. The generator prompt now forbids the model from
writing any URL or email in the cta `line`, so the contact route stays code-owned and changeable in
one place. No char limits, slide copy, or existing visual values were altered.
Re-rendered all 3 decks: 19 slides, all 1080×1350, both palettes visually verified.
**Next:** Unchanged — owner to add `OPENAI_API_KEY`, then the generation smoke test.
**Blockers:** Same — no API key yet.

### 2026-08-06 — Session 2: full build (Python backend)
**Done:** Complete codebase: `brand/tokens.json`, `templates/base.css` + 5 slide templates, `schema/deck.schema.json`, `src/validate.py`, `src/render.py` (slides + contact sheet + caption), 3 sample decks (`ai-automation-numbers` stat/dark, `ready-for-ai-agents` insight/dark, `enterprise-ai-myths` mythfact/light). Backend ported Node→**Python** per owner request (JS files stubbed as deprecated, pending deletion). Design system **visually verified** by rendering the exact templates/CSS in Chrome: dark glow, lavender `**highlight**`, giant numerals, chips, pills, light variant all correct.
**Next:** When sandbox VM is available: `pip install -r requirements.txt && playwright install chromium`, delete `src/*.js` + `package.json`, run `python src/render.py` on all 3 decks, inspect PNGs, present contact sheets for approval. Ask owner for the real Zylo logo SVG (slides currently use a text wordmark).
**Blockers:** Sandbox VM offline for the entire session — code unexecuted. Fonts fall back to Google Fonts at render time until `brand/fonts/` is vendored.

### 2026-08-06 — Session 1: research + foundations
**Done:** Live review of wearezylo.com (extracted real CSS tokens: `#07090F`, `#6428A0`, `#CFD3FF`, Poppins, pill/chip language) and all 9 Instagram accounts (Zylo's IG is empty — blank slate). Confirmed IG carousel specs (4:5, 1080×1350, 20-slide cap) and Graph API prerequisites (deferred). Wrote FEASIBILITY.md, AGENT.md, PROGRESS.md.
**Next:** Scaffold npm project, install Playwright + @fontsource/poppins, verify Chromium screenshot renders in sandbox, then brand kit → templates → renderer → sample decks.
**Blockers:** Sandbox shell VM was offline earlier this session — pipeline validation pending VM availability.
