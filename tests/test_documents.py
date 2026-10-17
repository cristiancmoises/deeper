"""Provider boundary tests: literal names, bounded references and paid-call guards."""

import io
import json
from email.message import Message
from http.client import IncompleteRead
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest


def module():
    from deeper import documents

    return documents


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("  Jose\u0301   da Silva  ", "José da Silva"),
        ("Ana\u00a0María O’Neill", "Ana María O’Neill"),
        ("J. Anne-Marie D'Angelo", "J. Anne-Marie D'Angelo"),
        ("王 小明", "王 小明"),
    ],
)
def test_name_normalizes_unicode_and_spaces(value, expected):
    assert module().validate_full_name(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        [],
        "",
        "Ana",
        "A .",
        "Ana 123",
        'Ana "Silva"',
        "Ana site:example.com",
        "Ana\nSilva",
        "Ana\tSilva",
        "Ana\x00Silva",
        "Ana\u202eSilva",
        "A" * 121 + " B",
        " " * 10000 + "Ana Silva",
    ],
)
def test_name_rejects_operators_controls_non_names_and_excessive_raw_input(value):
    with pytest.raises(ValueError):
        module().validate_full_name(value)


def test_query_is_literal_and_file_type_is_allowlisted():
    docs = module()
    assert docs.build_query(" José  Silva ", "pdf") == '"José Silva" filetype:pdf'
    assert docs.build_query("José Silva", "any") == '"José Silva"'
    assert set(docs.FILE_TYPES) == {
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
    }
    for value in ("PDF", "pdf OR doc", "exe", None, []):
        with pytest.raises(ValueError):
            docs.validate_file_type(value)
    url = urlsplit(docs.google_search_url("José Silva", "pdf"))
    assert (url.scheme, url.netloc, url.path) == ("https", "www.google.com", "/search")
    assert parse_qs(url.query) == {"q": ['"José Silva" filetype:pdf']}


class Response(io.BytesIO):
    status = 200
    request_url: str

    def geturl(self):
        return self.request_url


class Boundary:
    def __init__(self, payload=None, *, raw=None, error=None):
        self.raw = json.dumps(payload).encode() if raw is None else raw
        self.error = error
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        response = Response(self.raw)
        response.request_url = request.full_url
        return response


@pytest.fixture
def clock(monkeypatch):
    docs = module()
    values = {"seconds": 0.0, "utc": 86400.0, "sleeps": []}

    def sleep(seconds):
        values["sleeps"].append(seconds)
        values["seconds"] += seconds
        values["utc"] += seconds

    monkeypatch.setattr(
        docs,
        "time",
        SimpleNamespace(
            monotonic=lambda: values["seconds"], time=lambda: values["utc"], sleep=sleep
        ),
    )
    monkeypatch.setattr(docs, "_budget", docs._RequestBudget())
    return values


@pytest.mark.parametrize("engine", ["brave", "google"])
def test_provider_uses_one_fixed_keyless_get_and_reports_normalized_url_identity(
    clock, engine
):
    boundary = Boundary(
        {
            "status": "ok",
            "web": [
                {
                    "title": "Same",
                    "url": "https://EXAMPLE.org/report.PDF#page=2",
                    "description": "Public",
                },
                {"title": "duplicate", "url": "https://example.org/report.PDF#page=7"},
                {"title": "Same", "url": "https://example.org/another.pdf"},
                {"title": "Same", "url": "https://other.example/info"},
                {"title": "Mismatch", "url": "https://example.org/file.docx"},
            ],
        }
    )
    events = []
    report = (
        module()
        .SecuritySearch(opener=boundary)
        .search("José Silva", "pdf", events.append, engine=engine)
    )
    assert report == {
        "state": "done",
        "checked": 1,
        "total": 1,
        "unknown": 0,
        "references": [
            {
                "id": "https://example.org/report.PDF",
                "title": "Same",
                "url": "https://example.org/report.PDF",
                "snippet": "Public",
                "source": "example.org",
                "file_type": "pdf",
            },
            {
                "id": "https://example.org/another.pdf",
                "title": "Same",
                "url": "https://example.org/another.pdf",
                "snippet": "",
                "source": "example.org",
                "file_type": "pdf",
            },
            {
                "id": "https://other.example/info",
                "title": "Same",
                "url": "https://other.example/info",
                "snippet": "",
                "source": "other.example",
                "file_type": "unknown",
            },
        ],
    }
    assert events[0] == {
        "state": "running",
        "checked": 0,
        "total": 1,
        "unknown": 0,
        "references": [],
    }
    assert events[-1] == report
    assert len(boundary.calls) == 1
    request, timeout = boundary.calls[0]
    parts = urlsplit(request.full_url)
    assert (parts.scheme, parts.netloc, parts.path) == (
        "https",
        "securityops.co",
        "/api/v1/web",
    )
    assert request.method == "GET"
    assert request.data is None
    assert parse_qs(parts.query) == {
        "s": ['"José Silva" filetype:pdf'],
        "scraper": [engine],
        "extendedsearch": ["no"],
    }
    assert dict(request.header_items()) == {"Accept": "application/json"}
    assert timeout == 12


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "//example.org/a",
        "https://user:pass@example.org/a",
        "https://example.org:99999/a",
        "https://example.org/a\nB",
        "https://example.org/\\evil",
        "https://example.org/" + "a" * 2048,
    ],
)
def test_unsafe_reference_is_rejected_without_fetching_it(clock, url):
    boundary = Boundary({"status": "ok", "web": [{"title": "Bad", "url": url}]})
    report = module().SecuritySearch(opener=boundary).search("Ana Silva", "any")
    assert report["state"] == "done"
    assert report["references"] == []
    assert len(boundary.calls) == 1


