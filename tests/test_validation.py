"""Validation rules.

Each test names the failure it is guarding against, because these messages are
sent back to the model as correction instructions — a wording change here is a
behaviour change.
"""
import pytest

from zylo.domain.deck import Deck
from zylo.domain.validation import DeckValidator, Severity, error, warning
from zylo.domain.validation.constraints import FieldContext, MaxLength, NoEmoji
from zylo.domain.validation.rules import CountPromise, SingleAsk

from .conftest import deck_payload, slide


@pytest.fixture
def validator():
    return DeckValidator.with_default_rules()


def check(validator, **overrides):
    return validator.validate(Deck.from_dict(deck_payload(**overrides)))


def content(n):
    return [slide("content", title=f"T{i}", body=f"B{i}") for i in range(n)]


def test_a_good_deck_passes_clean(validator, valid_deck):
    result = validator.validate(valid_deck)
    assert result.ok and result.errors == [] and result.warnings == []


class TestIdentity:
    def test_odd_id_warns_but_does_not_block(self, validator):
        result = check(validator, id="nope")
        assert result.ok
        assert result.warnings == ['id "nope" should match YYYY-MM-DD_slug']

    def test_unknown_archetype_is_an_error(self, validator):
        assert 'archetype "wat" invalid' in check(validator, archetype="wat").errors

    def test_unknown_palette_is_an_error(self, validator):
        assert 'palette "beige" invalid' in check(validator, palette="beige").errors


class TestStructure:
    def test_too_few_slides(self, validator):
        result = check(validator, slides=[slide("cover", hook="H"), slide("cta", line="L")])
        assert "needs >=5 slides (cover + content + cta), got 2" in result.errors

    def test_instagram_cap_is_an_error(self, validator):
        slides = [slide("cover", hook="H"), *content(20), slide("cta", line="L")]
        assert "Instagram cap is 20 slides, got 22" in check(validator, slides=slides).errors

    def test_long_but_legal_deck_only_warns(self, validator):
        slides = [slide("cover", hook="H"), *content(10), slide("cta", line="L")]
        result = check(validator, slides=slides)
        assert "12 slides — 6-10 recommended" in result.warnings

    def test_must_open_on_a_cover_and_close_on_a_cta(self, validator):
        slides = [*content(4), slide("content", title="T", body="B")]
        result = check(validator, slides=slides)
        assert 'slides[0] must be role "cover"' in result.errors
        assert 'last slide must be role "cta"' in result.errors

    def test_unknown_role_is_reported_once_and_skipped(self, validator):
        slides = [slide("cover", hook="H"), slide("bogus", x=1), *content(2), slide("cta", line="L")]
        errors = check(validator, slides=slides).errors
        assert 'slide 2: unknown role "bogus"' in errors
        assert not any("slide 2 (bogus)" in e for e in errors)

    def test_archetype_constrains_which_middle_roles_are_allowed(self, validator):
        slides = [slide("cover", hook="H"), slide("stat", value="3x", label="faster"),
                  *content(2), slide("cta", line="L")]
        assert ('slide 2: role "stat" not allowed in archetype "insight"'
                in check(validator, slides=slides).errors)


class TestFields:
    def test_missing_required_field(self, validator):
        slides = [slide("cover", hook=""), *content(3), slide("cta", line="L")]
        assert ('slide 1 (cover): missing required field "hook"'
                in check(validator, slides=slides).errors)

    def test_over_length_names_both_numbers(self, validator):
        slides = [slide("cover", hook="x" * 80), *content(3), slide("cta", line="L")]
        assert ("slide 1 (cover).hook: 80 chars > 55 — rewrite the copy, never shrink the type"
                in check(validator, slides=slides).errors)

    def test_highlight_markers_are_excluded_from_the_count(self, validator):
        hook = "**" + "x" * 55 + "**"          # 59 raw, 55 visible
        slides = [slide("cover", hook=hook), *content(3), slide("cta", line="L")]
        assert check(validator, slides=slides).ok

    def test_unbalanced_markers(self, validator):
        slides = [slide("cover", hook="**broken"), *content(3), slide("cta", line="L")]
        assert ("slide 1 (cover).hook: unbalanced ** highlight markers"
                in check(validator, slides=slides).errors)

    def test_emoji_and_exclamation_are_both_rejected(self, validator):
        slides = [slide("cover", hook="Great 🚀"),
                  slide("content", title="Wow!", body="B"), *content(2), slide("cta", line="L")]
        errors = check(validator, slides=slides).errors
        assert "slide 1 (cover).hook: emojis are forbidden on slides" in errors
        assert "slide 2 (content).title: exclamation marks are forbidden on slides" in errors


