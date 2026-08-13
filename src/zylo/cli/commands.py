"""One class per command.

Each owns its arguments and its execution, so `zylo generate` and the legacy
`python src/generate.py` shim share a single definition — the shim just runs the
command with its own parser.
"""
import argparse
import socket
import sys
from pathlib import Path
from typing import Protocol

from ..container import ApplicationContainer
from ..domain.deck import Archetype, Palette
from ..domain.errors import ExtractError, GenerationError, RenderError, ZyloError
from ..domain.source import SourceMaterial
from ..prompts.frameworks import AUTO
from ..reporting import PrintReporter
from ..services.pipeline import DeckBrief

EXIT_OK = 0
EXIT_FAIL = 1


class Command(Protocol):
    name: str
    description: str

    def configure(self, parser: argparse.ArgumentParser) -> None:
        ...

    def run(self, args: argparse.Namespace, container: ApplicationContainer) -> int:
        ...


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return EXIT_FAIL


class GenerateCommand:
    name = "generate"
    description = "Generate a validated Zylo deck.json from a topic or a source URL"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("topic", nargs="?", default="",
                            help="omit if using --url/--source-file")
        parser.add_argument("--archetype", required=True, choices=Archetype.values())
        parser.add_argument("--palette", default="dark", choices=Palette.values())
        parser.add_argument("--slug", help="override the auto slug")
        parser.add_argument("--pillar", help="content pillar tag (reserved for sourcing)")
        parser.add_argument("--notes", help="extra direction for the model")
        parser.add_argument("--framework", default=AUTO,
                            help="narrative architecture; 'auto' lets the model pick one that fits")
        parser.add_argument("--url", help="blog or LinkedIn post URL to draw the points from")
        parser.add_argument("--source-file",
                            help="text file to draw the points from (use when a site blocks the fetch)")
        parser.add_argument("--render", action="store_true",
                            help="render immediately after generating")

    def run(self, args: argparse.Namespace, container: ApplicationContainer) -> int:
        if args.framework not in container.frameworks:
            return _fail(f"✗ framework must be one of {container.frameworks.choices()}")

        reporter = PrintReporter()
        try:
            source = self._source(args, container, reporter)
        except ExtractError as exc:
            return _fail(f"✗ {exc}")
        if source is None and not args.topic:
            return _fail("✗ give a topic, or --url / --source-file")

        brief = DeckBrief(topic=args.topic, archetype=args.archetype, palette=args.palette,
                          slug=args.slug, pillar=args.pillar, notes=args.notes,
                          framework=args.framework)
        try:
            deck = container.generator.generate(brief.generation_request(source), reporter)
        except GenerationError as exc:
            return _fail(f"✗ {exc}")

        deck_file = container.repository.save(deck)
        print(f"✓ wrote {container.paths.relative(deck_file)}")

        if args.render:
            try:
                container.renderer.render(deck, deck_file.parent, reporter)
            except RenderError as exc:
                return _fail(f"\n✗ {exc}")
        return EXIT_OK

    @staticmethod
    def _source(args, container, reporter) -> SourceMaterial | None:
        if args.url:
            return container.source_extractor.extract(args.url, reporter)
        if args.source_file:
            text = Path(args.source_file).read_text(encoding="utf-8").strip()
            if not text:
                raise ExtractError(f"{args.source_file} is empty")
            return SourceMaterial.from_text(text)
        return None


class ValidateCommand:
    name = "validate"
    description = "Check a deck.json against the schema rules"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("deck_file", help="decks/<dir>/deck.json")

    def run(self, args: argparse.Namespace, container: ApplicationContainer) -> int:
        path = Path(args.deck_file)
        try:
            deck = container.repository.load_from(path)
        except ZyloError as exc:
            return _fail(f"✗ {exc}")

        result = container.validator.validate(deck)
        for message in result.warnings:
            print(f"  WARN  {message}")
        for message in result.errors:
            print(f"  ERROR {message}")

        name = path.parent.name
        if result.ok:
            print(f"\n✓ {name}: valid ({len(result.warnings)} warning(s))")
            return EXIT_OK
        print(f"\n✗ {name}: {len(result.errors)} error(s)")
        return EXIT_FAIL


class RenderCommand:
    name = "render"
    description = "Render a deck.json to slide PNGs, a contact sheet and caption.txt"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("deck_file", help="decks/<dir>/deck.json")

    def run(self, args: argparse.Namespace, container: ApplicationContainer) -> int:
        try:
            container.renderer.render_file(Path(args.deck_file), PrintReporter())
        except ZyloError as exc:
            return _fail(f"\n✗ {exc}")
        return EXIT_OK


class ExtractCommand:
    name = "extract"
    description = "Pull the readable text out of a blog or LinkedIn post URL"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("url")
        parser.add_argument("--chars", type=int, default=2000,
                            help="how much of the extracted text to print")

    def run(self, args: argparse.Namespace, container: ApplicationContainer) -> int:
        try:
            source = container.source_extractor.extract(args.url, PrintReporter())
        except ExtractError as exc:
            return _fail(f"✗ {exc}")
        print(f"\n--- {source.title} ---\n{source.text[:args.chars]}")
        return EXIT_OK


class ServeCommand:
    name = "serve"
    description = "Run the Zylo Deck Studio web app"

    def configure(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--host", default=None)
        parser.add_argument("--port", type=int, default=None)

    def run(self, args: argparse.Namespace, container: ApplicationContainer) -> int:
        import uvicorn

        from ..api import create_app

        host = args.host or container.settings.host
        port = args.port or container.settings.port

        # Bind-check first: a busy port otherwise fails deep in uvicorn's output where
        # a non-technical operator will not see it.
        if not self._port_free(host, port):
            return _fail(f"Port {port} is already in use. "
                         f"Run with --port <other> (e.g. --port {port + 1}).")

        print(f"\n  Zylo Deck Studio  ->  http://{host}:{port}\n  (Ctrl+C to stop)\n")
        uvicorn.run(create_app(container), host=host, port=port, log_level="warning")
        return EXIT_OK

    @staticmethod
    def _port_free(host: str, port: int) -> bool:
        probe = socket.socket()
        try:
            probe.bind((host, port))
        except OSError:
            return False
        finally:
            probe.close()
        return True


def all_commands() -> list[Command]:
    return [GenerateCommand(), ValidateCommand(), RenderCommand(),
            ExtractCommand(), ServeCommand()]