@pytest.mark.parametrize("host", ["a" * 254, "\u0130" * 127])
def test_oversized_canonical_hostname_is_skipped_without_discarding_valid_results(
    clock, host
):
    boundary = Boundary(
        {
            "status": "ok",
            "web": [
                {"title": "Malformed host", "url": f"https://{host}/report.pdf"},
                {"title": "Public report", "url": "https://example.org/report.pdf"},
            ],
        }
    )
    report = module().SecuritySearch(opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert [reference["url"] for reference in report["references"]] == [
        "https://example.org/report.pdf"
    ]


def test_253_character_hostname_remains_available_without_truncation(clock):
    host = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 61])
    boundary = Boundary(
        {"status": "ok", "web": [{"url": f"https://{host}/report.pdf"}]}
    )
    report = module().SecuritySearch(opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert len(report["references"]) == 1
    assert report["references"][0]["source"] == host
    assert report["references"][0]["url"] == f"https://{host}/report.pdf"


def test_canonical_url_expansion_is_bounded_without_discarding_valid_results(clock):
    # U+0130 lowercases to two code points; the 2048-character raw URL becomes
    # 2049 characters after host normalization, while its host remains short.
    oversized_url = "https://\u0130/" + "a" * 2038
    assert len(oversized_url) == 2048
    boundary = Boundary(
        {
            "status": "ok",
            "web": [
                {"url": oversized_url},
                {"url": "https://example.org/report.pdf"},
            ],
        }
    )
    report = module().SecuritySearch(opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert [reference["url"] for reference in report["references"]] == [
        "https://example.org/report.pdf"
    ]


def test_2048_character_canonical_url_remains_available_without_truncation(clock):
    raw_url = "https://\u0130/" + "a" * 2037
    canonical_url = "https://i\u0307/" + "a" * 2037
    assert len(canonical_url) == 2048
    boundary = Boundary({"status": "ok", "web": [{"url": raw_url}]})
    report = module().SecuritySearch(opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert len(report["references"]) == 1
    assert report["references"][0]["url"] == canonical_url
    assert report["references"][0]["id"] == canonical_url
    assert report["references"][0]["source"] == "i\u0307"


def test_reference_fields_and_count_are_bounded_and_types_are_inferred(clock):
    boundary = Boundary(
        {
            "status": "ok",
            "web": [
                {
                    "url": f"https://example.org/{i}.html",
                    "title": "T" * 500,
                    "description": "S" * 2000,
                }
                for i in range(20)
            ],
        }
    )
    report = module().SecuritySearch(opener=boundary).search("Ana Silva", "any")
    assert len(report["references"]) == 10
    assert report["references"][0] == {
        "id": "https://example.org/0.html",
        "url": "https://example.org/0.html",
        "title": "T" * 300,
        "snippet": "S" * 1600,
        "source": "example.org",
        "file_type": "html",
    }


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b"[]",
        b"null",
        b"{}",
        b'{"status": "ok", "web":{}}',
        b'{"status": "ok", "web":[null]}',
        b'{"status": "ok", "web":[{"url":123}]}',
        b'{"status": "ok", "web":[{"url":"https://example.org/","title":{}}]}',
        b'{"status": "ok", "web":[],"error":"sensitive upstream detail"}',
        b'{"status": "ok", "web": [], "extra": NaN}',
        b" " * (1024 * 1024 + 1),
    ],
    ids=[
        "invalid-json",
        "array",
        "null",
        "missing-web",
        "wrong-web",
        "null-item",
        "wrong-url",
        "wrong-title",
        "provider-error",
        "non-finite",
        "oversized",
    ],
)
def test_malformed_or_oversized_provider_data_has_fixed_public_error(clock, raw):
    boundary = Boundary(raw=raw)
    report = module().SecuritySearch(opener=boundary).search("Ana Silva", "any")
    assert report["state"] == "error"
    assert report["error_code"] == "failed"
    assert report["references"] == []
    assert report["error"] == module().DocumentSearchError("failed").public_message
    assert len(boundary.calls) == 1


@pytest.mark.parametrize("surrogate_codepoint", [0xD800, 0xDFFF], ids=["high", "low"])
@pytest.mark.parametrize(
    ("field", "template"),
    [
        ("title", "Public {}"),
        ("description", "Excerpt {}"),
        ("url", "https://{}.example.org/reference.pdf"),
        ("url", "https://example.org/{}.pdf"),
        ("url", "https://example.org/reference.pdf?q={}"),
        ("url", "https://example.org/reference.pdf#{}"),
    ],
    ids=[
        "title",
        "snippet",
        "url-host-source",
        "url-path",
        "url-query",
        "url-fragment",
    ],
)
def test_escaped_lone_surrogates_fail_before_references_are_emitted(
    clock, field, template, surrogate_codepoint
):
    item = {
        "title": "Public reference",
        "url": "https://example.org/reference.pdf",
        "description": "Search excerpt",
    }
    item[field] = template.format(chr(surrogate_codepoint))
    # Boundary serializes with ensure_ascii=True: the invalid scalar arrives as
    # an escaped JSON string, rather than invalid UTF-8 rejected by byte decoding.
    boundary = Boundary({"status": "ok", "web": [item]})
    events = []
    report = (
        module()
        .SecuritySearch(opener=boundary)
        .search("Ana Silva", "any", events.append)
    )
    assert report["state"] == "error"
    assert report["error_code"] == "failed"
    assert report["error"] == module().DocumentSearchError("failed").public_message
    assert report["references"] == []
    assert events[-1] == report
    json.dumps(events, ensure_ascii=False).encode("utf-8")


def test_valid_non_bmp_metadata_is_preserved(clock):
    boundary = Boundary(
        {
            "status": "ok",
            "web": [
                {
                    "title": "Public \U0001f4c4",
                    "description": "Excerpt \U0001f30d",
                    "url": "https://example.org/\U0001f4c4.pdf",
                }
            ],
        }
    )
    report = module().SecuritySearch(opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert report["references"][0]["title"] == "Public \U0001f4c4"
    assert report["references"][0]["snippet"] == "Excerpt \U0001f30d"
    assert report["references"][0]["url"] == "https://example.org/\U0001f4c4.pdf"
    json.dumps(report, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Public \ud800"),
        ("description", "Excerpt \udfff"),
        ("url", "https://\ud800.example.org/reference.pdf"),
        ("url", "https://example.org/\udfff.pdf"),
    ],
    ids=["title", "snippet", "url-host-source", "url-path"],
)
def test_surrogate_provider_results_leave_real_job_html_and_updates_usable(
    clock, field, value
):
    from test_app import csrf
    from test_jobs import wait_for_job

    from deeper.app import create_app
    from deeper.config import Settings
    from deeper.jobs import JobManager

    item = {
        "title": "Public reference",
        "url": "https://example.org/reference.pdf",
        "description": "Search excerpt",
    }
    item[field] = value
    search = module().SecuritySearch(opener=Boundary({"status": "ok", "web": [item]}))
    settings = Settings(secret_key="unicode-provider-tests-only")
    with JobManager(settings, document_search=search) as manager:
        app = create_app(settings, manager)
        app.config["TESTING"] = True
        client = app.test_client()
        response = client.post(
            "/search",
            data={
                "username": "Ana Silva",
                "mode": "name",
                "file_type": "pdf",
                "consent": "1",
                "csrf_token": csrf(client),
            },
        )
        assert response.status_code == 303
        location = response.headers["Location"]
        with client.session_transaction() as session:
            owner = session["owner"]
        token = location.rsplit("/", 1)[-1]
        job = wait_for_job(manager, token, owner)
        # Exercise the real server-rendered boundary before inspecting the job:
        # malformed strings used to finish successfully then break UTF-8 HTML.
        results = client.get(location)
        assert results.status_code == 200
        results.data.decode("utf-8")
        updates = client.get(location + "/updates")
        assert updates.status_code == 200
        payload = updates.get_json()
        assert isinstance(payload, dict)
        assert payload["state"] == job["state"] == "error"
        assert payload["references"] == job["references"] == []
        assert job["error"] == module().DocumentSearchError("failed").public_message


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (URLError("secret-test-token"), "failed"),
        (TimeoutError("secret-test-token"), "failed"),
        (
            HTTPError(
                "https://securityops.co/api/v1/web",
                429,
                "secret-test-token",
                Message(),
                None,
            ),
            "quota",
        ),
        (
            HTTPError(
                "https://securityops.co/api/v1/web",
                302,
                "secret-test-token",
                Message(),
                None,
            ),
            "failed",
        ),
        (IncompleteRead(b"secret-test-token"), "failed"),
    ],
)
def test_provider_errors_are_not_retried_or_leaked(clock, error, code):
    boundary = Boundary(error=error)
    events = []
    report = (
        module()
        .SecuritySearch(opener=boundary)
        .search("Ana Silva", "any", events.append)
    )
    assert report["state"] == "error"
    assert report["error_code"] == code
    assert "secret-test-token" not in json.dumps(report)
    assert events[-1] == report
    assert len(boundary.calls) == 1


