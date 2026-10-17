"""Bounded public search-index references for literal full-name queries."""

import json
import math
import os
import threading
import time
import unicodedata
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

FILE_TYPES = {
    "any": "Todos (web e documentos)",
    "pdf": "PDF",
    "doc": "Word (.doc)",
    "docx": "Word (.docx)",
    "xls": "Excel (.xls)",
    "xlsx": "Excel (.xlsx)",
    "ppt": "PowerPoint (.ppt)",
    "pptx": "PowerPoint (.pptx)",
    "odt": "OpenDocument (.odt)",
    "ods": "OpenDocument (.ods)",
    "odp": "OpenDocument (.odp)",
    "rtf": "RTF",
    "txt": "Texto (.txt)",
    "csv": "CSV",
}
_ENDPOINT = "https://google.serper.dev/search"
_MAX_BYTES = 1024 * 1024
_ERRORS = {
    "unavailable": "A busca por nome está indisponível: o provedor não está configurado.",
    "quota": "O limite de buscas por nome ou a cota do provedor foi atingido. Tente novamente mais tarde.",
    "failed": "Não foi possível concluir a consulta ao provedor de busca. Tente novamente mais tarde.",
}


class DocumentSearchError(Exception):
    """A fixed, safe public error; upstream exception strings are never retained."""

    def __init__(self, code):
        self.code = code if isinstance(code, str) and code in _ERRORS else "failed"
        self.public_message = _ERRORS[self.code]
        super().__init__(self.public_message)


def validate_full_name(value: object) -> str:
    message = (
        "Informe nome e sobrenome, com até 120 caracteres, sem operadores ou links."
    )
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError(message)
    # Reject controls before space normalization; tabs/newlines must not disappear.
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise ValueError(message)
    name = " ".join(unicodedata.normalize("NFC", value).split())
    if not 2 <= len(name) <= 120 or any(
        not (unicodedata.category(char)[0] in ("L", "M") or char in " '-’.")
        for char in name
    ):
        raise ValueError(message)
    words = name.split(" ")
    if len(words) < 2 or any(
        not any(unicodedata.category(c).startswith("L") for c in word) for word in words
    ):
        raise ValueError(message)
    return name


def validate_file_type(value: object) -> str:
    if not isinstance(value, str) or value not in FILE_TYPES:
        raise ValueError("Selecione um tipo de arquivo válido.")
    return value


def build_query(name: str, file_type: str = "any") -> str:
    name, file_type = validate_full_name(name), validate_file_type(file_type)
    return f'"{name}"' + (f" filetype:{file_type}" if file_type != "any" else "")


