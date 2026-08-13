"""The terminal front door, including the documented src/*.py entry points.

README.md and AGENT.md both promise these commands, so their exit codes and
output shapes are part of the contract.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from zylo.adapters.browser import RawPage
from zylo.cli.commands import (
    ExtractCommand,
    GenerateCommand,
    RenderCommand,
    ValidateCommand,
    all_commands,
)
from zylo.cli.main import build_parser, run_command

from .conftest import deck_payload, slide
from .test_pipeline import ARTICLE, model_reply

ROOT = Path(__file__).resolve().parent.parent


def write_deck(tmp_path, **overrides) -> Path:
    directory = tmp_path / "2026-08-12_a-valid-deck"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "deck.json"
    target.write_text(json.dumps(deck_payload(**overrides)), encoding="utf-8")
    return target


class TestValidateCommand:
    def test_valid_deck_exits_zero(self, container, tmp_path, capsys):
        code = run_command(ValidateCommand(), [str(write_deck(tmp_path))], container=container)
        assert code == 0
        assert "✓ 2026-08-12_a-valid-deck: valid (0 warning(s))" in capsys.readouterr().out

    def test_invalid_deck_exits_one_and_lists_errors(self, container, tmp_path, capsys):
        deck_file = write_deck(tmp_path, slides=[
            slide("cover", hook="x" * 90), slide("content", title="T", body="B"),
            slide("content", title="T2", body="B2"), slide("content", title="T3", body="B3"),
            slide("cta", line="L")])
        code = run_command(ValidateCommand(), [str(deck_file)], container=container)
        out = capsys.readouterr().out
        assert code == 1
        assert "ERROR slide 1 (cover).hook: 90 chars > 55" in out
        assert "✗ 2026-08-12_a-valid-deck: 1 error(s)" in out

    def test_warnings_are_printed_but_still_pass(self, container, tmp_path, capsys):
        deck_file = write_deck(tmp_path, hashtags=["OnlyOne"])
        code = run_command(ValidateCommand(), [str(deck_file)], container=container)
        assert code == 0
        assert "WARN  hashtags: 1 — aim for 5-10" in capsys.readouterr().out

    def test_missing_file_fails_cleanly(self, container, tmp_path, capsys):
        code = run_command(ValidateCommand(), [str(tmp_path / "nope.json")], container=container)
        assert code == 1 and "no deck.json at" in capsys.readouterr().err

    def test_unparseable_file_fails_cleanly(self, container, tmp_path, capsys):
        bad = tmp_path / "deck.json"
        bad.write_text("{not json", encoding="utf-8")
        code = run_command(ValidateCommand(), [str(bad)], container=container)
        assert code == 1 and "not valid JSON" in capsys.readouterr().err


class TestRenderCommand:
    def test_renders_a_deck_in_place(self, container, tmp_path):
        deck_file = write_deck(tmp_path)
        assert run_command(RenderCommand(), [str(deck_file)], container=container) == 0
        assert (deck_file.parent / "contact-sheet.png").is_file()
        assert len(list((deck_file.parent / "slides").glob("*.png"))) == 5

    def test_invalid_deck_exits_one_without_writing(self, container, tmp_path, capsys):
        deck_file = write_deck(tmp_path, caption="")
        assert run_command(RenderCommand(), [str(deck_file)], container=container) == 1
        assert "validation failed — not rendering" in capsys.readouterr().err
        assert not (deck_file.parent / "slides").exists()


class TestGenerateCommand:
    def args(self, **overrides):
        base = {"topic": "Adoption is the gap", "archetype": "insight"}
        base.update(overrides)
        argv = [base.pop("topic")] if base.get("topic") is not None else []
        for key, value in base.items():
            if value is True:
                argv.append(f"--{key.replace('_', '-')}")
            elif value is not None:
                argv += [f"--{key.replace('_', '-')}", str(value)]
        return argv

    def test_writes_a_deck_and_reports_the_path(self, container, chat, deck_root, capsys):
        chat.replies = [model_reply()]
        code = run_command(GenerateCommand(), self.args(), container=container)
        assert code == 0
        assert "✓ wrote" in capsys.readouterr().out
        assert list(deck_root.glob("*/deck.json"))

    def test_render_flag_produces_images(self, container, chat, deck_root):
        chat.replies = [model_reply()]
        run_command(GenerateCommand(), self.args(render=True), container=container)
        assert list(deck_root.glob("*/contact-sheet.png"))

    def test_generation_failure_exits_one(self, container, chat, capsys):
        chat.replies = ["nonsense"] * 3
        code = run_command(GenerateCommand(), self.args(), container=container)
        assert code == 1 and "✗ still invalid after 3 attempts" in capsys.readouterr().err

    def test_source_file_is_read(self, container, chat, tmp_path):
        chat.replies = [model_reply()]
        notes = tmp_path / "notes.txt"
        notes.write_text(ARTICLE, encoding="utf-8")
        code = run_command(GenerateCommand(),
                           self.args(topic=None, source_file=str(notes)), container=container)
        assert code == 0

    def test_empty_source_file_exits_one(self, container, tmp_path, capsys):
        notes = tmp_path / "notes.txt"
        notes.write_text("   ", encoding="utf-8")
        code = run_command(GenerateCommand(),
                           self.args(topic=None, source_file=str(notes)), container=container)
        assert code == 1 and "is empty" in capsys.readouterr().err

    def test_url_is_extracted(self, container, chat, fetcher):
        chat.replies = [model_reply()]
        fetcher.page = RawPage(url="https://example.com/post", title="A Post",
                               best=ARTICLE, body=ARTICLE)
        code = run_command(GenerateCommand(),
                           self.args(topic=None, url="https://example.com/post"),
                           container=container)
        assert code == 0 and fetcher.requested == ["https://example.com/post"]

    def test_no_topic_and_no_source_exits_one(self, container, capsys):
        code = run_command(GenerateCommand(), ["--archetype", "insight"], container=container)
        assert code == 1 and "give a topic, or --url / --source-file" in capsys.readouterr().err

    def test_unknown_framework_exits_one(self, container, capsys):
        code = run_command(GenerateCommand(), self.args(framework="nope"), container=container)
        assert code == 1 and "framework must be one of" in capsys.readouterr().err

    def test_unknown_archetype_is_rejected_by_argparse(self, container):
        with pytest.raises(SystemExit):
            run_command(GenerateCommand(), self.args(archetype="wat"), container=container)


class TestExtractCommand:
    def test_prints_the_title_and_text(self, container, fetcher, capsys):
        fetcher.page = RawPage(url="https://example.com/post", title="A Post",
                               best=ARTICLE, body=ARTICLE)
        code = run_command(ExtractCommand(), ["https://example.com/post"], container=container)
        out = capsys.readouterr().out
        assert code == 0 and "--- A Post ---" in out and "Paragraph 0" in out

    def test_unreadable_page_exits_one(self, container, fetcher, capsys):
        fetcher.page = RawPage(url="https://example.com/post", best="thin", body="thin")
        code = run_command(ExtractCommand(), ["https://example.com/post"], container=container)
        assert code == 1 and "✗" in capsys.readouterr().err


class TestParser:
    def test_every_command_is_registered(self):
        parser = build_parser(all_commands())
        for name in ("generate", "validate", "render", "extract", "serve"):
            assert parser.parse_args([name, *_minimal_args(name)]).command == name

    def test_a_command_is_required(self):
        with pytest.raises(SystemExit):
            build_parser(all_commands()).parse_args([])


def _minimal_args(name):
    return {"generate": ["T", "--archetype", "insight"], "validate": ["f.json"],
            "render": ["f.json"], "extract": ["https://example.com"], "serve": []}[name]


class TestLegacyEntryPoints:
    """README.md and AGENT.md document these paths; they have to keep working."""

    @pytest.mark.parametrize("script", ["generate.py", "validate.py", "render.py",
                                        "extract.py", "app.py"])
    def test_shim_imports_and_shows_help(self, script):
        result = subprocess.run([sys.executable, str(ROOT / "src" / script), "--help"],
                                capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert "usage:" in result.stdout.lower()

    def test_validate_shim_end_to_end(self, tmp_path):
        deck_file = write_deck(tmp_path)
        result = subprocess.run([sys.executable, str(ROOT / "src" / "validate.py"),
                                 str(deck_file)], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0
        assert "valid (0 warning(s))" in result.stdout

    def test_validate_shim_reports_failure(self, tmp_path):
        deck_file = write_deck(tmp_path, caption="")
        result = subprocess.run([sys.executable, str(ROOT / "src" / "validate.py"),
                                 str(deck_file)], capture_output=True, text=True, timeout=60)
        assert result.returncode == 1
        assert "caption is required" in result.stdout

    def test_frameworks_shim_still_exports_the_old_names(self):
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src'); import frameworks as f; "
             "print(f.choices()); print(sorted(f.FRAMEWORKS)); "
             "print(len(f.framework_block('callout', 'mythfact'))); "
             "print(f.for_archetype('stat')); print(bool(f.HOOKS and f.PSYCHOLOGY))"],
            capture_output=True, text=True, cwd=ROOT, timeout=60)
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0] == "['auto', 'callout', 'hacklist', 'problemproof', 'valuestack']"
        assert lines[3] == "['auto', 'hacklist', 'problemproof', 'valuestack']"
        assert lines[4] == "True"

    def test_module_entry_point_works(self):
        result = subprocess.run([sys.executable, "-m", "zylo", "--help"],
                                capture_output=True, text=True, cwd=ROOT / "src", timeout=60)
        assert result.returncode == 0 and "generate" in result.stdout
