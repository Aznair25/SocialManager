"""`python -m zylo <command>`, and the runner the legacy shims use.

    python -m zylo generate "<topic>" --archetype insight --render
    python -m zylo validate decks/<dir>/deck.json
    python -m zylo render   decks/<dir>/deck.json
    python -m zylo extract  https://example.com/post
    python -m zylo serve    --port 8777
"""
import argparse
import sys

from ..container import ApplicationContainer
from .commands import Command, all_commands


def build_parser(commands: list[Command]) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zylo", description="Zylo Deck Studio")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in commands:
        sub = subparsers.add_parser(command.name, help=command.description,
                                    description=command.description)
        command.configure(sub)
        sub.set_defaults(_command=command)
    return parser


def main(argv: list[str] | None = None, container: ApplicationContainer | None = None) -> int:
    args = build_parser(all_commands()).parse_args(argv)
    return args._command.run(args, container or ApplicationContainer.default())


def run_command(command: Command, argv: list[str] | None = None,
                prog: str | None = None, usage: str | None = None,
                container: ApplicationContainer | None = None) -> int:
    """Run a single command with its own parser — how the src/*.py shims work."""
    parser = argparse.ArgumentParser(prog=prog, usage=usage, description=command.description)
    command.configure(parser)
    args = parser.parse_args(argv)
    return command.run(args, container or ApplicationContainer.default())


if __name__ == "__main__":
    sys.exit(main())
