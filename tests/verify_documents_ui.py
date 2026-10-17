"""Isolated Chromium QA for real document UI using clearly synthetic updates."""

import argparse
import json
import sys
import threading
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import render_template, request
from playwright.sync_api import expect, sync_playwright
from test_document_ui import ENGINES, FILE_TYPES, name_job
from waitress.server import TcpWSGIServer, create_server

from deeper.app import create_app
from deeper.config import Settings
from deeper.documents import _references
from deeper.jobs import JobManager

REFERENCE = {
    "id": "https://example.org/report.pdf",
    "url": "https://example.org/report.pdf",
    "title": "Synthetic public report",
    "source": "example.org",
    "file_type": "pdf",
    "snippet": "A synthetic search-index excerpt, not a verified document.",
}


def fixture_app():
    manager = SimpleNamespace(name_search_available=True)
    app = create_app(
        Settings(secret_key="synthetic-document-ui"), cast(JobManager, manager)
    )

    @app.get("/fixture-text.css")
    def enlarged_text():
        return ":root { font-size: 200%; }", 200, {"Content-Type": "text/css"}

    @app.get("/fixture/<case>")
    def fixture(case):
        request.view_args = {"token": "fixture"}
        job = None if case in ("form", "unavailable") else name_job()
        if case == "done":
            job = name_job(state="done", checked=1, references=[REFERENCE])
        if case == "empty":
            job = name_job(state="done", checked=1)
        if case == "quota":
            job = name_job(state="error", checked=1, error="Cota diária atingida.")
        return render_template(
            "index.html",
            username="Ana Maria",
            mode="name",
            file_type="pdf",
            consent=False,
            file_types=FILE_TYPES,
            engine="brave",
            engines=ENGINES,
            name_search_available=case != "unavailable",
            job=job,
            csrf_token="fixture",
            error=None,
        )

    return app


def payload(**changes):
    data = name_job(**changes)
    # Actual updates carry reference snapshots, not the initial query/link fields.
    data.pop("query")
    data.pop("google_url")
    if data["state"] != "queued":
        data["queue_position"] = 0
    return data


def verify_unicode_boundaries(browser, base):
    """Python's bounded provider strings must survive real browser validation."""
    url_prefix = "https://example.org/"
    boundary_url = url_prefix + "a" * 2023 + "😀.pdf"
    assert len(boundary_url) == 2048
    valid = [
        ("title-mixed", dict(REFERENCE, title="a" * 299 + "😀")),
        ("title-supplementary", dict(REFERENCE, title="😀" * 300)),
        ("snippet-mixed", dict(REFERENCE, snippet="a" * 1599 + "😀")),
        ("url-supplementary", dict(REFERENCE, id=boundary_url, url=boundary_url)),
    ]
    invalid = [
        ("title-over-limit", dict(REFERENCE, title="a" * 300 + "😀")),
        ("title-supplementary-over-limit", dict(REFERENCE, title="😀" * 301)),
        ("snippet-over-limit", dict(REFERENCE, snippet="a" * 1600 + "😀")),
        (
            "url-over-limit",
            dict(REFERENCE, id=boundary_url + "a", url=boundary_url + "a"),
        ),
        ("source-over-limit", dict(REFERENCE, source="a" * 253 + "😀")),
    ]
    evidence = []
    for accepted, cases in ((True, valid), (False, invalid)):
        for case, reference in cases:
            if accepted:
                # Exercise the actual upstream sanitizer before the browser boundary.
                sanitized = _references(
                    {
                        "status": "ok",
                        "web": [
                            {
                                "url": reference["url"],
                                "title": reference["title"],
                                "description": reference["snippet"],
                            }
                        ],
                    },
                    "pdf",
                )
                assert sanitized == [reference]
                references = sanitized
            else:
                # A valid entry preceding the invalid one detects partial DOM writes.
                references = [REFERENCE, dict(reference, id=reference["url"])]
            context = browser.new_context()
            page = context.new_page()
            calls, issues = [], []
            page.on("pageerror", lambda error, issues=issues: issues.append(str(error)))

            def updates(route, _request=None, *, references=references, calls=calls):
                calls.append(1)
                route.fulfill(
                    json=payload(state="done", checked=1, references=references)
                )

            page.route("**/updates*", updates)
            try:
                page.goto(base + "/fixture/queued")
                if accepted:
                    expect(page.locator("[data-document-reference]")).to_have_count(1)
                    expect(page.locator("[data-document-state]")).to_have_text(
                        "Busca concluída"
                    )
                    assert (
                        page.locator("[data-document-reference] h3").inner_text()
                        == reference["title"]
                    )
                    assert (
                        page.locator(".document-snippet").inner_text()
                        == reference["snippet"]
                    )
                    assert (
                        page.locator("[data-document-reference] a").get_attribute(
                            "href"
                        )
                        == reference["url"]
                    )
                    expect(page.locator("[data-document-update-error]")).to_be_hidden()
                    assert len(calls) == 1
                else:
                    expect(page.locator("[data-document-update-error]")).to_be_visible()
                    assert page.locator("[data-document-reference]").count() == 0
                    assert len(calls) == 3
                assert not issues, issues
                evidence.append(
                    {
                        "case": case,
                        "accepted": accepted,
                        "rendered_references": 1 if accepted else 0,
                        "poll_requests": len(calls),
                    }
                )
            finally:
                context.close()
    return evidence


