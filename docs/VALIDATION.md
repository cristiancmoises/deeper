# Deeper 0.3.0: validation

**English** | [Português (Brasil)](pt-BR/VALIDATION.md)

Date: 10 October 2026. The automated searches below use synthetic local HTTP fixtures only; no public-site usernames were queried. The live IONOS deployment is a separate release gate and is not claimed by this local test report.

## Results

| Check | Result |
| --- | --- |
| Python 3.12.12 full suite | 84 tests passed in 10.92s. |
| Wheel build | `deeper_maigret-0.3.0-py3-none-any.whl`; includes `search-progress.js` and both license files. |
| Installed-wheel smoke | Fresh venv outside the repository; version 0.3.0, Maigret 0.6.6, official database, local HTTP search, health, HTML, CSS, and JavaScript asset passed. |
| Real Maigret with local HTTP | 3 checks completed, 1 inconclusive, 1 synthetic profile found. |
| Incremental browser results | Chromium 153.0.8010.47, desktop 1440×900 and mobile 390×844; first profile appeared in 1.796s / 1.872s while the slow fixture was pending; progress 1/2, at most one update request in flight, no page reloads or console issues. |
| Final reconciliation and visible status | Corrected profiles replaced stale cards, withdrawn profiles disappeared, terminal completion and unavailable-search recovery were visible, and stopped polling cleared the busy state. |
| No-JavaScript fallback | Search remained server-rendered with a manual refresh link; no script requests in the disabled-JavaScript browser run. |
| Safe rendering and recovery | HTML-like fields stayed inert, `javascript:` links were rejected, safe links used `noopener noreferrer`, and polling stopped after three 503 responses. |
| Accessibility and layout | Reduced motion and 200% text at 320px passed without horizontal overflow. |
| Progress-payload benchmark | Two synthetic 500-site runs: 14 progress messages, 14,993 incremental worker-format JSONL bytes vs 42,984 cumulative-reference bytes (65.1% lower); cold / second run 4.150s / 3.008s. |
| Compose configuration | `docker compose config --quiet` passed. A local image build was not run; the release deployment is the separate image-build check. |

The benchmark uses Linux x86_64, Python 3.12.12, Maigret 0.6.6, 20 connections, one worker, and a local HTTP fixture with a 5ms response delay. These timings and payload sizes do not predict public-site latency; Deeper does not control the response time of external sites. [`PERFORMANCE.md`](PERFORMANCE.md) records the method and the smaller 100-site sample where four sparse events carried slightly more bytes incrementally than cumulatively.

## Reproduction

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m build --wheel
LD_LIBRARY_PATH=/path/to/guix/profile/lib .venv/bin/python tests/verify_ui.py --browser /path/to/chromium
.venv/bin/python scripts/benchmark.py --project /path/to/deeper --output /tmp/progress.json --runs 2 --sites 500
```

Run the installed-wheel smoke using a fresh virtual environment with hash-locked runtime dependencies, from a directory outside the repository. `tests/verify_installation.py` checks the installed module path, package and engine versions, health endpoint, official site database, local HTTP search, HTML, CSS, and packaged JavaScript asset.

## Limitations

- Public sites were not queried. Network conditions, blocks, and platform response times may dominate search duration. A cold search still loads Maigret's database.
- The 0.3.0 full suite ran on Python 3.12.12; Python 3.11 was not rerun for this release. The 0.2.0 validation record is historical and does not substitute for a 0.3.0 Python 3.11 run.
- Jobs and cache stay in memory, are private to one session, and expire under the configured retention limit. Run a single HTTP instance.
- Checks incompatible with a username or requiring unconfigured protocols may be skipped by Maigret and counted among processed items.
- Windows was not tested; the SIGTERM check is Unix-specific.