def test_provider_needs_no_credentials_and_ignores_legacy_key(monkeypatch, clock):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    assert module().SecuritySearch.from_env().available is True
    boundary = Boundary({"status": "ok", "web": []})
    report = module().SecuritySearch(opener=boundary).search("Ana Silva", "any")
    assert report["state"] == "done"
    monkeypatch.setenv("SERPER_API_KEY", "unused-legacy-key")
    assert module().SecuritySearch.from_env().available is True
    assert len(boundary.calls) == 1


@pytest.mark.parametrize(
    "engine", ["google_api", "Google", "", None, [], "brave&scraper=google_api"]
)
def test_invalid_engine_never_performs_io_or_consumes_budget(clock, engine):
    boundary = Boundary({"status": "ok", "web": []})
    search = module().SecuritySearch(opener=boundary, daily_limit=1)
    with pytest.raises(ValueError):
        search.search("Ana Silva", engine=engine)
    assert boundary.calls == []
    assert search.search("Ana Silva")["state"] == "done"


@pytest.mark.parametrize(
    "payload",
    [
        {"web": []},
        {"status": "error", "web": [], "message": "private upstream reason"},
        {"status": "rate limited", "web": []},
        {"status": "ok", "web": None},
    ],
)
def test_http_success_with_unsuccessful_payload_is_fixed_failure(clock, payload):
    boundary = Boundary(payload)
    report = (
        module().SecuritySearch(opener=boundary).search("Ana Silva", engine="google")
    )
    assert report["state"] == "error"
    assert report["error_code"] == "failed"
    assert report["error"] == module().DocumentSearchError("failed").public_message
    assert len(boundary.calls) == 1


