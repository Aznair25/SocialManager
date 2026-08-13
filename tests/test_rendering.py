"""HTML building and the render service, driven by a fake screenshot engine."""
import pytest

from zylo.domain.deck import Deck
from zylo.domain.errors import RenderError
from zylo.rendering import escape, rich_text
from zylo.rendering.contact_sheet import ContactSheetLayout
from zylo.services.rendering import CaptionWriter

from .conftest import deck_payload, slide
from .fakes import RecordingReporter


class TestMarkup:
    def test_escapes_before_converting_highlights(self):
        """The other order would let deck copy inject markup."""
        assert rich_text("<script>") == "&lt;script&gt;"
        assert rich_text("a **b** c") == 'a <span class="hl">b</span> c'

    def test_highlight_content_is_still_escaped(self):
        assert rich_text("**<b>**") == '<span class="hl">&lt;b&gt;</span>'

    def test_escape_quotes_for_attribute_safety(self):
        assert escape('a"b') == "a&quot;b"


class TestSlideHtml:
    def test_produces_a_standalone_document(self, container, valid_deck):
        html = container.slide_builder.build(valid_deck, valid_deck.slides[0], 0, 5)
        assert html.startswith("<!doctype html>")
        assert "<style>" in html and ":root{" in html

    def test_inlines_the_logo_rather_than_linking_it(self, container, valid_deck):
        """set_content() pages cannot load file:// subresources."""
        html = container.slide_builder.build(valid_deck, valid_deck.slides[0], 0, 5)
        assert "--logo:url(data:image/png;base64," in html

    def test_renders_the_slide_counter_one_based(self, container, valid_deck):
        html = container.slide_builder.build(valid_deck, valid_deck.slides[1], 1, 5)
        assert "02/05" in html

    def test_palette_selects_the_css_variables(self, container):
        dark = Deck.from_dict(deck_payload(palette="dark"))
        light = Deck.from_dict(deck_payload(palette="light"))
        assert (container.slide_builder.build(dark, dark.slides[0], 0, 5)
                != container.slide_builder.build(light, light.slides[0], 0, 5))

    def test_unknown_role_is_a_render_error_not_a_crash(self, container, valid_deck):
        from zylo.domain.deck import Slide

        with pytest.raises(RenderError, match="no template for slide role"):
            container.slide_builder.build(valid_deck, Slide("bogus", {}), 0, 5)


class TestContactSheetLayout:
    def test_thumbnail_keeps_the_slide_aspect_ratio(self, container):
        layout = ContactSheetLayout.for_theme(container.theme)
        assert layout.thumb_height == round(250 * 1350 / 1080) == 312

    @pytest.mark.parametrize("count,rows", [(1, 1), (4, 1), (5, 2), (8, 2), (9, 3)])
    def test_rows_ceiling_divide(self, count, rows):
        assert ContactSheetLayout().rows(count) == rows

    def test_width_is_independent_of_slide_count(self):
        layout = ContactSheetLayout()
        assert layout.width() == 32 * 2 + 4 * 250 + 3 * 20
        assert layout.height(8) > layout.height(4)


class TestCaptionWriter:
    def test_prefixes_hashtags_that_lack_a_hash(self, valid_deck):
        out = CaptionWriter().render(valid_deck)
        assert out.endswith("#AIConsulting #EnterpriseAI #AIGovernance #AIAdoption #AIStrategy\n")

    def test_leaves_already_prefixed_tags_alone(self):
        deck = Deck.from_dict(deck_payload(hashtags=["#Already", "NotYet"]))
        assert "#Already #NotYet" in CaptionWriter().render(deck)

    def test_separates_caption_and_tags_with_a_blank_line(self, valid_deck, tmp_path):
        path = CaptionWriter().write(valid_deck, tmp_path)
        assert path.read_text(encoding="utf-8").count("\n\n") >= 1


class TestRenderService:
    def test_writes_a_png_per_slide_plus_a_contact_sheet(self, container, valid_deck, tmp_path):
        pngs = container.renderer.render(valid_deck, tmp_path)
        assert [p.name for p in pngs] == ["01.png", "02.png", "03.png", "04.png", "05.png"]
        assert (tmp_path / "contact-sheet.png").is_file()
        assert (tmp_path / "caption.txt").is_file()

    def test_uses_one_browser_session_for_the_whole_deck(self, container, valid_deck, tmp_path):
        container.renderer.render(valid_deck, tmp_path)
        assert container.screenshot_engine.sessions == 1

    def test_resizes_the_viewport_for_the_contact_sheet(self, container, valid_deck, tmp_path):
        layout = ContactSheetLayout.for_theme(container.theme)
        container.renderer.render(valid_deck, tmp_path)
        assert ("resize", layout.width(), layout.height(5)) in container.screenshot_engine.log

    def test_contact_sheet_is_captured_full_page(self, container, valid_deck, tmp_path):
        container.renderer.render(valid_deck, tmp_path)
        sheet = [e for e in container.screenshot_engine.log
                 if e[0] == "capture" and e[1] == "contact-sheet.png"][0]
        assert sheet[3] is True

    def test_refuses_to_render_an_invalid_deck(self, container, tmp_path):
        """A rendered PNG is what gets uploaded, so this must never produce files."""
        target = tmp_path / "out"
        target.mkdir()
        broken = Deck.from_dict(deck_payload(
            slides=[slide("cover", hook="x" * 90), slide("content", title="T", body="B"),
                    slide("content", title="T2", body="B2"),
                    slide("content", title="T3", body="B3"), slide("cta", line="L")]))
        with pytest.raises(RenderError, match="validation failed — not rendering"):
            container.renderer.render(broken, target)
        assert list(target.iterdir()) == []
        assert container.screenshot_engine.sessions == 0

    def test_reports_progress_per_slide(self, container, valid_deck, tmp_path):
        reporter = RecordingReporter()
        container.renderer.render(valid_deck, tmp_path, reporter)
        assert "  ✓ slide 1/5 (cover)" in reporter.messages
        assert "  ✓ contact-sheet.png" in reporter.messages
        assert "  ✓ caption.txt" in reporter.messages

    def test_render_file_loads_the_deck_from_disk(self, container, valid_deck):
        deck_file = container.repository.save(valid_deck)
        pngs = container.renderer.render_file(deck_file)
        assert len(pngs) == 5 and pngs[0].parent.parent == deck_file.parent