def verify_native_search(browser):
    """Exercise the real mode route, consent form, scheduler, and update endpoint."""
    supplementary = "𐐀" * 59 + " " + "𐐀" * 60
    decomposed = "A\u0301" * 59 + " " + "e\u0301" * 60
    normalized = "Á" * 59 + " " + "é" * 60
    assert len(supplementary) == len(normalized) == 120
    name_cases = [
        ("basic", "Ana Maria", "Ana Maria"),
        ("supplementary-120", supplementary, supplementary),
        ("decomposed-nfc-120", decomposed, normalized),
        ("normalized-121-rejected", "A" * 60 + " " + "B" * 60, None),
    ]
    evidence = []
    for javascript, engine, (case, raw_name, normalized_name) in product(
        (True, False), ENGINES, name_cases
    ):
        release, completed = threading.Event(), threading.Event()
        calls = []

        class SyntheticSearch:
            available = True

            def __init__(self, release, completed, calls):
                self.release = release
                self.completed = completed
                self.calls = calls

            def search(self, name, file_type, emit, *, engine="brave"):
                self.calls.append((name, file_type, engine))
                assert self.release.wait(10)
                self.completed.set()
                return {"state": "done", "checked": 1, "references": [REFERENCE]}

        with JobManager(
            Settings(secret_key="synthetic-native-documents"),
            document_search=SyntheticSearch(release, completed, calls),
        ) as manager:
            server = cast(
                TcpWSGIServer,
                create_server(
                    create_app(manager.settings, manager),
                    host="127.0.0.1",
                    port=0,
                    threads=4,
                ),
            )
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            assert server.socket is not None
            base = f"http://127.0.0.1:{server.socket.getsockname()[1]}"
            context = browser.new_context(java_script_enabled=javascript)
            page = context.new_page()
            posts = []
            page.on(
                "request",
                lambda request, posts=posts: (
                    posts.append(request.url) if request.method == "POST" else None
                ),
            )
            try:
                page.goto(base)
                page.get_by_role("link", name="Nome completo", exact=True).click()
                assert page.url == base + "/?mode=name"
                expect(page.get_by_label("Mecanismo de busca")).to_have_value("brave")
                if engine == "google":
                    page.goto(base + "/?mode=name&engine=google")
                expect(page.get_by_label("Mecanismo de busca")).to_have_value(engine)
                page.get_by_label("Mecanismo de busca").select_option("brave")
                page.get_by_label("Mecanismo de busca").select_option(engine)
                searchbox = page.get_by_role("searchbox", name="Nome completo")
                searchbox.focus()
                # Native insertion exercises the browser's maxlength enforcement.
                page.keyboard.insert_text(raw_name)
                expect(searchbox).to_have_value(raw_name)
                assert searchbox.evaluate("element => element.validity.valid")
                page.get_by_label("Tipo de arquivo").select_option("pdf")
                page.get_by_role("button", name="Pesquisar").click()
                assert posts == [] and calls == []
                page.get_by_role("checkbox").check()
                with page.expect_response(
                    lambda response, *, base=base: (
                        response.url == base + "/search"
                        and response.request.method == "POST"
                    )
                ) as post:
                    searchbox.press("Enter")
                if normalized_name is None:
                    assert post.value.status == 422
                    expect(page.locator("#search-error")).to_contain_text("120")
                    expect(page.get_by_label("Mecanismo de busca")).to_have_value(
                        engine
                    )
                    assert calls == [] and len(posts) == 1
                    evidence.append(
                        {
                            "case": case,
                            "javascript": javascript,
                            "engine": engine,
                            "status": 422,
                            "provider_calls": 0,
                        }
                    )
                    continue
                assert post.value.status == 303
                expect(page.locator("[data-document-state]")).to_have_text(
                    "Buscando referências"
                )
                expect(page.locator("[data-document-engine]")).to_have_text(
                    f"SecuritySearch · {ENGINES[engine]}"
                )
                expect(page.get_by_label("Mecanismo de busca")).to_have_value(engine)
                release.set()
                assert completed.wait(3)
                if not javascript:
                    page.get_by_role("link", name="Atualizar", exact=True).click()
                expect(page.locator("[data-document-reference]")).to_have_count(1)
                assert calls == [(normalized_name, "pdf", engine)]
                assert len(posts) == 1
                expect(page.locator("[data-document-progress-label]")).to_contain_text(
                    "1 de 1 solicitação"
                )
                evidence.append(
                    {
                        "case": case,
                        "javascript": javascript,
                        "engine": engine,
                        "status": 303,
                        "provider_calls": 1,
                    }
                )
            finally:
                release.set()
                context.close()
                server.close()
                thread.join(timeout=3)
    return evidence


