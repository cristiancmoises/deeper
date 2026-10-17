"""Name work shares username admission, private caching and executor slots."""

import threading

import pytest
from test_jobs import complete_runner, wait_for_job

from deeper.config import Settings
from deeper.jobs import CapacityError, JobManager, SessionCapacityError

REFERENCE = {
    "id": "https://example.com/public.pdf",
    "title": "Public reference",
    "url": "https://example.com/public.pdf",
    "snippet": "Search index excerpt",
    "source": "example.com",
    "file_type": "pdf",
}


class DocumentSearch:
    available = True

    def __init__(self, references=None):
        self.calls = []
        self.references = references if references is not None else [REFERENCE]

    def search(self, name, file_type, emit):
        self.calls.append((name, file_type))
        return {
            "state": "done",
            "checked": 1,
            "total": 1,
            "unknown": 0,
            "references": self.references,
        }


def test_name_reports_full_private_bounded_references_and_zero_profile_cursor():
    search = DocumentSearch(
        [
            dict(REFERENCE, id=str(i), url=f"https://example.com/{i}.pdf")
            for i in range(15)
        ]
    )
    with JobManager(
        Settings(), runner=complete_runner, document_search=search
    ) as manager:
        token = manager.submit(
            "  Maria   Silva ", "owner", mode="name", file_type="pdf"
        )
        job = wait_for_job(manager, token, "owner")
        assert job["username"] == "Maria Silva"
        assert job["mode"] == "name" and job["file_type"] == "pdf"
        assert job["query"] == '"Maria Silva" filetype:pdf'
        assert job["google_url"].startswith("https://www.google.com/search?")
        assert job["checked"] == job["total"] == 1
        assert job["cursor"] == 0 and job["profiles"] == []
        assert len(job["references"]) == 10
        updates = manager.updates(token, "owner", 0)
        assert updates is not None
        assert updates["references"] == job["references"]
        updates["references"].clear()
        refreshed = manager.updates(token, "owner", 0)
        assert refreshed is not None
        assert len(refreshed["references"]) == 10
        assert manager.snapshot(token, "stranger") is None
        assert manager.updates(token, "stranger", 0) is None
        with pytest.raises(ValueError):
            manager.updates(token, "owner", 1)


def test_name_cache_separates_filter_owner_and_mode_without_calling_username_runner():
    search = DocumentSearch()
    with JobManager(
        Settings(), runner=complete_runner, document_search=search
    ) as manager:
        first = manager.submit("Maria Silva", "owner", mode="name", file_type="pdf")
        wait_for_job(manager, first, "owner")
        assert (
            manager.submit("Maria  Silva", "owner", mode="name", file_type="pdf")
            == first
        )
        filtered = manager.submit("Maria Silva", "owner", mode="name", file_type="doc")
        wait_for_job(manager, filtered, "owner")
        other = manager.submit("Maria Silva", "other", mode="name", file_type="pdf")
        wait_for_job(manager, other, "other")
        assert len({first, filtered, other}) == 3
        assert search.calls == [
            ("Maria Silva", "pdf"),
            ("Maria Silva", "doc"),
            ("Maria Silva", "pdf"),
        ]
        old = manager.submit("synthetic", "owner")
        old_job = wait_for_job(manager, old, "owner")
        old_updates = manager.updates(old, "owner", 0)
        assert old_updates is not None
        assert old_job["profiles"] and "references" not in old_updates


@pytest.mark.parametrize(
    "kwargs",
    [
        {"mode": "other"},
        {"file_type": "pdf OR txt"},
        {"mode": "name", "file_type": "exe"},
    ],
)
def test_manager_rejects_untrusted_mode_and_filetype_before_work(kwargs):
    search = DocumentSearch()
    with JobManager(
        Settings(), runner=complete_runner, document_search=search
    ) as manager:
        with pytest.raises(ValueError):
            manager.submit("Maria Silva", "owner", **kwargs)
        assert search.calls == []


def test_name_and_username_share_slots_session_limit_and_fair_order():
    releases = {
        value: threading.Event()
        for value in ("first", "Maria Silva", "Ana Lima", "other")
    }
    started = {value: threading.Event() for value in releases}
    order = []

    def run(value):
        order.append(value)
        started[value].set()
        assert releases[value].wait(3)

    def runner(username, settings, emit):
        run(username)
        return complete_runner(username, settings, emit)

    class BlockingSearch(DocumentSearch):
        def search(self, name, file_type, emit):
            run(name)
            return super().search(name, file_type, emit)

    with JobManager(
        Settings(workers=2), runner=runner, document_search=BlockingSearch()
    ) as manager:
        try:
            first = manager.submit("first", "a")
            second = manager.submit("Maria Silva", "b", mode="name")
            assert started["first"].wait(1) and started["Maria Silva"].wait(1)
            assert manager.submit("Maria Silva", "b", mode="name") == second
            queued = manager.submit("Ana Lima", "a", mode="name")
            with pytest.raises(SessionCapacityError):
                manager.submit("third", "a")
            other = manager.submit("other", "c")
            queued_job = manager.snapshot(queued, "a")
            other_job = manager.snapshot(other, "c")
            assert queued_job is not None and other_job is not None
            assert queued_job["state"] == "queued"
            assert other_job["queue_position"] == 1
            assert len(order) == 2
            releases["first"].set()
            assert started["other"].wait(1)
            assert not started["Ana Lima"].is_set()
            releases["Maria Silva"].set()
            assert started["Ana Lima"].wait(1)
        finally:
            for event in releases.values():
                event.set()
        assert wait_for_job(manager, first, "a")["state"] == "done"
        assert wait_for_job(manager, second, "b")["state"] == "done"


def test_name_failures_do_not_expose_provider_exception_or_report_text():
    class FailingSearch(DocumentSearch):
        def search(self, name, file_type, emit):
            raise RuntimeError("private provider secret")

    with JobManager(Settings(), document_search=FailingSearch()) as manager:
        token = manager.submit("Maria Silva", "owner", mode="name")
        job = wait_for_job(manager, token, "owner")
        assert job["state"] == "error" and job["error"]
        assert "private" not in str(job)
        assert job["checked"] == 0 and job["total"] == 1


def test_name_and_username_share_global_job_capacity():
    release = threading.Event()

    class BlockingSearch(DocumentSearch):
        def search(self, name, file_type, emit):
            assert release.wait(3)
            return super().search(name, file_type, emit)

    with JobManager(
        Settings(workers=1, max_jobs=2),
        runner=complete_runner,
        document_search=BlockingSearch(),
    ) as manager:
        try:
            manager.submit("Maria Silva", "owner-a", mode="name")
            manager.submit("synthetic", "owner-b")
            with pytest.raises(CapacityError):
                manager.submit("Ana Lima", "owner-c", mode="name")
        finally:
            release.set()


@pytest.mark.parametrize(
    "error_code", ["quota", "failed", "unavailable", "private-secret"]
)
def test_provider_error_codes_are_mapped_to_fixed_public_messages(error_code):
    class ReportFailure(DocumentSearch):
        def search(self, name, file_type, emit):
            return {
                "state": "error",
                "checked": 1,
                "total": 10000,
                "error": "private provider secret",
                "error_code": error_code,
                "references": [],
            }

    with JobManager(Settings(), document_search=ReportFailure()) as manager:
        token = manager.submit("Maria Silva", "owner", mode="name")
        job = wait_for_job(manager, token, "owner")
        assert job["state"] == "error" and job["error"]
        assert job["checked"] == 1 and job["total"] == 1
        assert "private" not in str(job)
