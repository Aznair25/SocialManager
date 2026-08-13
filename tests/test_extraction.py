"""URL -> reference material, exercised without a browser.

The fetch is a port, so everything that actually decides whether a page is
usable can be tested against canned pages.
"""
import pytest

from zylo.adapters.browser import RawPage
from zylo.adapters.extraction import (
    ExtractionLimits,
    WebPageSourceExtractor,
    clean_body,
    clean_title,
    prose_chars,
)
from zylo.domain.errors import ExtractError

from .fakes import FakePageFetcher, RecordingReporter

ARTICLE = "\n".join(
    f"This is paragraph {i} of a genuine article, long enough to count as prose "
    f"rather than a navigation fragment." for i in range(8)
)


def extractor(page=None, error=None, limits=None):
    return WebPageSourceExtractor(FakePageFetcher(page, error), limits)


def page(**overrides) -> RawPage:
    defaults = {"url": "https://example.com/post", "title": "A Post - Example",
                "og_title": "", "og_description": "", "description": "",
                "best": ARTICLE, "body": ARTICLE}
    defaults.update(overrides)
    return RawPage(**defaults)


class TestCleanBody:
    def test_drops_navigation_lines(self):
        raw = "Sign in\nHome\nAbout\nA real sentence with enough words to survive.\nSubscribe"
        assert clean_body(raw) == "A real sentence with enough words to survive."

    def test_collapses_whitespace(self):
        assert clean_body("  spaced    out   sentence here  ") == "spaced out sentence here"

    def test_removes_repeated_lines(self):
        raw = "A genuine sentence of prose.\nA genuine sentence of prose."
        assert clean_body(raw) == "A genuine sentence of prose."

    def test_drops_short_single_word_chrome(self):
        assert clean_body("x\nyy\nMenu\n5 min read") == ""


class TestCleanTitle:
    @pytest.mark.parametrize("title,netloc,expected", [
        ("Foo - Wikipedia", "en.wikipedia.org", "Foo"),
        ("Post | LinkedIn", "www.linkedin.com", "Post"),
        ("Real Title - A Genuine Subtitle", "example.com", "Real Title - A Genuine Subtitle"),
        ("", "example.com", ""),
    ])
    def test_strips_only_a_real_site_suffix(self, title, netloc, expected):
        assert clean_title(title, netloc) == expected

    def test_long_post_bodies_reduce_to_their_opening_sentence(self):
        title = "Enterprises keep buying licences. " + "And then a great deal more text. " * 5
        assert clean_title(title, "example.com") == "Enterprises keep buying licences."

    def test_long_title_without_a_sentence_break_is_cut_on_a_word(self):
        result = clean_title("word " * 40, "example.com")
        assert len(result) <= 100 and not result.endswith("wor")


class TestExtraction:
    def test_returns_cleaned_text_with_provenance(self):
        source = extractor(page()).extract("https://example.com/post")
        assert source.url == "https://example.com/post"
        assert source.title == "A Post"
        assert "paragraph 0" in source.text

    def test_reports_progress(self):
        reporter = RecordingReporter()
        extractor(page()).extract("https://example.com/post", reporter)
        assert reporter.messages[0] == "  Reading example.com"
        assert reporter.messages[1].startswith("  Extracted ")
        assert "A Post" in reporter.messages[1]

    @pytest.mark.parametrize("url", ["", "   ", "example.com", "ftp://example.com", "not a url"])
    def test_rejects_anything_that_is_not_an_http_url(self, url):
        with pytest.raises(ExtractError, match="does not look like a web address"):
            extractor(page()).extract(url)

    def test_prefers_the_whole_body_when_the_selector_grabbed_a_sidebar(self):
        source = extractor(page(best="Tiny sidebar.", body=ARTICLE)).extract("https://example.com/post")
        assert "paragraph 7" in source.text

    def test_merges_the_social_summary_ahead_of_the_body(self):
        """og:description is often all LinkedIn serves without an account."""
        summary = "A distinct summary sentence that the page body does not contain at all."
        source = extractor(page(og_description=summary)).extract("https://example.com/post")
        assert source.text.startswith(summary)

    def test_does_not_duplicate_a_summary_already_in_the_body(self):
        first_line = ARTICLE.splitlines()[0]
        source = extractor(page(og_description=first_line)).extract("https://example.com/post")
        assert source.text.count(first_line) == 1

    def test_prefers_the_og_title(self):
        source = extractor(page(og_title="Better Title")).extract("https://example.com/post")
        assert source.title == "Better Title"

    def test_truncates_on_a_line_boundary(self):
        source = extractor(page(), limits=ExtractionLimits(max_chars=300)).extract(
            "https://example.com/post")
        assert len(source.text) <= 300 and not source.text.endswith(" ")