def verify_rejected_engine(browser):
    """A tampered paid engine must fail in the actual app before any search."""

    class NeverSearch:
        available = True

        def search(self, *args, **kwargs):
            raise AssertionError("An invalid engine reached the search provider")

    with JobManager(
        Settings(secret_key="synthetic-rejected-engine"), document_search=NeverSearch()
    ) as manager:
        server = cast(
            TcpWSGIServer,
            create_server(
                create_app(manager.settings, manager),
                host="127.0.0.1",
                port=0,
                threads=4,
            ),
        )
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        assert server.socket is not None
        base = f"http://127.0.0.1:{server.socket.getsockname()[1]}"
        context = browser.new_context()
        try:
            page = context.new_page()
            page.goto(base + "/?mode=name")
            csrf = page.locator('input[name="csrf_token"]').input_value()
            response = context.request.post(
                base + "/search",
                form={
                    "csrf_token": csrf,
                    "mode": "name",
                    "username": "Ana Maria",
                    "file_type": "pdf",
                    "consent": "1",
                    "engine": "google_api",
                },
            )
            assert response.status == 422
            response = context.request.get(base + "/?mode=name&engine=google_api")
            assert response.status == 422
            assert manager._jobs == {}
        finally:
            context.close()
            server.close()
            thread.join(timeout=3)
    return {
        "engine": "google_api",
        "get_status": 422,
        "post_status": 422,
        "jobs_created": 0,
    }


