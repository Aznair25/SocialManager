"""HTTP surface.

The endpoint list is a contract — web/index.html and any curl script depend on
it — so every route is exercised, including the ones that only ever 404.
"""
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from zylo.api import create_app

from .conftest import deck_payload
from .test_pipeline import _wait, model_reply


@pytest.fixture
def client(container):
    return TestClient(create_app(container))


@pytest.fixture
def saved_deck(container, valid_deck):
    container.repository.save(valid_deck)
    return valid_deck


@pytest.fixture
def rendered_deck(container, saved_deck):
    container.renderer.render(saved_deck, container.repository.directory(saved_deck.id))
    return saved_deck


class TestConfig:
    def test_advertises_the_available_choices(self, client):
        body = client.get("/api/config").json()
        assert body["archetypes"] == ["insight", "mythfact", "stat"]
        assert body["palettes"] == ["dark", "light"]
        assert body["frameworks"] == ["auto", "callout", "hacklist",
                                      "problemproof", "valuestack"]
        assert body["model"] == "test-model"
        assert isinstance(body["api_key_set"], bool)


class TestCreateValidation:
    def post(self, client, **body):
        payload = {"topic": "A perfectly good topic", "archetype": "insight",
                   "palette": "dark", "framework": "auto"}
        payload.update(body)
        return client.post("/api/decks", json=payload)

    def test_rejects_an_unknown_archetype(self, client):
        response = self.post(client, archetype="wat")
        assert response.status_code == 400
        assert "archetype must be one of" in response.json()["detail"]

    def test_rejects_an_unknown_palette(self, client):
        assert self.post(client, palette="beige").status_code == 400

    def test_rejects_an_unknown_framework(self, client):
        response = self.post(client, framework="nope")
        assert response.status_code == 400
        assert "framework must be one of" in response.json()["detail"]

    def test_rejects_a_request_with_neither_topic_nor_source(self, client):
        response = self.post(client, topic="ab")
        assert response.status_code == 400
        assert "give a topic, or a source_url / source_text" in response.json()["detail"]

    def test_a_source_makes_the_topic_optional(self, client, chat):
        chat.replies = [model_reply()]
        response = self.post(client, topic=None, source_text="x" * 900)
        assert response.status_code == 200

    def test_over_long_fields_are_rejected_by_the_schema(self, client):
        assert self.post(client, topic="x" * 400).status_code == 422


class TestCreateFlow:
    def test_returns_a_job_that_completes(self, client, container, chat):
        chat.replies = [model_reply()]
        response = client.post("/api/decks", json={"topic": "Adoption is the gap",
                                                   "archetype": "insight", "palette": "dark"})
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        assert response.json()["status"] == "queued"

        snapshot = _wait(container.jobs, job_id)
        assert snapshot["status"] == "done"

        polled = client.get(f"/api/jobs/{job_id}").json()
        assert polled["deck_id"] == snapshot["deck_id"]
        assert "Deck ready for review" in polled["log"]

    def test_unknown_job_is_a_404(self, client):
        assert client.get("/api/jobs/nope").status_code == 404


class TestRead:
    def test_lists_decks_newest_first(self, client, container, valid_deck):
        from zylo.domain.deck import Deck

        container.repository.save(valid_deck)
        container.repository.save(Deck.from_dict(deck_payload(id="2026-08-01_older")))

        decks = client.get("/api/decks").json()["decks"]
        assert [d["id"] for d in decks] == ["2026-08-12_a-valid-deck", "2026-08-01_older"]
        assert decks[0]["slides"] == 5 and decks[0]["rendered"] is False

    def test_listing_is_empty_when_nothing_exists(self, client):
        assert client.get("/api/decks").json() == {"decks": []}

    def test_listing_skips_unreadable_directories(self, client, container, valid_deck):
        container.repository.save(valid_deck)
        broken = container.repository.directory("2026-08-11_broken")
        broken.mkdir(parents=True)
        (broken / "deck.json").write_text("{not json", encoding="utf-8")
        assert len(client.get("/api/decks").json()["decks"]) == 1

    def test_fetches_one_deck(self, client, saved_deck):
        body = client.get(f"/api/decks/{saved_deck.id}").json()
        assert body["deck"]["id"] == saved_deck.id
        assert body["slides"] == [] and body["contact_sheet"] is False

    def test_fetches_a_rendered_deck_with_its_artefacts(self, client, rendered_deck):
        body = client.get(f"/api/decks/{rendered_deck.id}").json()
        assert body["slides"] == ["01.png", "02.png", "03.png", "04.png", "05.png"]
        assert body["contact_sheet"] is True
        assert "#AIConsulting" in body["caption"]

    def test_unknown_deck_is_a_404(self, client):
        assert client.get("/api/decks/nope").status_code == 404

    @pytest.mark.parametrize("deck_id", ["..", "%2e%2e", "%2e%2e%2f%2e%2e%2fetc"])
    def test_deck_ids_cannot_escape_the_decks_directory(self, client, deck_id):
        """Unencoded ../.. is collapsed by the client before it is ever sent, so the
        encoded forms are what actually reach the handler."""
        assert client.get(f"/api/decks/{deck_id}").status_code == 404