class TestStatRules:
    def test_long_stat_value_warns_about_rendering(self, validator):
        slides = [slide("cover", hook="H"), slide("stat", value="1234567", label="long"),
                  slide("stat", value="3x", label="faster"),
                  slide("stat", value="50+", label="companies"), slide("cta", line="L")]
        result = check(validator, archetype="stat", slides=slides)
        assert 'slide 2: stat value "1234567" >6 chars renders smaller' in result.warnings

    def test_reusing_a_figure_for_a_second_claim_is_rejected(self, validator):
        """This is how invented statistics get in."""
        slides = [slide("cover", hook="H"), slide("stat", value="+85%", label="efficiency"),
                  slide("stat", value="85%", label="pilots stall"),
                  slide("stat", value="3x", label="faster"), slide("cta", line="L")]
        errors = check(validator, archetype="stat", slides=slides).errors
        assert len(errors) == 1
        assert 'slides 2 and 3 both use the figure "85"' in errors[0]
        assert '("efficiency" vs "pilots stall")' in errors[0]

    def test_the_same_figure_twice_is_fine_when_it_has_no_digits(self, validator):
        slides = [slide("cover", hook="H"), slide("stat", value="N/A", label="a"),
                  slide("stat", value="N/A", label="b"),
                  slide("stat", value="3x", label="faster"), slide("cta", line="L")]
        assert check(validator, archetype="stat", slides=slides).ok


class TestCountPromise:
    def build(self, hook, middle):
        return Deck.from_dict(deck_payload(
            slides=[slide("cover", hook=hook), *content(middle), slide("cta", line="L")]))

    def test_a_counted_hook_must_be_delivered_exactly(self):
        errors = list(CountPromise().check(self.build("5 signs you are stuck", 3)))
        assert "cover promises 5 but the deck delivers 3" in errors[0].message

    def test_matching_count_passes(self):
        assert list(CountPromise().check(self.build("3 signs you are stuck", 3))) == []

    @pytest.mark.parametrize("hook", ["3x faster than before", "40% of pilots stall",
                                      "2026 is the year", "1 thing matters"])
    def test_figures_and_ones_are_not_counted_promises(self, hook):
        assert list(CountPromise().check(self.build(hook, 3))) == []


class TestCallToAction:
    def cta(self, line):
        return Deck.from_dict(deck_payload(
            slides=[slide("cover", hook="H"), *content(3), slide("cta", line=line)]))

    def test_three_clauses_is_a_stacked_ask(self):
        issues = list(SingleAsk().check(self.cta("One. Two. Three.")))
        assert issues and "stacks multiple asks" in issues[0].message

    def test_a_setup_plus_an_ask_stays_legal(self):
        assert list(SingleAsk().check(self.cta("Two of these true? Let us talk."))) == []


class TestCaptionAndHashtags:
    def test_caption_is_required(self, validator):
        assert "caption is required" in check(validator, caption="   ").errors

    def test_caption_length_cap(self, validator):
        assert ("caption 2400 chars > 2200 (Instagram limit)"
                in check(validator, caption="x" * 2400).errors)

    def test_hashtag_count_warns_outside_the_sweet_spot(self, validator):
        assert "hashtags: 1 — aim for 5-10" in check(validator, hashtags=["One"]).warnings

    def test_hashtags_beyond_instagrams_cap_are_an_error(self, validator):
        result = check(validator, hashtags=[f"t{i}" for i in range(31)])
        assert "hashtags exceed Instagram limit of 30" in result.errors


class TestExtensibility:
    """SOLID payoff: new checks arrive as new objects, not edits to old ones."""

    def test_a_custom_rule_can_be_added_without_touching_the_validator(self, valid_deck):
        class NoQuestionCovers:
            def check(self, deck):
                if deck.cover and deck.cover.text("hook", "").endswith("?"):
                    yield error("cover hook must not be a question")

        deck = Deck.from_dict(deck_payload(
            slides=[slide("cover", hook="Is your pilot a strategy?"),
                    *content(3), slide("cta", line="L")]))
        extended = DeckValidator.with_default_rules().with_rule(NoQuestionCovers())

        assert extended.validate(deck).errors == ["cover hook must not be a question"]
        assert DeckValidator.with_default_rules().validate(deck).ok

    def test_with_rule_leaves_the_original_validator_alone(self):
        base = DeckValidator.with_default_rules()
        assert len(base.with_rule(object()).rules) == len(base.rules) + 1

    def test_constraints_are_independent_of_the_rule_that_runs_them(self):
        ctx = FieldContext(index=1, role="cover", name="hook", raw="🚀 " + "x" * 60, limit=55)
        assert len(list(MaxLength().check(ctx))) == 1
        assert len(list(NoEmoji().check(ctx))) == 1


class TestReport:
    def test_severity_partitions_the_issues_in_order(self):
        from zylo.domain.validation.report import ValidationReport

        report = ValidationReport.of([error("e1"), warning("w1"), error("e2")])
        assert report.errors == ["e1", "e2"]
        assert report.warnings == ["w1"]
        assert not report.ok and not bool(report)
        assert report.joined_errors() == "e1; e2"
        assert report.issues[1].severity is Severity.WARNING
