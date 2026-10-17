"""Name-mode forms and server snapshots remain useful without JavaScript."""

from types import SimpleNamespace
from typing import cast

import pytest
from bs4 import BeautifulSoup
from flask import render_template

from deeper.app import create_app
from deeper.config import Settings
from deeper.jobs import JobManager

FILE_TYPES = {
    kind: kind.upper()
    for kind in (
        "any",
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "odt",
        "ods",
        "odp",
        "rtf",
        "txt",
        "csv",
    )
}
ENGINES = {"brave": "Brave", "google": "Google CSE"}


def render_name(*, available=True, job=None, **changes):
    app = create_app(
        Settings(secret_key="document-ui-fixture"),
        manager=cast(JobManager, SimpleNamespace()),
    )
    values = {
        "username": "Ana Maria",
        "mode": "name",
        "file_type": "pdf",
        "consent": False,
        "name_search_available": available,
        "file_types": FILE_TYPES,
        "engine": "brave",
        "engines": ENGINES,
        "csrf_token": "fixture",
        "error": None,
        "job": job,
    }
    values.update(changes)
    with app.test_request_context("/search/fixture"):
        # url_for uses this parameter for the private updates/results routes.
        from flask import request

        request.view_args = {"token": "fixture"}
        return BeautifulSoup(render_template("index.html", **values), "html.parser")


def name_job(**changes):
    job = {
        "username": "Ana Maria",
        "mode": "name",
        "file_type": "pdf",
        "engine": "brave",
        "state": "queued",
        "query": '"Ana Maria" filetype:pdf',
        "google_url": "https://www.google.com/search?q=%22Ana+Maria%22+filetype%3Apdf",
        "references": [],
        "cursor": 0,
        "profiles": [],
        "checked": 0,
        "total": 1,
        "elapsed": 0,
        "error": "",
        "unknown": 0,
        "cache_age": None,
        "queue_position": 2,
    }
    job.update(changes)
    return job


def element(page, selector):
    found = page.select_one(selector)
    assert found is not None, selector
    return found


def test_name_form_submits_mode_filter_and_explicit_required_consent():
    # Missing hidden mode/filter/consent would silently submit a username search.
    page = render_name()
    assert page.select_one('a[href="/?mode=name"][aria-current="page"]')
    assert page.select_one('input[name="mode"][value="name"]')
    assert (
        element(page, 'label[for="username"]').get_text(strip=True) == "Nome completo"
    )
    assert element(page, 'input[name="username"]')["maxlength"] == "1024"
    assert "120" in element(page, "#name-help").get_text()
    assert "normaliza" in element(page, "#name-help").get_text()
    options = page.select('select[name="file_type"] option')
    assert [option["value"] for option in options] == list(FILE_TYPES)
    assert page.select_one('option[value="pdf"][selected]')
    checkbox = page.select_one('input[name="consent"][value="1"][required]')
    assert checkbox and not checkbox.has_attr("checked")
    consent = element(page, 'label[for="name-consent"]').get_text()
    assert "SecuritySearch" in consent and "mecanismo selecionado" in consent
    assert "Brave" in consent and "Google CSE" in consent
    assert len(page.select('nav[aria-label="Código-fonte"] a')) == 4


@pytest.mark.parametrize("engine", ["brave", "google"])
def test_name_engine_native_selection_preserves_the_selected_mechanism(engine):
    # A lost selected option would send a different mechanism on a native resubmit.
    page = render_name(engine=engine)
    options = page.select('select[name="engine"] option')
    assert [option["value"] for option in options] == ["brave", "google"]
    assert element(page, 'select[name="engine"] option[selected]')["value"] == engine
    assert (
        element(page, 'label[for="engine"]').get_text(strip=True)
        == "Mecanismo de busca"
    )


def test_name_engine_defaults_to_brave_and_username_has_no_engine_control():
    assert (
        element(render_name(), 'select[name="engine"] option[selected]')["value"]
        == "brave"
    )
    assert not render_name(mode="username").select('select[name="engine"]')


@pytest.mark.parametrize("engine,label", list(ENGINES.items()))
def test_job_labels_its_actual_engine_and_google_link_is_a_separate_query(
    engine, label
):
    # The submitted form's choice must never relabel an existing job's provider.
    page = render_name(
        engine="google" if engine == "brave" else "brave", job=name_job(engine=engine)
    )
    assert (
        element(page, "[data-document-engine]").get_text(strip=True)
        == f"SecuritySearch · {label}"
    )
    google = element(page, "[data-google-search]").get_text()
    assert "consulta" in google.lower() and "externa" in google.lower()
    assert "mais resultados" not in google.lower()


def test_name_unavailable_explains_why_submit_is_disabled():
    # An unavailable provider must not look like an operable paid search.
    page = render_name(available=False)
    assert page.select_one('button[type="submit"][disabled]')
    assert "indisponível" in element(page, "[data-name-unavailable]").get_text()


def test_name_queue_uses_provider_progress_and_separate_script():
    # Name jobs count one provider request, never Maigret sites or guessed handles.
    page = render_name(job=name_job())
    assert page.select_one("[data-document-results][aria-busy=true]")
    assert "solicitação" in element(page, "[data-document-progress-label]").get_text()
    assert "2" in element(page, "[data-document-queue]").get_text()
    live = page.select_one("[data-document-announcement][aria-live=polite]")
    assert live and not live.find_parent(attrs={"aria-busy": "true"})
    assert page.select_one('script[src="/static/document-progress.js"]')
    assert not page.select_one('script[src="/static/search-progress.js"]')
    assert "@Ana Maria" not in page.get_text()


def test_completed_reference_is_escaped_and_honestly_labeled():
    # Provider markup must remain text and metadata must not imply content verification.
    reference = {
        "id": "https://example.org/report.pdf",
        "url": "https://example.org/report.pdf",
        "title": "<img src=x onerror=alert(1)>",
        "snippet": "<script>bad()</script>",
        "source": "example.org",
        "file_type": "pdf",
    }
    page = render_name(job=name_job(state="done", checked=1, references=[reference]))
    link = page.select_one("[data-document-reference] h3 a")
    assert link and link.get_text() == reference["title"]
    assert link["rel"] == ["noopener", "noreferrer"]
    assert not page.select("main img, main script:not([src])")
    assert "inferido" in element(page, "[data-document-reference]").get_text()
    assert "identidade" in element(page, "[data-document-disclosure]").get_text()
    assert "Google" in element(page, "[data-google-search]").get_text()
    assert not page.select("[data-profile-grid], [data-profile-name]")


@pytest.mark.parametrize(
    "state,error", [("done", ""), ("error", "Cota diária atingida.")]
)
def test_terminal_empty_and_error_states_do_not_claim_the_other(state, error):
    # A provider failure must not be displayed as a successful zero-result search.
    page = render_name(job=name_job(state=state, checked=1, error=error))
    empty = element(page, "[data-document-empty]")
    terminal = element(page, "[data-document-error]")
    assert empty.has_attr("hidden") == (state == "error")
    assert terminal.has_attr("hidden") == (state != "error")
    if error:
        assert error in terminal.get_text()
