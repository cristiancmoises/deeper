"""Smoke test an installed wheel, including a pruned Deeper-only environment."""

import argparse
import asyncio
import json
import sys
import threading
import urllib.request
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import metadata
from pathlib import Path

from maigret.sites import MaigretSite
from waitress.server import TcpWSGIServer, create_server

import deeper
from deeper.app import create_app
from deeper.config import Settings
from deeper.engine import load_sites, search_username
from deeper.jobs import JobManager


class FormControls(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"input", "select", "option"}:
            self.elements.append((tag, dict(attrs)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert Path(deeper.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()), (
        deeper.__file__
    )
    assert metadata.version("deeper-maigret") == "0.5.0"
    sites = load_sites(Settings(top_sites=10))
    assert len(sites) == 10

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(
                200
                if self.path.startswith("/found/")
                else 404
                if self.path.startswith("/absent/")
                else 503
            )
            self.end_headers()
            self.wfile.write(b"<html>synthetic profile</html>")

        def log_message(self, format: str, *args: object) -> None:
            pass

    fixture = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    fixture_thread = threading.Thread(target=fixture.serve_forever, daemon=True)
    fixture_thread.start()
    base = f"http://127.0.0.1:{fixture.server_port}"
    local = {
        name: MaigretSite(
            name,
            {
                "urlMain": base,
                "url": base + route + "/{username}",
                "checkType": "status_code",
                "requestHeadOnly": False,
                "disabled": False,
            },
        )
        for name, route in [
            ("Found", "/found"),
            ("Absent", "/absent"),
            ("Unknown", "/error"),
        ]
    }
    try:
        report = asyncio.run(
            search_username("synthetic", Settings(), lambda event: None, sites=local)
        )
        assert report["state"] == "done" and report["checked"] == 3
        assert report["unknown"] == 1 and len(report["profiles"]) == 1
    finally:
        fixture.shutdown()
        fixture.server_close()
        fixture_thread.join()
    manager = JobManager(Settings())
    app = create_app(Settings(secret_key="test"), manager)
    server = create_server(app, host="127.0.0.1", port=0)
    assert isinstance(server, TcpWSGIServer)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.getsockname()[1]}"
        with urllib.request.urlopen(base + "/health") as response:
            health = json.load(response)
            assert health["status"] == "ok" and health["deeper_version"] == "0.5.0"
        with urllib.request.urlopen(base) as response:
            html = response.read().decode()
            assert "<script" not in html and "<h1>" in html
            assert "script-src 'self'" in response.headers["Content-Security-Policy"]
            assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
        with urllib.request.urlopen(base + "/?mode=name") as response:
            assert response.status == 200
            controls = FormControls()
            controls.feed(response.read().decode())
            assert any(
                tag == "select" and attrs.get("name") == "engine"
                for tag, attrs in controls.elements
            )
            assert any(
                tag == "option"
                and attrs.get("value") == "brave"
                and "selected" in attrs
                for tag, attrs in controls.elements
            )
            assert any(
                tag == "option" and attrs.get("value") == "google"
                for tag, attrs in controls.elements
            )
            assert any(
                tag == "select" and attrs.get("name") == "file_type"
                for tag, attrs in controls.elements
            )
            assert any(
                tag == "input"
                and attrs.get("name") == "mode"
                and attrs.get("value") == "name"
                for tag, attrs in controls.elements
            )
            assert any(
                tag == "input"
                and attrs.get("name") == "consent"
                and attrs.get("type") == "checkbox"
                and attrs.get("value") == "1"
                and "required" in attrs
                for tag, attrs in controls.elements
            )
        assets = [
            "deeper.css",
            "search-progress.js",
            "document-progress.js",
            "icons/github.svg",
            "icons/codeberg.svg",
            "icons/forgejo.svg",
        ]
        for asset in assets:
            with urllib.request.urlopen(base + "/static/" + asset) as response:
                assert response.status == 200, asset
                assert response.read(), asset
    finally:
        server.task_dispatcher.shutdown(timeout=3)
        server.close()
        thread.join(timeout=3)
        manager.close()
    result = {
        "deeper_version": metadata.version("deeper-maigret"),
        "maigret_version": metadata.version("maigret"),
        "python": sys.version.split()[0],
        "module_path": deeper.__file__,
        "database_sites": len(sites),
        "real_maigret_local_report": {
            key: report[key] for key in ("state", "checked", "unknown")
        },
        "found_profiles": len(report["profiles"]),
        "health_html_css": "pass",
        "home_page_no_javascript": True,
        "name_mode_filter_consent": "pass",
        "name_engine_brave_default_google_optional": "pass",
        "installed_assets": assets,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
