"""Queue positions are visible without exposing any other search data."""

from types import SimpleNamespace
from typing import cast

import pytest
from bs4 import BeautifulSoup

from deeper.app import create_app
from deeper.config import Settings
from deeper.jobs import JobManager


def render_job(**changes):
    job = {
        "state": "queued",
        "username": "synthetic",
        "cache_age": None,
        "checked": 0,
        "total": 0,
        "elapsed": 0,
        "cursor": 0,
        "profiles": [],
        "unknown": 0,
        "error": "",
    }
    job.update(changes)
    manager = SimpleNamespace(snapshot=lambda token, owner: job if owner else None)
    app = create_app(
        Settings(secret_key="test-queue-ui"), manager=cast(JobManager, manager)
    )
    client = app.test_client()
    client.get("/")
    response = client.get("/search/synthetic-queue")
    assert response.status_code == 200
    return BeautifulSoup(response.data, "html.parser")


def test_queued_page_shows_current_position_and_announces_it_outside_busy_results():
    page = render_job(queue_position=3)

    position = page.select_one("[data-queue-position]")
    assert position is not None
    assert not position.has_attr("hidden")
    assert "3" in position.get_text() and "fila" in position.get_text().lower()
    announcement = page.select_one("[data-update-status]")
    assert announcement is not None
    assert announcement["aria-live"] == "polite"
    assert announcement["aria-atomic"] == "true"
    assert "3" in announcement.get_text() and "fila" in announcement.get_text().lower()
    assert announcement.find_parent(attrs={"aria-busy": "true"}) is None
    assert not page.select(".profile")


@pytest.mark.parametrize("state", ["running", "done", "partial", "error"])
def test_nonqueued_page_does_not_show_a_queue_position(state):
    page = render_job(state=state, queue_position=0)

    position = page.select_one("[data-queue-position]")
    assert position is None or position.has_attr("hidden")
    main = page.select_one("main")
    assert main is not None
    assert "fila" not in main.get_text().lower()


@pytest.mark.parametrize(
    "position",
    [
        None,
        True,
        0,
        -1,
        1.5,
        2**53,
        "3",
        "<img src=x onerror=alert(1)>",
    ],
)
def test_invalid_snapshot_position_keeps_generic_queue_copy(position):
    page = render_job(queue_position=position)

    position = page.select_one("[data-queue-position]")
    assert position is None or position.has_attr("hidden")
    state = page.select_one("[data-search-state]")
    assert state is not None
    assert state.get_text() == "Aguardando para buscar"
    assert not page.select("main img")


def test_snapshot_without_queue_position_keeps_generic_queue_copy():
    page = render_job()

    state = page.select_one("[data-search-state]")
    assert state is not None
    assert state.get_text() == "Aguardando para buscar"


def test_source_navigation_has_named_links_and_local_logos_for_every_repository():
    app = create_app(
        Settings(secret_key="test-source-navigation"),
        manager=cast(JobManager, SimpleNamespace()),
    )
    client = app.test_client()
    page = BeautifulSoup(client.get("/").data, "html.parser")

    navigation = page.select_one('nav[aria-label="Código-fonte"]')
    assert navigation is not None
    links = navigation.select("a[href]")
    assert {str(link["href"]) for link in links} == {
        "https://git.securityops.co/cristiancmoises/deeper",
        "https://git.securityops.com.br/cristiancmoises/deeper",
        "https://github.com/cristiancmoises/deeper",
        "https://codeberg.org/berkeley/deeper",
    }
    assert len(links) == 4
    assert len({str(link.get("aria-label")) for link in links}) == 4
    for link in links:
        assert link.get("aria-label")
        logo = link.select_one('img[alt=""]')
        assert logo is not None
        source = logo.get("src")
        assert isinstance(source, str) and source.startswith("/static/icons/")
        assert logo.get("width") == logo.get("height") == "20"
        asset = client.get(source)
        assert asset.status_code == 200
        assert asset.content_type.startswith("image/svg+xml")
    assert "img-src 'self'" in client.get("/").headers["Content-Security-Policy"]


def test_source_navigation_remains_available_while_search_is_queued():
    page = render_job(queue_position=2)

    assert len(page.select('nav[aria-label="Código-fonte"] a[href]')) == 4
    assert page.select_one("[data-queue-position]") is not None