@pytest.mark.parametrize("status", [401, 403, 503])
def test_unavailable_http_errors_are_fixed_without_fallback(clock, status):
    error = HTTPError(
        "https://securityops.co/api/v1/web",
        status,
        "private upstream reason",
        Message(),
        None,
    )
    boundary = Boundary(error=error)
    report = (
        module().SecuritySearch(opener=boundary).search("Ana Silva", engine="google")
    )
    assert report["state"] == "error"
    assert report["error_code"] == "unavailable"
    assert report["error"] == module().DocumentSearchError("unavailable").public_message
    assert len(boundary.calls) == 1


def test_successful_result_tail_is_not_examined_or_fetched(clock):
    boundary = Boundary(
        {
            "status": "ok",
            "web": [
                {
                    "title": "Public",
                    "description": "",
                    "url": f"https://example.org/{i}.pdf",
                }
                for i in range(10)
            ]
            + [None],
        }
    )
    report = module().SecuritySearch(opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert len(report["references"]) == 10
    assert len(boundary.calls) == 1


@pytest.mark.parametrize("code", [None, [], {}, "secret-test-token"])
def test_unknown_error_codes_use_only_the_fixed_public_failure(code):
    error = module().DocumentSearchError(code)
    assert error.code == "failed"
    assert error.public_message == (
        "Não foi possível concluir a consulta ao provedor de busca. Tente novamente mais tarde."
    )
    assert str(error) == error.public_message


def test_daily_budget_is_shared_across_engines_counts_failures_and_resets_on_utc_day(
    clock,
):
    boundary = Boundary(error=URLError("network failure"))
    first = module().SecuritySearch(opener=boundary, daily_limit=1)
    second = module().SecuritySearch(opener=boundary, daily_limit=1)
    assert first.search("Ana Silva", "any")["error_code"] == "failed"
    assert second.search("Ana Silva", "any", engine="google")["error_code"] == "quota"
    assert len(boundary.calls) == 1
    clock["utc"] += 86400
    assert second.search("Ana Silva", "any", engine="google")["error_code"] == "failed"
    assert len(boundary.calls) == 2


def test_spacing_across_midnight_charges_each_upstream_start_to_its_utc_day(clock):
    clock["utc"] = 86399.0
    starts = []

    class RecordingBoundary(Boundary):
        def open(self, request, *, timeout):
            starts.append(clock["utc"])
            return super().open(request, timeout=timeout)

    search = module().SecuritySearch(
        opener=RecordingBoundary({"status": "ok", "web": []}), daily_limit=2
    )
    reports = [search.search("Ana Silva") for _ in range(4)]
    assert starts == [86399.0, 86400.0, 86401.0]
    assert [report["state"] for report in reports] == ["done", "done", "done", "error"]
    assert reports[-1]["error_code"] == "quota"
    starts_per_day = {}
    for timestamp in starts:
        day = int(timestamp // 86400)
        starts_per_day[day] = starts_per_day.get(day, 0) + 1
    assert starts_per_day == {0: 1, 1: 2}


def test_calls_are_spaced_at_least_one_second(clock):
    boundary = Boundary({"status": "ok", "web": []})
    search = module().SecuritySearch(opener=boundary)
    assert search.search("Ana Silva", "any")["state"] == "done"
    assert search.search("Ana Souza", "any")["state"] == "done"
    assert clock["sleeps"] == [1.0]


@pytest.mark.parametrize("value", ["NaN", "inf", "-1", "0", "31", "invalid"])
def test_invalid_timeout_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv("DEEPER_NAME_TIMEOUT", value)
    with pytest.raises(ValueError):
        module().SecuritySearch.from_env()


def test_env_configuration_is_private_and_bounded(monkeypatch, clock):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-key")
    monkeypatch.setenv("DEEPER_NAME_DAILY_LIMIT", "1")
    monkeypatch.setenv("DEEPER_NAME_TIMEOUT", "2.5")
    search = module().SecuritySearch.from_env()
    assert search.available
    assert "test-only-key" not in repr(search)


def test_continuously_readable_response_cannot_run_past_deadline(clock):
    class SlowResponse(Response):
        def read1(self, size: int | None = -1):
            clock["seconds"] += 6.5
            return super().read1(1)

    class SlowBoundary:
        def open(self, request, *, timeout):
            response = SlowResponse(b'{"status": "ok", "web":[]}')
            response.request_url = request.full_url
            return response

    report = module().SecuritySearch(opener=SlowBoundary()).search("Ana Silva")
    assert report["state"] == "error"
    assert report["error_code"] == "failed"


def test_default_budget_stops_the_101st_upstream_call(clock):
    boundary = Boundary({"status": "ok", "web": []})
    search = module().SecuritySearch(opener=boundary)
    for _ in range(100):
        assert search.search("Ana Silva")["state"] == "done"
    assert search.search("Ana Silva")["error_code"] == "quota"
    assert len(boundary.calls) == 100


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "1.5", "invalid"])
def test_invalid_daily_limit_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv("DEEPER_NAME_DAILY_LIMIT", value)
    with pytest.raises(ValueError):
        module().SecuritySearch.from_env()


def test_default_network_opener_refuses_redirects_without_following(monkeypatch, clock):
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, HTTPServer

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/must-not-be-requested")
            self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = urllib.request.Request

    def local_request(*args, **kwargs):
        args = (f"http://127.0.0.1:{server.server_port}/redirect",) + args[1:]
        return original(*args, **kwargs)

    monkeypatch.setattr(module(), "Request", local_request)
    try:
        report = module().SecuritySearch().search("Ana Silva", "any")
        assert report["state"] == "error"
        assert calls == ["/redirect"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
