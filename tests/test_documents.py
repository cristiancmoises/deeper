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

    def geturl(self):
        return "https://google.serper.dev/search"


class Boundary:
    def __init__(self, payload=None, *, raw=None, error=None):
        self.raw = json.dumps(payload).encode() if raw is None else raw
        self.error = error
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return Response(self.raw)


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


def test_provider_uses_one_fixed_post_and_reports_normalized_url_identity(clock):
    boundary = Boundary(
        {
            "organic": [
                {
                    "title": "Same",
                    "link": "https://EXAMPLE.org/report.PDF#page=2",
                    "snippet": "Public",
                },
                {"title": "duplicate", "link": "https://example.org/report.PDF#page=7"},
                {"title": "Same", "link": "https://example.org/another.pdf"},
                {"title": "Same", "link": "https://other.example/info"},
                {"title": "Mismatch", "link": "https://example.org/file.docx"},
            ]
        }
    )
    events = []
    report = (
        module()
        .SerperSearch("test-only-key", opener=boundary)
        .search("José Silva", "pdf", events.append)
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
    assert request.full_url == "https://google.serper.dev/search"
    assert request.method == "POST"
    assert json.loads(request.data) == {
        "q": '"José Silva" filetype:pdf',
        "num": 10,
        "gl": "br",
        "hl": "pt-br",
    }
    assert request.get_header("X-api-key") == "test-only-key"
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
    boundary = Boundary({"organic": [{"title": "Bad", "link": url}]})
    report = (
        module()
        .SerperSearch("test-only-key", opener=boundary)
        .search("Ana Silva", "any")
    )
    assert report["state"] == "done"
    assert report["references"] == []
    assert len(boundary.calls) == 1


@pytest.mark.parametrize("host", ["a" * 254, "\u0130" * 127])
def test_oversized_canonical_hostname_is_skipped_without_discarding_valid_results(
    clock, host
):
    boundary = Boundary(
        {
            "organic": [
                {"title": "Malformed host", "link": f"https://{host}/report.pdf"},
                {"title": "Public report", "link": "https://example.org/report.pdf"},
            ]
        }
    )
    report = module().SerperSearch("test-only-key", opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert [reference["url"] for reference in report["references"]] == [
        "https://example.org/report.pdf"
    ]


def test_253_character_hostname_remains_available_without_truncation(clock):
    host = ".".join(["a" * 63, "b" * 63, "c" * 63, "d" * 61])
    boundary = Boundary({"organic": [{"link": f"https://{host}/report.pdf"}]})
    report = module().SerperSearch("test-only-key", opener=boundary).search("Ana Silva")
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
            "organic": [
                {"link": oversized_url},
                {"link": "https://example.org/report.pdf"},
            ]
        }
    )
    report = module().SerperSearch("test-only-key", opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert [reference["url"] for reference in report["references"]] == [
        "https://example.org/report.pdf"
    ]


def test_2048_character_canonical_url_remains_available_without_truncation(clock):
    raw_url = "https://\u0130/" + "a" * 2037
    canonical_url = "https://i\u0307/" + "a" * 2037
    assert len(canonical_url) == 2048
    boundary = Boundary({"organic": [{"link": raw_url}]})
    report = module().SerperSearch("test-only-key", opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert len(report["references"]) == 1
    assert report["references"][0]["url"] == canonical_url
    assert report["references"][0]["id"] == canonical_url
    assert report["references"][0]["source"] == "i\u0307"


def test_reference_fields_and_count_are_bounded_and_types_are_inferred(clock):
    boundary = Boundary(
        {
            "organic": [
                {
                    "link": f"https://example.org/{i}.html",
                    "title": "T" * 500,
                    "snippet": "S" * 2000,
                }
                for i in range(20)
            ]
        }
    )
    report = (
        module()
        .SerperSearch("test-only-key", opener=boundary)
        .search("Ana Silva", "any")
    )
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
        b'{"organic":{}}',
        b'{"organic":[null]}',
        b'{"organic":[{"link":123}]}',
        b'{"organic":[{"link":"https://example.org/","title":{}}]}',
        b'{"organic":[],"error":"sensitive upstream detail"}',
        b'{"organic": [], "extra": NaN}',
        b" " * (1024 * 1024 + 1),
    ],
    ids=[
        "invalid-json",
        "array",
        "null",
        "missing-organic",
        "wrong-organic",
        "null-item",
        "wrong-link",
        "wrong-title",
        "provider-error",
        "non-finite",
        "oversized",
    ],
)
def test_malformed_or_oversized_provider_data_has_fixed_public_error(clock, raw):
    boundary = Boundary(raw=raw)
    report = (
        module()
        .SerperSearch("test-only-key", opener=boundary)
        .search("Ana Silva", "any")
    )
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
        ("snippet", "Excerpt {}"),
        ("link", "https://{}.example.org/reference.pdf"),
        ("link", "https://example.org/{}.pdf"),
        ("link", "https://example.org/reference.pdf?q={}"),
        ("link", "https://example.org/reference.pdf#{}"),
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
        "link": "https://example.org/reference.pdf",
        "snippet": "Search excerpt",
    }
    item[field] = template.format(chr(surrogate_codepoint))
    # Boundary serializes with ensure_ascii=True: the invalid scalar arrives as
    # an escaped JSON string, rather than invalid UTF-8 rejected by byte decoding.
    boundary = Boundary({"organic": [item]})
    events = []
    report = (
        module()
        .SerperSearch("test-only-key", opener=boundary)
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
            "organic": [
                {
                    "title": "Public \U0001f4c4",
                    "snippet": "Excerpt \U0001f30d",
                    "link": "https://example.org/\U0001f4c4.pdf",
                }
            ]
        }
    )
    report = module().SerperSearch("test-only-key", opener=boundary).search("Ana Silva")
    assert report["state"] == "done"
    assert report["references"][0]["title"] == "Public \U0001f4c4"
    assert report["references"][0]["snippet"] == "Excerpt \U0001f30d"
    assert report["references"][0]["url"] == "https://example.org/\U0001f4c4.pdf"
    json.dumps(report, ensure_ascii=False).encode("utf-8")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", "Public \ud800"),
        ("snippet", "Excerpt \udfff"),
        ("link", "https://\ud800.example.org/reference.pdf"),
        ("link", "https://example.org/\udfff.pdf"),
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
        "link": "https://example.org/reference.pdf",
        "snippet": "Search excerpt",
    }
    item[field] = value
    search = module().SerperSearch(
        "test-only-key", opener=Boundary({"organic": [item]})
    )
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
                "https://google.serper.dev/search",
                429,
                "secret-test-token",
                Message(),
                None,
            ),
            "quota",
        ),
        (
            HTTPError(
                "https://google.serper.dev/search",
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
        .SerperSearch("secret-test-token", opener=boundary)
        .search("Ana Silva", "any", events.append)
    )
    assert report["state"] == "error"
    assert report["error_code"] == code
    assert "secret-test-token" not in json.dumps(report)
    assert events[-1] == report
    assert len(boundary.calls) == 1


def test_missing_credentials_never_calls_provider(monkeypatch, clock):
    monkeypatch.delenv("SERPER_API_KEY", raising=False)
    assert module().SerperSearch.from_env().available is False
    boundary = Boundary({"organic": []})
    report = module().SerperSearch("", opener=boundary).search("Ana Silva", "any")
    assert report["error_code"] == "unavailable"
    assert boundary.calls == []


@pytest.mark.parametrize("code", [None, [], {}, "secret-test-token"])
def test_unknown_error_codes_use_only_the_fixed_public_failure(code):
    error = module().DocumentSearchError(code)
    assert error.code == "failed"
    assert error.public_message == (
        "Não foi possível concluir a consulta ao provedor de busca. Tente novamente mais tarde."
    )
    assert str(error) == error.public_message


def test_daily_budget_is_shared_counts_failures_and_resets_on_utc_day(clock):
    boundary = Boundary(error=URLError("network failure"))
    first = module().SerperSearch("test-only-key", opener=boundary, daily_limit=1)
    second = module().SerperSearch("test-only-key", opener=boundary, daily_limit=1)
    assert first.search("Ana Silva", "any")["error_code"] == "failed"
    assert second.search("Ana Silva", "any")["error_code"] == "quota"
    assert len(boundary.calls) == 1
    clock["utc"] += 86400
    assert second.search("Ana Silva", "any")["error_code"] == "failed"
    assert len(boundary.calls) == 2


def test_spacing_across_midnight_charges_each_upstream_start_to_its_utc_day(clock):
    clock["utc"] = 86399.0
    starts = []

    class RecordingBoundary(Boundary):
        def open(self, request, *, timeout):
            starts.append(clock["utc"])
            return super().open(request, timeout=timeout)

    search = module().SerperSearch(
        "test-only-key", opener=RecordingBoundary({"organic": []}), daily_limit=2
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
    boundary = Boundary({"organic": []})
    search = module().SerperSearch("test-only-key", opener=boundary)
    assert search.search("Ana Silva", "any")["state"] == "done"
    assert search.search("Ana Souza", "any")["state"] == "done"
    assert clock["sleeps"] == [1.0]


@pytest.mark.parametrize("value", ["NaN", "inf", "-1", "0", "31", "invalid"])
def test_invalid_timeout_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv("DEEPER_NAME_TIMEOUT", value)
    with pytest.raises(ValueError):
        module().SerperSearch.from_env()


def test_env_configuration_is_private_and_bounded(monkeypatch, clock):
    monkeypatch.setenv("SERPER_API_KEY", "test-only-key")
    monkeypatch.setenv("DEEPER_NAME_DAILY_LIMIT", "1")
    monkeypatch.setenv("DEEPER_NAME_TIMEOUT", "2.5")
    search = module().SerperSearch.from_env()
    assert search.available
    assert "test-only-key" not in repr(search)


def test_continuously_readable_response_cannot_run_past_deadline(clock):
    class SlowResponse(Response):
        def read1(self, size: int | None = -1):
            clock["seconds"] += 6.5
            return super().read1(1)

    class SlowBoundary:
        def open(self, request, *, timeout):
            return SlowResponse(b'{"organic":[]}')

    report = (
        module()
        .SerperSearch("test-only-key", opener=SlowBoundary())
        .search("Ana Silva")
    )
    assert report["state"] == "error"
    assert report["error_code"] == "failed"


def test_default_budget_stops_the_101st_upstream_call(clock):
    boundary = Boundary({"organic": []})
    search = module().SerperSearch("test-only-key", opener=boundary)
    for _ in range(100):
        assert search.search("Ana Silva")["state"] == "done"
    assert search.search("Ana Silva")["error_code"] == "quota"
    assert len(boundary.calls) == 100


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "1.5", "invalid"])
def test_invalid_daily_limit_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv("DEEPER_NAME_DAILY_LIMIT", value)
    with pytest.raises(ValueError):
        module().SerperSearch.from_env()


def test_default_network_opener_refuses_redirects_without_following(monkeypatch, clock):
    import threading
    import urllib.request
    from http.server import BaseHTTPRequestHandler, HTTPServer

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(self.path)
            self.send_response(302)
            self.send_header("Location", "/must-not-be-requested")
            self.end_headers()

        def do_GET(self):
            calls.append(self.path)
            self.send_response(200)
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
        report = module().SerperSearch("test-only-key").search("Ana Silva", "any")
        assert report["state"] == "error"
        assert calls == ["/redirect"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
