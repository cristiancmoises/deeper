"""Form validation, sharing consent and session ownership for name jobs."""

import pytest
from flask import template_rendered
from test_app import csrf
from test_jobs import complete_runner, wait_for_job
from test_name_jobs import DocumentSearch

from deeper.app import create_app
from deeper.config import Settings
from deeper.jobs import JobManager


@pytest.fixture
def name_bundle():
    search = DocumentSearch()
    settings = Settings(secret_key="name-tests-only")
    with JobManager(
        settings, runner=complete_runner, document_search=search
    ) as manager:
        app = create_app(settings, manager)
        app.config["TESTING"] = True
        yield app, manager, search


def test_name_mode_is_selected_without_javascript_and_receives_render_contract(
    name_bundle,
):
    app, _, _ = name_bundle
    contexts = []

    def collect(sender, template, context, **extra):
        contexts.append(context)

    with template_rendered.connected_to(collect, app):
        response = app.test_client().get("/?mode=name")
    assert response.status_code == 200
    context = contexts[-1]
    assert context["mode"] == "name" and context["file_type"] == "any"
    assert context["name_search_available"] is True
    assert "pdf" in context["file_types"] and context["consent"] is False
    assert context["engine"] == "brave"
    assert context["engines"] == {"brave": "Brave", "google": "Google CSE"}


@pytest.mark.parametrize(
    "engine, status", [("google", 200), ("google_api", 422), ("anything", 422)]
)
def test_name_get_validates_engine_and_preserves_optional_selection(
    name_bundle, engine, status
):
    app, _, search = name_bundle
    contexts = []

    def collect(sender, template, context, **extra):
        contexts.append(context)

    with template_rendered.connected_to(collect, app):
        response = app.test_client().get("/?mode=name&engine=" + engine)
    assert response.status_code == status
    if status == 200:
        assert contexts[-1]["engine"] == engine
    assert search.calls == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"consent": ""},
        {"consent": "true"},
        {"username": "Maria"},
        {"username": "Maria Silva OR site:private"},
        {"file_type": "exe"},
        {"mode": "bad"},
        {"engine": "google_api"},
        {"engine": "brave&scraper=google_api"},
    ],
)
def test_name_form_rejects_missing_consent_and_invalid_intent_without_work(
    name_bundle, overrides
):
    app, _, search = name_bundle
    client = app.test_client()
    data = {
        "username": "Maria Silva",
        "mode": "name",
        "file_type": "pdf",
        "consent": "1",
        "csrf_token": csrf(client),
    }
    data.update(overrides)
    response = client.post("/search", data=data)
    assert response.status_code == 422
    assert search.calls == []
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("engine", ["brave", "google"])
def test_name_post_uses_private_same_updates_route_and_keeps_full_references(
    name_bundle,
    engine,
):
    app, manager, search = name_bundle
    client = app.test_client()
    response = client.post(
        "/search",
        data={
            "username": " Maria  Silva ",
            "mode": "name",
            "file_type": "pdf",
            "consent": "1",
            "engine": engine,
            "csrf_token": csrf(client),
        },
    )
    assert response.status_code == 303
    location = response.headers["Location"]
    with client.session_transaction() as session:
        owner = session["owner"]
    wait_for_job(manager, location.rsplit("/", 1)[-1], owner)
    updates = client.get(location + "/updates")
    assert updates.status_code == 200
    assert updates.json["mode"] == "name" and updates.json["file_type"] == "pdf"
    assert updates.json["engine"] == engine
    assert len(updates.json["references"]) == 1 and updates.json["cursor"] == 0
    assert (
        client.get(location + "/updates").json["references"]
        == updates.json["references"]
    )
    assert app.test_client().get(location).status_code == 404
    assert app.test_client().get(location + "/updates").status_code == 404
    assert search.calls == [("Maria Silva", "pdf", engine)]


def test_validation_error_preserves_selected_engine_and_names_consent_recipient(
    name_bundle,
):
    app, _, search = name_bundle
    client = app.test_client()
    contexts = []

    def collect(sender, template, context, **extra):
        contexts.append(context)

    token = csrf(client)
    with template_rendered.connected_to(collect, app):
        response = client.post(
            "/search",
            data={
                "username": "Maria Silva",
                "mode": "name",
                "engine": "google",
                "csrf_token": token,
            },
        )
    assert response.status_code == 422
    assert contexts[-1]["engine"] == "google"
    assert "SecuritySearch" in contexts[-1]["error"]
    assert "Google CSE" in contexts[-1]["error"]
    assert search.calls == []


def test_missing_provider_is_explicit_and_does_not_submit_name(name_bundle):
    app, manager, search = name_bundle
    search.available = False
    client = app.test_client()
    response = client.post(
        "/search",
        data={
            "username": "Maria Silva",
            "mode": "name",
            "consent": "1",
            "csrf_token": csrf(client),
        },
    )
    assert response.status_code == 503
    assert search.calls == []
    assert manager.name_search_available is False


def test_name_mode_still_requires_csrf(name_bundle):
    app, _, search = name_bundle
    client = app.test_client()
    client.get("/?mode=name")
    response = client.post(
        "/search",
        data={
            "username": "Maria Silva",
            "mode": "name",
            "file_type": "any",
            "consent": "1",
        },
    )
    assert response.status_code == 400
    assert search.calls == []
