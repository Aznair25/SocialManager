"""The end-to-end use case, wired to fakes.

This is the test that would have caught the old duplication: the API and the CLI
now go through this one path, so it only has to be right once.
"""
import json

import pytest

from zylo.adapters.browser import RawPage
from zylo.domain.errors import DeckNotFoundError, ExtractError
from zylo.services.jobs import JobStore, Status
from zylo.services.pipeline import DeckBrief, Stage

from .conftest import deck_payload
from .fakes import RecordingObserver


def model_reply() -> str:
    payload = deck_payload()
    return json.dumps({"slides": payload["slides"], "caption": payload["caption"],
                       "hashtags": payload["hashtags"]})


ARTICLE = "\n".join(
    f"Paragraph {i} carries a real point about enterprise adoption, long enough to read "
    f"as prose rather than as a navigation fragment." for i in range(8)
)


class TestTopicPipeline:
    def test_runs_every_stage_in_order(self, container, chat):
        chat.replies = [model_reply()]
        observer = RecordingObserver()
        container.pipeline.run(DeckBrief(topic="Adoption is the gap"), observer)
        assert observer.stages == [Stage.GENERATING, Stage.VALIDATING,
                                   Stage.RENDERING, Stage.DONE]

    def test_writes_the_deck_and_its_artefacts(self, container, chat, deck_root):
        chat.replies = [model_reply()]
        result = container.pipeline.run(DeckBrief(topic="Adoption is the gap"))

        directory = deck_root / result.deck.id
        assert (directory / "deck.json").is_file()
        assert (directory / "contact-sheet.png").is_file()
        assert (directory / "caption.txt").is_file()
        assert len(list((directory / "slides").glob("*.png"))) == 5

    def test_saved_json_round_trips(self, container, chat):
        chat.replies = [model_reply()]
        result = container.pipeline.run(DeckBrief(topic="Adoption is the gap"))
        on_disk = json.loads(result.deck_file.read_text(encoding="utf-8"))
        assert on_disk == result.deck.to_dict()

    def test_reports_what_it_is_doing(self, container, chat):
        chat.replies = [model_reply()]
        observer = RecordingObserver()
        container.pipeline.run(DeckBrief(topic="Adoption is the gap"), observer)
        assert "Writing the deck for: Adoption is the gap" in observer.messages
        assert "Validation passed" in observer.messages
        assert "Deck ready for review" in observer.messages

    def test_the_deck_id_reaches_the_observer_for_the_ui(self, container, chat):
        chat.replies = [model_reply()]
        observer = RecordingObserver()
        result = container.pipeline.run(DeckBrief(topic="Adoption is the gap"), observer)
        assert observer.deck_ids == [result.deck.id]


class TestSourcePipeline:
    def test_pasted_text_skips_the_fetch(self, container, chat, fetcher):
        chat.replies = [model_reply()]
        observer = RecordingObserver()
        container.pipeline.run(DeckBrief(source_text=ARTICLE), observer)

        assert fetcher.requested == []
        assert observer.stages[0] == Stage.READING
        assert f"Using {len(ARTICLE)} characters of pasted source text" in observer.messages
        assert "Writing the deck from the source points" in observer.messages

    def test_a_url_is_fetched_and_recorded(self, container, chat, fetcher):
        chat.replies = [model_reply()]
        fetcher.page = RawPage(url="https://example.com/post", title="A Post",
                               best=ARTICLE, body=ARTICLE)
        result = container.pipeline.run(DeckBrief(source_url="https://example.com/post"))

        assert fetcher.requested == ["https://example.com/post"]
        assert result.deck.source_url == "https://example.com/post"

    def test_topic_is_derived_from_the_page_title(self, container, chat, fetcher):
        chat.replies = [model_reply()]
        fetcher.page = RawPage(url="https://example.com/post", title="Adoption Is The Gap",
                               best=ARTICLE, body=ARTICLE)
        result = container.pipeline.run(DeckBrief(source_url="https://example.com/post"))
        assert result.deck.topic == "Adoption Is The Gap"

    def test_an_unreadable_page_stops_the_run_before_the_model_is_called(
            self, container, chat, fetcher):
        fetcher.error = ExtractError("example.com did not return readable article text")
        with pytest.raises(ExtractError):
            container.pipeline.run(DeckBrief(source_url="https://example.com/post"))
        assert chat.call_count == 0