class TestArtefacts:
    def test_serves_a_slide(self, client, rendered_deck):
        response = client.get(f"/api/decks/{rendered_deck.id}/slides/01.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_unknown_slide_is_a_404(self, client, rendered_deck):
        assert client.get(f"/api/decks/{rendered_deck.id}/slides/99.png").status_code == 404

    def test_a_slide_name_cannot_escape_the_slides_directory(self, client, rendered_deck):
        response = client.get(f"/api/decks/{rendered_deck.id}/slides/..%2f..%2fdeck.json")
        assert response.status_code == 404

    def test_serves_the_contact_sheet(self, client, rendered_deck):
        assert client.get(f"/api/decks/{rendered_deck.id}/contact-sheet.png").status_code == 200

    def test_contact_sheet_before_rendering_is_a_404(self, client, saved_deck):
        response = client.get(f"/api/decks/{saved_deck.id}/contact-sheet.png")
        assert response.status_code == 404 and response.json()["detail"] == "not rendered yet"

    def test_serves_the_caption(self, client, rendered_deck):
        response = client.get(f"/api/decks/{rendered_deck.id}/caption.txt")
        assert response.status_code == 200 and "#EnterpriseAI" in response.text

    def test_caption_before_rendering_is_a_404(self, client, saved_deck):
        assert client.get(f"/api/decks/{saved_deck.id}/caption.txt").status_code == 404

    def test_download_zips_everything_under_the_deck_id(self, client, rendered_deck):
        response = client.get(f"/api/decks/{rendered_deck.id}/download")
        assert response.status_code == 200
        assert rendered_deck.id in response.headers["content-disposition"]

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = sorted(archive.namelist())
        assert f"{rendered_deck.id}/deck.json" in names
        assert f"{rendered_deck.id}/slides/01.png" in names
        assert f"{rendered_deck.id}/contact-sheet.png" in names
        assert all(n.startswith(f"{rendered_deck.id}/") for n in names)


class TestRerender:
    def test_queues_a_rerender_job(self, client, container, saved_deck):
        response = client.post(f"/api/decks/{saved_deck.id}/render")
        assert response.status_code == 200
        snapshot = _wait(container.jobs, response.json()["job_id"])
        assert snapshot["status"] == "done"
        assert (container.repository.directory(saved_deck.id) / "contact-sheet.png").is_file()

    def test_rerendering_an_unknown_deck_is_a_404(self, client):
        assert client.post("/api/decks/nope/render").status_code == 404

    def test_a_hand_edit_is_picked_up(self, client, container, saved_deck):
        """The whole point of the endpoint: edit deck.json, re-render."""
        deck_file = container.repository.deck_file(saved_deck.id)
        payload = json.loads(deck_file.read_text(encoding="utf-8"))
        payload["slides"].insert(1, {"role": "content", "title": "Added by hand",
                                     "body": "A slide the operator wrote themselves."})
        deck_file.write_text(json.dumps(payload), encoding="utf-8")

        response = client.post(f"/api/decks/{saved_deck.id}/render")
        snapshot = _wait(container.jobs, response.json()["job_id"])
        assert snapshot["status"] == "done", snapshot["error"]
        assert len(container.repository.artifacts(saved_deck.id).slide_names()) == 6

    def test_a_hand_edit_that_breaks_the_rules_fails_the_job(self, client, container, saved_deck):
        deck_file = container.repository.deck_file(saved_deck.id)
        payload = json.loads(deck_file.read_text(encoding="utf-8"))
        payload["slides"].pop(1)          # 4 slides — below the minimum
        deck_file.write_text(json.dumps(payload), encoding="utf-8")

        response = client.post(f"/api/decks/{saved_deck.id}/render")
        snapshot = _wait(container.jobs, response.json()["job_id"])
        assert snapshot["status"] == "error"
        assert "needs >=5 slides" in snapshot["error"]


class TestUi:
    def test_serves_the_browser_ui(self, client):
        response = client.get("/")
        assert response.status_code == 200 and "<html" in response.text.lower()
