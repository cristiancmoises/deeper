# Deeper 0.2.0

**English** | [Português (Brasil)](README.pt-BR.md)

Try the live application: **[deeper.securityops.co](https://deeper.securityops.co)**

Deeper is an independent, minimal web interface for **Maigret 0.6.6**. Enter a
username to check publicly accessible profile pages across supported sites.
Matching usernames do not prove that profiles belong to the same person; review
each result in context. Deeper does not perform recursive searches, use
authenticated platform cookies, or bypass access controls.

The interface uses a black-and-cyan design with an animated CSS title. The
search page sends no JavaScript to the browser. Results are private to a browser
session and kept in memory; the application has no database, persistent search
history, or on-disk reports.

## Screenshots

The initial search screen:

![Deeper initial search screen](docs/images/deeper-search-start.png)

A search in progress with results:

![Deeper search progress and results](docs/images/deeper-search-results.png)

The displayed usernames and matches are examples, not identity verification.

## Quick deployment with Docker Compose

Requirements: Git, Docker Engine, and the Docker Compose plugin. The default
configuration binds to `127.0.0.1:8080`, so the service is not exposed directly
to the public internet.

```sh
git clone https://github.com/cristiancmoises/deeper.git
cd deeper
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/health
```

Open <http://127.0.0.1:8080>. Follow startup output with
`docker compose logs -f deeper`, and stop the service with `docker compose down`.
The public source repository is on
[GitHub](https://github.com/cristiancmoises/deeper).

For a small VPS, create a local `.env` file beside `compose.yaml` with:

```dotenv
DEEPER_WORKERS=1
DEEPER_MAX_JOBS=16
```

Then run `docker compose up -d --build`. For a public self-hosted deployment,
put a reverse proxy with HTTPS in front of Deeper and set
`DEEPER_SECURE_COOKIE=1` in `.env`. Keep the app bound to loopback when the proxy
runs on the same host. If your proxy needs a non-loopback binding, restrict it
with a firewall and do not expose the plain HTTP port directly to the internet.

## What is included in 0.2.0

- Isolated search workers are reused: the Maigret database is loaded once per
  process, with an independent site copy for each search. Workers start on
  demand, are recycled after 25 searches, and exit after 120 seconds idle.
- Completed searches for the same session and username are reused for up to
  60 seconds. The page shows the result age; errors and partial results are not
  reused.
- Results and cache stay in memory. Expired jobs are removed periodically,
  including when no new requests arrive.
- The Docker build installs without a download cache or bytecode and copies only
  the installed runtime into the final image. Unused dependency tests,
  `pycountry` translations, and installation tools are removed; engine data and
  license files are preserved.
- Logs rotate across three 2 MB files. The container filesystem is read-only
  and `/tmp` is a 32 MB tmpfs. Searches are not persisted in Docker volumes.

Measurements and methodology are documented in
[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md). Docker image size and performance
on external platforms must be measured in your own environment. Builds also use
temporary storage and Docker cache; a smaller runtime does not eliminate that
cost. Inspect local usage with `docker system df` and
`docker image inspect deeper:0.2.0 --format '{{.Size}}'`. Deeper does not run
global Docker or VPS cleanup commands.

## Python installation

Python **3.11 and 3.12** were validated. Install the pinned, hashed dependencies
and run the application:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir --no-compile --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-cache-dir --no-compile --no-deps .
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m deeper
```

The environment does not need to be activated in fish. On Windows, use
`.venv\Scripts\python.exe`. `scripts/slim_runtime.py` is only for Deeper's
dedicated Docker runtime; it removes the pip installer and should not be run in
a shared environment.

To select a host and port:

```sh
env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m deeper --host 0.0.0.0 --port 8080
```

`/health` reports whether the Maigret package is available; it does not check
connectivity to every platform. To install the included wheel after installing
the lock file, run
`pip install --no-deps wheels/deeper_maigret-0.2.0-py3-none-any.whl`.

## Searches, limits, and freshness

Defaults enable up to **500 sites**, **20 connections** per search, **two
simultaneous searches**, a **10-second per-site timeout**, and a **180-second
search deadline**. A watchdog terminates blocked processes after the deadline
plus 15 seconds for startup. Reusing a worker reduces startup overhead; it does
not make external sites respond faster. A cold search still pays the database
loading cost.

While a search is pending, the HTML page refreshes every three seconds. Refreshing
does not start another search. Select the title to return to the start page. If
you repeat a completed username in the same session within 60 seconds, the page
shows the result age; after that, it starts a new search. Set
`DEEPER_CACHE_TTL=0` to disable completed-result reuse. Results preserve the
distinction between CLAIMED, absent, and inconclusive.

Jobs are private to the session and expire 15 minutes after completion, with
periodic cleanup within five seconds. The queue and memory use are bounded by
the number of jobs; older completed results may be evicted to free capacity.
Warm workers retain memory until idle shutdown or recycling. Restarting clears
jobs and cache; without a persistent key, it also invalidates sessions.

Because jobs are held in memory, run a **single HTTP instance**;
`DEEPER_WORKERS` controls search concurrency. Sessions require cookies. There is
no recursive search, AI API, authenticated platform cookie support, or bypass
mechanism. Checks that require unconfigured DNS/Tor/I2P or an incompatible
username format may be skipped by Maigret and counted as processed checks.

## Configuration

| Variable | Default | Effect |
| --- | --- | --- |
| `DEEPER_TOP_SITES` | `500` | Maximum sites; `0` checks every enabled site. |
| `DEEPER_SITE_TIMEOUT` | `10` | Seconds per site. |
| `DEEPER_SEARCH_TIMEOUT` | `180` | Search deadline in seconds. |
| `DEEPER_CONNECTIONS` | `20` | Connections per search. |
| `DEEPER_WORKERS` | `2` | Concurrent searches. |
| `DEEPER_MAX_JOBS` | `64` | In-memory jobs, including queue and cache. |
| `DEEPER_RETENTION` | `900` | Seconds to retain a completed job. |
| `DEEPER_CACHE_TTL` | `60` | Reuse completed results in the same session; `0` disables it. |
| `DEEPER_WORKER_MAX_JOBS` | `25` | Recycle a process after this many searches. |
| `DEEPER_WORKER_IDLE_TIMEOUT` | `120` | Shut down an idle process after this many seconds. |
| `DEEPER_SECRET_KEY` | random at startup | Optional session key to persist across restarts. |
| `DEEPER_SECURE_COOKIE` | `0` | Set to `1` when serving exclusively over HTTPS. |

Compose accepts settings from the environment or a local `.env` file. Changing
site limits, extraction behavior, timeouts, or connection counts can affect
coverage and reliability; the original search defaults were preserved in this
optimization.

## Validation and license

[`docs/VALIDATION.md`](docs/VALIDATION.md) describes the validation performed
for this release. The test suite uses real Maigret code against local HTTP
fixtures with synthetic profiles. `tests/verify_ui.py` uses Playwright as an
external QA tool; it does not add scripts to the page.

Deeper is an independent interface and is not the official Maigret project.
The backend is **Maigret 0.6.6**, an MIT-licensed project by **Soxoj**. Thank
you to Soxoj for making the project available under the MIT license. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), [`LICENSE`](LICENSE), and
[`LICENSE-MAIGRET`](LICENSE-MAIGRET) for attribution and license terms.
