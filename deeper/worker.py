"""Isolated worker: JSON on stdin, newline-delimited JSON on stdout."""
import asyncio
from contextlib import redirect_stdout
from copy import deepcopy
import json
import sys

from .config import Settings
from .engine import load_sites, search_username, validate_username


def clone_sites(templates):
    sites = deepcopy(templates)
    for site in sites.values():
        # Upstream keeps mutable defaults (notably headers) on MaigretSite.
        # Materialize them per instance: deepcopy alone does not copy class attrs.
        for name, value in vars(type(site)).items():
            if (name.islower() and not name.startswith('_') and name not in vars(site)
                    and isinstance(value, (dict, list, set))):
                setattr(site, name, deepcopy(value))
    return sites


def main():
    channel = sys.stdout

    def emit(report):
        channel.write(json.dumps(report, ensure_ascii=False) + '\n')
        channel.flush()

    def progress(report):
        # search() may finish while uninterruptible DNS/executor work remains.
        # Keep the final data as progress until asyncio.run has fully cleaned up.
        if report.get('state') in ('done', 'partial', 'error'):
            report = dict(report, state='running')
        emit(report)

    templates = None
    selected_top = None
    while line := sys.stdin.readline(8193):
        try:
            if len(line) > 8192:
                raise ValueError('Worker request too long')
            request = json.loads(line)
            settings = Settings(**request['settings'])
            username = validate_username(request['username'])
            # Upstream diagnostics never enter the JSON-lines protocol.
            with redirect_stdout(sys.stderr):
                if templates is None or selected_top != settings.top_sites:
                    templates = load_sites(settings)
                    selected_top = settings.top_sites
                # Maigret mutates stats/activation: never reuse those across jobs.
                sites = clone_sites(templates)
                report = asyncio.run(search_username(username, settings, progress, sites=sites))
            # Only this acknowledgement releases the worker and its watchdog.
            emit(report)
        except Exception:
            emit({'state': 'error', 'error': 'Não foi possível concluir a busca. Tente novamente.'})
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
