# Zylo Deck Studio

Generates brand-consistent Instagram carousel decks for Zylo — topic in, reviewed
1080×1350 slides out. Copy is written by an LLM; every pixel is rendered
deterministically from HTML/CSS templates via headless Chromium. Nothing is ever
posted automatically.

Read [AGENT.md](AGENT.md) before changing anything — its rules are binding.

## Setup (once)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env      # then put your OPENAI_API_KEY in .env
```

## Use it from the browser

```bash
python src/app.py         # -> http://127.0.0.1:8777
```

Enter a topic, pick a style and look, press **Generate deck**. The page shows live
progress, then the contact sheet, every slide, the caption, and a zip download.
Use `--port` if 8777 is taken.

## Use it from the command line

```bash
python src/generate.py "How AI agents cut enterprise support costs" \
    --archetype insight --palette dark --render

python src/validate.py decks/<dir>/deck.json   # must pass before rendering
python src/render.py   decks/<dir>/deck.json   # slides + contact sheet + caption
```

Rendering is fully local and needs no API key — only generation calls OpenAI.

The same commands are also available as subcommands, if you prefer one entry point:

```bash
cd src && python -m zylo generate "..." --archetype insight --render
cd src && python -m zylo validate ../decks/<dir>/deck.json
```

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

OpenAI, Playwright and page fetching are replaced by fakes, so the suite needs no API key,
no browser and no network.

## How the code is laid out

`src/zylo/` is the implementation; the `src/*.py` scripts above are thin shims over it.

```
domain/      deck model + validation rules. Pure — no I/O, no SDKs.
prompts/     Zylo's voice, archetype guides, narrative frameworks.
ports.py     the interfaces the outside world is reached through.
adapters/    OpenAI, Playwright, filesystem implementations of those interfaces.
rendering/   deck -> HTML (theme, templates, slides, contact sheet). Pure.
services/    generate, render, run the pipeline, track jobs.
api/ cli/    thin delivery layers over the services.
container.py the one place that decides which adapter is used.
```

Adding a validation rule means adding a class to `domain/validation/rules.py` and listing it;
adding a narrative framework means adding an entry to `prompts/frameworks.py` and it appears
in the CLI and the UI automatically. See [AGENT.md](AGENT.md) for the full map.

## Build from an article or LinkedIn post

Instead of a topic, point it at a link and it takes the *points* — the deck is written from
scratch in Zylo's voice, never copied. A mechanical check rejects any seven consecutive words
shared with the source and makes the model rewrite.

```bash
python src/generate.py --url "https://example.com/blog/post" --archetype insight --render
python src/generate.py --source-file notes.txt --archetype mythfact --render
```

Fetching is plain and unauthenticated. Some sites (LinkedIn included, for anything not fully
public) will refuse — the error says so, and you can paste the text in instead, in the UI or
with `--source-file`.

## Refreshing the brand tokens

Every colour, font, radius and spacing value comes from `brand/tokens.json`, which was
read off wearezylo.com by hand on 2026-08-06. There is deliberately no scraper for this —
it happens once a rebrand, and a coding agent does it better than a selector would.

When the site changes, open this repo in Claude Code (or Cowork) and ask:

> Look at https://wearezylo.com and update `brand/tokens.json` to match its current design.
> Keep the existing key names and structure exactly — `render.py` turns them into CSS
> variables and the templates reference those names. Change values only; do not add,
> rename or remove keys. Update the `extracted` date, note what changed in PROGRESS.md,
> then re-render one deck per archetype and show me the contact sheets.

Points worth making explicit in the ask, because they are easy to get wrong:

- **Both palettes.** Most keys come in a dark/light pair (`fgOnDark` / `fgOnLight`). The
  site is dark-first, so the light values usually have to be derived rather than read.
- **Contrast.** `fgMutedOnLight` on `bgLight` still has to be legible at 1080×1350 — check
  the rendered PNG, not the hex.
- **`canvas` and `identity` are not brand colours.** 1080×1350 is the Instagram format and
  `identity.logo` points at an owner-supplied asset; neither comes from the website.
- **Never hard-code a hex in a template.** If a new colour is genuinely needed, it gets a
  token first (AGENT.md rule 2).

Afterwards, `python src/render.py decks/<dir>/deck.json` on an existing deck is the fastest
way to see the change — rendering is local and needs no API key.

## Output

```
decks/YYYY-MM-DD_slug/
  deck.json          the spec (validated against schema/deck.schema.json)
  slides/NN.png      1080×1350 each
  contact-sheet.png  the review artefact — a human approves this before upload
  caption.txt        caption + hashtags
```
