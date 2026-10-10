"""The official Maigret API, normalized for safe server-rendered HTML."""
import asyncio
from importlib.resources import files
import json
import logging
import re
import sys
import time
from urllib.parse import urlsplit

from .config import Settings


def validate_username(value: str) -> str:
    username = value.strip().removeprefix('@')
    if not re.fullmatch(r'[\w.-]{1,64}', username) or not any(
        char.isalnum() for char in username
    ):
        raise ValueError('Use um nome de usuário de até 64 caracteres, sem espaços ou links.')
    return username


def safe_url(value) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        return None
    if any(ord(char) < 33 or ord(char) == 127 for char in value) or '\\' in value:
        return None
    try:
        parts = urlsplit(value)
        if (parts.scheme not in ('http', 'https') or not parts.hostname
                or parts.username is not None or parts.password is not None):
            return None
        # Accessing port also rejects malformed/out-of-range port numbers.
        _ = parts.port
    except ValueError:
        return None
    return value


_LABELS = {
    'fullname': 'Nome', 'full_name': 'Nome', 'name': 'Nome', 'bio': 'Bio',
    'description': 'Descrição', 'location': 'Localização', 'country': 'País',
    'city': 'Cidade', 'username': 'Usuário', 'id': 'ID', 'website': 'Site',
    'followers_count': 'Seguidores', 'following_count': 'Seguindo',
    'created_at': 'Criado em', 'email': 'E-mail', 'gender': 'Gênero',
}


def _display(value) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)[:2048]
    return str(value)[:2048]


def normalize_result(result, is_similar=False) -> dict | None:
    if not result.is_found() or not (url := safe_url(result.site_url_user)):
        return None
    data = result.ids_data if isinstance(result.ids_data, dict) else {}
    details = [{'label': _LABELS.get(str(key), str(key).replace('_', ' ').capitalize()),
                'value': _display(value)}
               for key, value in list(data.items())[:32]
               if key not in ('links', 'website') and value is not None
               and value != '' and value != [] and value != {}]
    candidates = data.get('links', [])
    if isinstance(candidates, str):
        try:
            candidates = json.loads(candidates)
        except (ValueError, TypeError):
            candidates = [candidates]
    if not isinstance(candidates, list):
        candidates = []
    candidates = candidates + [data.get('website')]
    links = list(dict.fromkeys(link for candidate in candidates
                              if (link := safe_url(candidate))))[:16]
    return {'name': str(result.site_name), 'url': url,
            'tags': [str(tag) for tag in (result.tags or [])][:8],
            'details': details, 'links': links, 'similar': bool(is_similar)}


def load_sites(settings: Settings) -> dict:
    from maigret import MaigretDatabase
    resource = files('maigret').joinpath('resources/data.json')
    db = MaigretDatabase().load_from_json(json.loads(resource.read_text(encoding='utf-8')))
    ranked = db.ranked_sites_dict(top=settings.top_sites or sys.maxsize, disabled=False)
    # Maigret adds mirrors to the ranked set. Keep the configured ceiling exact.
    return dict(list(ranked.items())[:settings.top_sites]) if settings.top_sites else ranked


class _Progress:
    """Maigret notifier protocol, without console output or network side effects."""
    def __init__(self, total, emit):
        self.total = total
        self.emit = emit
        self.results = {}
        self.profiles = {}
        self.pending_profiles = {}
        self.sent_profiles = set()
        self.last_emit = 0.0

    def start(self, *args, **kwargs):
        pass

    def finish(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    info = warning
    success = warning
    enrich = warning

    def update(self, result, is_similar=False):
        profile = self.record(result, is_similar)
        site_name = result.site_name
        if profile is None:
            self.pending_profiles.pop(site_name, None)
        elif site_name not in self.sent_profiles:
            self.pending_profiles[site_name] = profile
        now = time.monotonic()
        if now - self.last_emit >= 0.5:
            self.last_emit = now
            self.emit(self.progress_update())

    def record(self, result, is_similar=False):
        self.results[result.site_name] = result.status
        if profile := normalize_result(result, is_similar):
            self.profiles[result.site_name] = profile
        else:
            self.profiles.pop(result.site_name, None)
        return profile

    def progress_update(self):
        from maigret.result import MaigretCheckStatus
        profiles_delta = sorted(self.pending_profiles.values(),
                                key=lambda profile: profile['name'].casefold())
        self.sent_profiles.update(self.pending_profiles)
        self.pending_profiles.clear()
        return {'state': 'running', 'checked': len(self.results), 'total': self.total,
                'unknown': sum(status == MaigretCheckStatus.UNKNOWN
                               for status in self.results.values()),
                'profiles_delta': profiles_delta}

    def snapshot(self, state='running'):
        from maigret.result import MaigretCheckStatus
        return {'state': state, 'checked': len(self.results), 'total': self.total,
                'unknown': sum(status == MaigretCheckStatus.UNKNOWN
                               for status in self.results.values()),
                'profiles': sorted(self.profiles.values(), key=lambda profile: profile['name'].casefold())}


async def search_username(username: str, settings: Settings, emit, *, sites=None) -> dict:
    from maigret import search
    username = validate_username(username)
    sites = load_sites(settings) if sites is None else sites
    if not sites:
        raise RuntimeError('No enabled sites in the Maigret database')
    progress = _Progress(len(sites), emit)
    emit(progress.progress_update())
    logger = logging.getLogger('deeper.maigret')
    logger.setLevel(logging.CRITICAL)
    collected = {}
    state = 'done'
    try:
        await asyncio.wait_for(search(
            username=username, site_dict=sites, logger=logger, query_notify=progress,
            timeout=settings.site_timeout, max_connections=settings.max_connections,
            is_parsing_enabled=True, no_progressbar=True, retries=0,
            output_container=collected, dns_resolver='threaded',
        ), timeout=settings.search_timeout)
    except TimeoutError:
        state = 'partial'
    # Final site results also cover checks that did not call notifier.update().
    for record in collected.values():
        result = record.get('status')
        if result is not None:
            progress.record(result, bool(getattr(record.get('site'), 'similar_search', False)))
    report = progress.snapshot(state)
    emit(report)
    return report