class TestUnusablePages:
    def test_a_wall_message_is_quoted_back(self):
        text = "Please enable javascript to view this content properly."
        wall = RawPage(url="https://example.com/post", best=text, body=text)
        with pytest.raises(ExtractError, match="the page says “please enable javascript”"):
            extractor(wall).extract("https://example.com/post")

    def test_nav_only_sign_in_pages_are_still_rejected(self):
        """"Sign in to see" is itself stripped as chrome, leaving nothing behind."""
        wall = RawPage(url="https://example.com/post", best="Sign in to see this post",
                       body="Sign in to see this post")
        with pytest.raises(ExtractError, match="navigation and links, not an article"):
            extractor(wall).extract("https://example.com/post")

    def test_a_redirect_is_named(self):
        thin = RawPage(url="https://example.com/feed", best="Some short bits here now",
                       body="Some short bits here now")
        with pytest.raises(ExtractError, match="it redirected to /feed"):
            extractor(thin).extract("https://example.com/post")

    def test_a_directory_page_is_rejected_for_lacking_prose(self):
        """Nav fragments survive line filtering; measuring prose separately catches them."""
        listing = "\n".join([f"Category number {i} listing page" for i in range(40)])
        thin = RawPage(url="https://example.com/post", best=listing, body=listing)
        with pytest.raises(ExtractError, match="navigation and links, not an article"):
            extractor(thin).extract("https://example.com/post")

    def test_fetch_errors_are_passed_through_untouched(self):
        boom = ExtractError("example.com returned HTTP 404 for that URL")
        with pytest.raises(ExtractError, match="HTTP 404"):
            extractor(error=boom).extract("https://example.com/post")


# A real LinkedIn post: 89 lines, 2,920 characters, only three lines >= 60 chars.
# Written the way LinkedIn posts are written — one short line per thought.
SHORT_LINE_POST = "\n".join([
    "Your six-week MVP lives or dies by the pod you hire.",
    "Speed matters.",
    "Clarity matters.",
    "Most teams miss the real bottleneck.",
    "It is not the model.",
    "It is the pod.",
    "A six-week MVP needs one thing above all.",
    "A pod that can ship end-to-end without drama.",
    "That means product, data, model and deployment in one team.",
    "No handoffs between three vendors.",
    "No waiting two weeks for an environment.",
    "Scope the thing you can defend in a demo.",
    "Cut everything else.",
    "Hire for range, not for titles.",
    "One person who can do two of the four is worth three specialists.",
    "Give them the decision rights on day one.",
    "Review weekly against a working build, never a deck.",
    "That is the whole method.",
])


class TestShortLinePosts:
    """Regression: LinkedIn's house style used to be read as navigation chrome.

    The old test counted only lines >= 60 characters, so a 2,900-character post
    made of short lines scored ~250 and was rejected as "navigation and links".
    """

    def test_a_short_line_post_is_readable_source_material(self):
        page = RawPage(url="https://www.linkedin.com/posts/someone_a-post",
                       title="Post | LinkedIn", best=SHORT_LINE_POST, body=SHORT_LINE_POST)
        source = extractor(page).extract("https://www.linkedin.com/posts/someone_a-post")
        assert "six-week MVP" in source.text
        assert source.title == "Post"

    def test_the_old_length_only_measure_would_have_failed_it(self):
        long_lines = sum(len(line) for line in SHORT_LINE_POST.splitlines() if len(line) >= 60)
        assert long_lines < ExtractionLimits().min_prose
        assert prose_chars(SHORT_LINE_POST) >= ExtractionLimits().min_prose


class TestProseChars:
    def test_counts_long_lines_regardless_of_punctuation(self):
        assert prose_chars("x" * 80) == 80

    @pytest.mark.parametrize("line", ["Speed matters.", "Is it though?", "Ship it!",
                                      'He said "ship it."', "And so on…"])
    def test_counts_short_lines_that_close_like_sentences(self, line):
        assert prose_chars(line) == len(line)

    @pytest.mark.parametrize("line", ["Home", "13K posts", "See all results",
                                      "Sign in", "Related posts"])
    def test_ignores_navigation_fragments(self, line):
        assert prose_chars(line) == 0

    def test_a_listing_page_still_scores_near_zero(self):
        listing = "\n".join(f"Category number {i} listing page" for i in range(40))
        assert prose_chars(listing) == 0