def google_search_url(name: str, file_type: str = "any") -> str:
    return "https://www.google.com/search?" + urlencode(
        {"q": build_query(name, file_type)}
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _RequestBudget:
    """One shared per-process guard. Failed attempts still consume the budget."""

    def __init__(self):
        self.lock = threading.Lock()
        self.day = None
        self.used = 0
        self.last_call = None

    def run(self, daily_limit, operation):
        # Keep reservation and upstream start ordered across the two job workers.
        with self.lock:
            if self.last_call is not None:
                remaining = 1.0 - (time.monotonic() - self.last_call)
                if remaining > 0:
                    time.sleep(remaining)
            # Spacing may cross UTC midnight; charge the day the call starts.
            day = int(time.time() // 86400)
            if day != self.day:
                self.day, self.used = day, 0
            if self.used >= daily_limit:
                raise DocumentSearchError("quota")
            self.used += 1
            self.last_call = time.monotonic()
            return operation()


_budget = _RequestBudget()


def _reference_url(value):
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or "\\" in value
        or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return None
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in ("https", "http")
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
        ):
            return None
        port = parts.port
        host = parts.hostname.lower()
        if len(host) > 253:
            return None
        authority = f"[{host}]" if ":" in host else host
        if port is not None and (parts.scheme, port) not in (
            ("https", 443),
            ("http", 80),
        ):
            authority += f":{port}"
        url = urlunsplit((parts.scheme, authority, parts.path, parts.query, ""))
        return url if len(url) <= 2048 else None
    except ValueError:
        return None


def _references(payload, file_type):
    if (
        not isinstance(payload, dict)
        or "error" in payload
        or not isinstance(payload.get("organic"), list)
    ):
        raise DocumentSearchError("failed")
    references, seen = [], set()
    for item in payload["organic"][:10]:
        if not isinstance(item, dict) or not isinstance(item.get("link"), str):
            raise DocumentSearchError("failed")
        title, snippet = item.get("title", ""), item.get("snippet", "")
        if not isinstance(title, str) or not isinstance(snippet, str):
            raise DocumentSearchError("failed")
        try:
            # JSON permits escaped lone surrogates. Reject them before clipping
            # metadata or deriving the public URL, id and source hostname.
            for value in (title, snippet, item["link"]):
                value.encode("utf-8")
        except UnicodeEncodeError:
            raise DocumentSearchError("failed") from None
        url = _reference_url(item["link"])
        if not url or url in seen:
            continue
        parts = urlsplit(url)
        path = unquote(parts.path).lower()
        extension = (
            path.rsplit("/", 1)[-1].rsplit(".", 1)[-1]
            if "." in path.rsplit("/", 1)[-1]
            else ""
        )
        inferred = (
            extension
            if extension in FILE_TYPES and extension != "any"
            else ("html" if extension in ("html", "htm") else "unknown")
        )
        if file_type != "any" and inferred in FILE_TYPES and inferred != file_type:
            continue
        seen.add(url)
        references.append(
            {
                "id": url,
                "title": title[:300],
                "url": url,
                "snippet": snippet[:1600],
                "source": parts.hostname,
                "file_type": inferred,
            }
        )
    return references


def _reject_constant(value):
    raise ValueError("Non-finite JSON number")


class SerperSearch:
    """Only search-index metadata is retrieved; reference URLs are never fetched."""

    def __init__(
        self, api_key="", *, opener=None, daily_limit=100, timeout: float = 12
    ):
        if (
            not isinstance(daily_limit, int)
            or isinstance(daily_limit, bool)
            or daily_limit < 1
        ):
            raise ValueError("DEEPER_NAME_DAILY_LIMIT must be a positive integer")
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or not math.isfinite(timeout)
            or not 1 <= timeout <= 30
        ):
            raise ValueError("DEEPER_NAME_TIMEOUT must be finite and between 1 and 30")
        self._api_key = api_key.strip() if isinstance(api_key, str) else ""
        if any(ord(char) < 33 or ord(char) > 126 for char in self._api_key):
            self._api_key = ""
        self._opener = opener if opener is not None else build_opener(_NoRedirect())
        self._daily_limit = daily_limit
        self._timeout = timeout

    @classmethod
    def from_env(cls):
        try:
            daily_limit = int(os.environ.get("DEEPER_NAME_DAILY_LIMIT", "100"))
            timeout = float(os.environ.get("DEEPER_NAME_TIMEOUT", "12"))
        except ValueError:
            raise ValueError(
                "Invalid name-search limit or timeout configuration"
            ) from None
        return cls(
            os.environ.get("SERPER_API_KEY", ""),
            daily_limit=daily_limit,
            timeout=timeout,
        )

    @property
    def available(self):
        return bool(self._api_key)

    def _request(self, query):
        deadline = time.monotonic() + self._timeout
        request = Request(
            _ENDPOINT,
            data=json.dumps(
                {
                    "q": query,
                    "num": 10,
                    "gl": "br",
                    "hl": "pt-br",
                }
            ).encode("utf-8"),
            headers={
                "X-API-KEY": self._api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=self._timeout) as response:
                if response.status != 200 or response.geturl() != _ENDPOINT:
                    raise DocumentSearchError("failed")
                body = bytearray()
                while len(body) <= _MAX_BYTES:
                    if time.monotonic() >= deadline:
                        raise DocumentSearchError("failed")
                    # One buffered socket read per iteration permits deadline checks
                    # even when an upstream stream continuously supplies tiny chunks.
                    chunk = response.read1(min(65536, _MAX_BYTES + 1 - len(body)))
                    if time.monotonic() >= deadline:
                        raise DocumentSearchError("failed")
                    if not chunk:
                        break
                    body.extend(chunk)
        except HTTPError as error:
            raise DocumentSearchError(
                "quota" if error.code in (402, 429) else "failed"
            ) from None
        except (URLError, OSError, ValueError, HTTPException):
            raise DocumentSearchError("failed") from None
        if len(body) > _MAX_BYTES:
            raise DocumentSearchError("failed")
        try:
            return json.loads(body.decode("utf-8"), parse_constant=_reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            raise DocumentSearchError("failed") from None

    def search(self, name, file_type="any", emit=None):
        query = build_query(name, file_type)
        initial = {
            "state": "running",
            "checked": 0,
            "total": 1,
            "unknown": 0,
            "references": [],
        }
        if emit:
            emit(initial)
        report = {**initial, "state": "done", "checked": 1}
        try:
            if not self.available:
                raise DocumentSearchError("unavailable")
            payload = _budget.run(self._daily_limit, lambda: self._request(query))
            report["references"] = _references(payload, file_type)
        except DocumentSearchError as error:
            report.update(
                state="error", error_code=error.code, error=error.public_message
            )
        if emit:
            emit(report)
        return report