def verify(browser, base, output):
    evidence = []
    for width in (320, 768, 1024, 1440):
        context = browser.new_context(
            viewport={"width": width, "height": 1000}, reduced_motion="reduce"
        )
        page = context.new_page()
        issues, navigations = [], []
        page.on("pageerror", lambda error, issues=issues: issues.append(str(error)))
        page.on(
            "console",
            lambda message, issues=issues: (
                issues.append(message.text)
                if message.type in ("error", "warning")
                else None
            ),
        )
        update = {"data": payload()}
        page.route(
            "**/updates*",
            lambda route, _request=None, *, update=update: route.fulfill(
                json=update["data"]
            ),
        )
        page.goto(base + "/fixture/queued")
        expect(page.locator("[data-document-queue]")).to_contain_text("2")
        expect(page.locator("[data-document-announcement]")).to_contain_text(
            "posição 2"
        )
        page.on(
            "framenavigated",
            lambda frame, page=page, navigations=navigations: (
                navigations.append(frame.url) if frame == page.main_frame else None
            ),
        )
        update["data"] = payload(state="running", queue_position=None)
        expect(page.locator("[data-document-state]")).to_have_text(
            "Buscando referências"
        )
        expect(page.locator("[data-document-queue]")).to_be_hidden()
        hostile = dict(
            REFERENCE,
            title="<img src=x onerror=alert(1)>",
            snippet="<script>window.unsafe=true</script>",
        )
        update["data"] = payload(state="done", checked=1, references=[hostile, hostile])
        expect(page.locator("[data-document-reference]")).to_have_count(1)
        expect(page.locator("[data-document-state]")).to_have_text("Busca concluída")
        assert (
            page.locator("[data-document-reference] h3").inner_text()
            == hostile["title"]
        )
        assert page.locator("main img, main script:not([src])").count() == 0
        assert (
            page.locator("[data-document-reference] a").get_attribute("href")
            == REFERENCE["url"]
        )
        assert not navigations
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert "Nome completo" in page.locator("body").aria_snapshot()
        page.screenshot(path=str(output / f"documents-{width}.png"), full_page=True)
        page.goto(base + "/fixture/form")
        for _ in range(7):
            page.keyboard.press("Tab")
        expect(
            page.get_by_role("link", name="Nome completo", exact=True)
        ).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.get_by_role("searchbox", name="Nome completo")).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.get_by_role("button", name="Pesquisar")).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.get_by_label("Tipo de arquivo")).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.get_by_label("Mecanismo de busca")).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.get_by_role("checkbox")).to_be_focused()
        assert page.get_by_role("checkbox").evaluate(
            "element => !element.checkValidity()"
        )
        if width == 320:
            page.add_style_tag(url=base + "/fixture-text.css")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / "documents-text-200.png"), full_page=True)
        assert not issues, issues
        evidence.append(
            {
                "width": width,
                "overflow": False,
                "keyboard": True,
                "no_reload": True,
                "escaped_markup": True,
                "reduced_motion": True,
                "console_issues": issues,
            }
        )
        context.close()

    # No JavaScript still exposes mode switching, consent, and completed results.
    context = browser.new_context(
        java_script_enabled=False, viewport={"width": 320, "height": 1000}
    )
    page = context.new_page()
    page.goto(base + "/fixture/done")
    expect(page.locator("[data-document-reference]")).to_have_count(1)
    expect(page.get_by_role("checkbox")).to_be_visible()
    assert (
        page.get_by_role("link", name="Nome completo", exact=True).get_attribute("href")
        == "/?mode=name"
    )
    page.screenshot(path=str(output / "documents-no-js.png"), full_page=True)
    context.close()

    for case, selector in (
        ("empty", "[data-document-empty]"),
        ("quota", "[data-document-error]"),
        ("unavailable", "[data-name-unavailable]"),
    ):
        page = browser.new_page()
        page.goto(base + "/fixture/" + case)
        expect(page.locator(selector)).to_be_visible()
        page.close()

    for case in (
        "malformed",
        "unsafe",
        "oversized",
        "paid-engine",
        "changed-engine",
        "404",
        "network",
    ):
        context = browser.new_context()
        page = context.new_page()
        calls = []

        def update_response(route, _request=None, *, case=case, calls=calls):
            calls.append(1)
            if case == "404":
                route.fulfill(status=404, json={"error": "Busca indisponível."})
            elif case == "network":
                route.abort("failed")
            elif case == "unsafe":
                route.fulfill(
                    json=payload(
                        state="done",
                        checked=1,
                        references=[
                            REFERENCE,
                            dict(
                                REFERENCE,
                                id="javascript:alert(1)",
                                url="javascript:alert(1)",
                            ),
                        ],
                    )
                )
            elif case == "oversized":
                route.fulfill(
                    json=payload(state="done", checked=1, references=[REFERENCE] * 11)
                )
            elif case in ("paid-engine", "changed-engine"):
                route.fulfill(
                    json=payload(
                        state="done",
                        checked=1,
                        references=[REFERENCE],
                        engine="google_api" if case == "paid-engine" else "google",
                    )
                )
            else:
                route.fulfill(
                    json=payload(state="done", checked=True, references=[REFERENCE])
                )

        page.route("**/updates*", update_response)
        page.goto(base + "/fixture/queued")
        expect(page.locator("[data-document-update-error]")).to_be_visible(
            timeout=12000
        )
        assert page.locator("[data-document-reference]").count() == 0
        if case == "404":
            expect(page.locator("[data-document-retry]")).to_be_hidden()
            assert len(calls) == 1
        else:
            assert len(calls) == 3
            retry = page.locator("[data-document-retry]")
            expect(retry).to_be_visible()
            page.unroute("**/updates*", update_response)
            page.route(
                "**/updates*",
                lambda route: route.fulfill(json=payload(state="done", checked=1)),
            )
            retry.click()
            expect(page.locator("[data-document-empty]")).to_be_visible()
        context.close()
    return evidence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--unicode-only", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    server = cast(
        TcpWSGIServer, create_server(fixture_app(), host="127.0.0.1", port=0, threads=4)
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    assert server.socket is not None
    base = f"http://127.0.0.1:{server.socket.getsockname()[1]}"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=args.browser, headless=True, chromium_sandbox=True
            )
            evidence = {
                "source": "synthetic fixtures; not live provider evidence",
                "browser": browser.version,
                "unicode_boundaries": verify_unicode_boundaries(browser, base),
            }
            if not args.unicode_only:
                evidence["views"] = verify(browser, base, output)
                evidence["native_name_boundaries"] = verify_native_search(browser)
                evidence["invalid_paid_engine"] = verify_rejected_engine(browser)
                evidence["native_form_js_and_no_js"] = True
            (output / "documents-verification.json").write_text(
                json.dumps(evidence, indent=2)
            )
            print(json.dumps(evidence, indent=2))
            browser.close()
    finally:
        server.close()
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