class TestRerender:
    def test_rerenders_an_existing_deck(self, container, valid_deck):
        container.repository.save(valid_deck)
        observer = RecordingObserver()
        pngs = container.pipeline.rerender(valid_deck.id, observer)
        assert len(pngs) == 5
        assert observer.stages == [Stage.RENDERING, Stage.DONE], "job must reach a terminal stage"

    def test_unknown_deck_is_a_not_found(self, container):
        with pytest.raises(DeckNotFoundError):
            container.pipeline.rerender("nope")

    def test_a_deck_id_cannot_escape_the_decks_directory(self, container):
        with pytest.raises(DeckNotFoundError):
            container.pipeline.rerender("../../etc")


class TestJobs:
    def test_a_job_records_stages_logs_and_completion(self, container, chat):
        chat.replies = [model_reply()]
        job = container.jobs.create(topic="Adoption")
        container.job_runner.submit(
            job, lambda observer: container.pipeline.run(DeckBrief(topic="Adoption"), observer))
        snapshot = _wait(container.jobs, job.id)

        assert snapshot["status"] == Status.DONE
        assert snapshot["stage"] == Stage.DONE
        assert snapshot["deck_id"].endswith("_adoption")
        assert "Deck ready for review" in snapshot["log"]

    def test_a_failure_is_surfaced_not_swallowed(self, container, chat):
        chat.replies = ["nonsense", "nonsense", "nonsense"]
        job = container.jobs.create(topic="Adoption")
        container.job_runner.submit(
            job, lambda observer: container.pipeline.run(DeckBrief(topic="Adoption"), observer))
        snapshot = _wait(container.jobs, job.id)

        assert snapshot["status"] == Status.ERROR
        assert snapshot["stage"] == Stage.FAILED
        assert "still invalid after 3 attempts" in snapshot["error"]
        assert snapshot["log"][-1].startswith("FAILED:")

    def test_unexpected_errors_are_labelled_with_their_type(self, container):
        job = container.jobs.create()

        def explode(_observer):
            raise ZeroDivisionError("boom")

        container.job_runner.submit(job, explode)
        snapshot = _wait(container.jobs, job.id)
        assert snapshot["error"] == "ZeroDivisionError: boom"

    def test_store_is_isolated_per_job(self):
        store = JobStore()
        a, b = store.create(topic="A"), store.create(topic="B")
        store.append_log(a.id, "only for a")
        store.update(b.id, status=Status.DONE)

        assert store.snapshot(a.id)["log"] == ["only for a"]
        assert store.snapshot(b.id)["log"] == []
        assert store.snapshot(a.id)["status"] == Status.QUEUED
        assert store.snapshot(b.id)["status"] == Status.DONE

    def test_blank_log_lines_are_dropped(self):
        store = JobStore()
        job = store.create()
        store.append_log(job.id, "   ")
        store.append_log(job.id, "  real  ")
        assert store.snapshot(job.id)["log"] == ["real"]

    def test_snapshot_is_a_copy(self):
        store = JobStore()
        job = store.create()
        store.append_log(job.id, "one")
        snapshot = store.snapshot(job.id)
        snapshot["log"].append("two")
        assert store.snapshot(job.id)["log"] == ["one"]

    def test_unknown_job_snapshots_to_none(self):
        assert JobStore().snapshot("nope") is None


def _wait(store: JobStore, job_id: str, timeout: float = 10.0) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        snapshot = store.snapshot(job_id)
        if snapshot and snapshot["status"] in (Status.DONE, Status.ERROR):
            return snapshot
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} did not finish: {store.snapshot(job_id)}")
