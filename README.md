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

## Output

```
decks/YYYY-MM-DD_slug/
  deck.json          the spec (validated against schema/deck.schema.json)
  slides/NN.png      1080×1350 each
  contact-sheet.png  the review artefact — a human approves this before upload
  caption.txt        caption + hashtags
```
