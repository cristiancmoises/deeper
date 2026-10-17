# Deeper 0.5.0

**English** | [Português (Brasil)](README.pt-BR.md)

Try the live application: **[deeper.securityops.co](https://deeper.securityops.co)**

Check the deployed application's `/health` version and
[`validation record`](docs/VALIDATION.md) for the currently deployed release.

Deeper is an independent web interface with two modes. **Username** uses
**Maigret 0.6.6** to check public profile pages. **Full name and documents**
uses **SecuritySearch**, with free **Brave** by default or optional free
**Google CSE** selected per search, to find up to **10 search-index references**, with one
selector for any result type, PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, ODT, ODS, ODP,
RTF, TXT, or CSV.
Matching usernames do not prove that profiles belong to the same person; review
each result in context. A name reference does not prove identity or document
contents, even when the exact name appears in the query. Deeper does not guess
usernames from names, download or preview documents, fetch result URLs, perform
recursive searches, use authenticated platform cookies, or bypass access controls.

The interface uses a black-and-cyan design with an animated CSS title. The
search landing page is server-rendered without JavaScript. A pending results
page loads a mode-specific same-origin script that appends results and updates progress
without reloading the whole page. If JavaScript is unavailable, the HTML still
works and a manual refresh link remains available. Results are private to a
browser session and kept in memory; the application has no database, persistent
search history, or on-disk reports.

## Screenshots

These **0.5.0** screenshots show the real local application in sandboxed Chromium.

Full-name form with “Cristian Cezar Moisés”, PDF and Brave selected, and consent
unchecked. This is a form demonstration, not document findings about that person:

![Deeper full-name form with PDF and Brave selected and consent unchecked](docs/images/deeper-name-search.png)

Real Brave results for the quoted public, non-personal example “GNU Guix” with
the PDF filter: ten search-index references. File types are inferred from URLs;
documents were not downloaded and their content or MIME type was not verified:

![Ten real Brave search-index references for the public GNU Guix PDF example](docs/images/deeper-document-results.png)

## Quick deployment with Docker Compose

Requirements: Git, Docker Engine, and the Docker Compose plugin. Both search
modes work without a provider account or API key; no paid API is used. The default
configuration binds to `127.0.0.1:8080`, so the service is not exposed directly
to the public internet.

```sh
git clone https://github.com/cristiancmoises/deeper.git
cd deeper
cp .env.example .env
# Optional: edit .env to adjust resource limits.
docker compose up -d --build
curl -fsS http://127.0.0.1:8080/health
```

Open <http://127.0.0.1:8080>. Follow startup output with
`docker compose logs -f deeper`, and stop the service with `docker compose down`.
Keep `.env` private; Git ignores it. Public source mirrors are on
[GitHub](https://github.com/cristiancmoises/deeper),
[Codeberg](https://codeberg.org/berkeley/deeper),
[Security Ops](https://git.securityops.co/cristiancmoises/deeper), and
[Security Ops Brasil](https://git.securityops.com.br/cristiancmoises/deeper).
The links identify the project's public source repositories.

The default public-service profile runs **two searches at once**, accepts up to
**64 outstanding searches** across sessions, and allows **two outstanding
searches per browser session**. Outstanding means queued or running. The
container is limited to 512 MiB RAM and 1 GiB combined RAM and swap; size the host
for the reverse proxy, operating system, and other services as well.

For a lower-memory, single-search profile, add these settings to the local
`.env` beside `compose.yaml`:

```dotenv
DEEPER_WORKERS=1
DEEPER_MAX_JOBS=16
DEEPER_MAX_JOBS_PER_SESSION=2
```

Then run `docker compose up -d --build`. For a public self-hosted deployment,
put a reverse proxy with HTTPS in front of Deeper and set
`DEEPER_SECURE_COOKIE=1` in `.env`. Keep the app bound to loopback when the proxy
runs on the same host. If your proxy needs a non-loopback binding, restrict it
with a firewall and do not expose the plain HTTP port directly to the internet.

## Full-name search, privacy, and provider limits

Select full-name mode and enter at least two name words, from 2 to 120 characters.
Deeper normalizes Unicode to NFC and whitespace. Letters, combining marks,
spaces, apostrophes, hyphens, and periods are supported; quotes and query
operators are rejected. The entire name is quoted, and the allowlisted file type
is the only appended search operator. Explicit consent is required before
sharing the name and file-type query with SecuritySearch and the selected engine.
Their service policies
apply to this external processing.

Each uncached name job makes **one GET** to `https://securityops.co/api/v1/web`,
with the quoted query in `s`, `scraper=brave` (default) or `scraper=google`
(Google CSE), and `extendedsearch=no`. No account, key, paid API, automatic
retry, or engine fallback is used. Google CSE may rate-limit requests; Deeper
reports unavailable or quota errors honestly. Results show the actual selected
engine; Brave results are never labeled Google. Responses are bounded to 1 MiB.
The default HTTP timeout is 12 seconds,
configurable from 1 to 30 seconds: a normal `urllib` HTTP timeout, not a
process-enforced wall-clock deadline. The optional external Google query link
opens additional results outside Deeper and its result limit; it does not identify
the engine that supplied the displayed references.

References contain a URL-based identifier, title, URL, snippet, source hostname,
and inferred file type. They are deduplicated by URL, not title or host. Known
document extensions inconsistent with the selected filter are removed; unknown
types remain labeled unverified. Neither extension nor search filter proves a
response's MIME type or document contents. Indexes can omit, delay, or misattribute
results. An empty search does not prove absence.

The default resource guard allows **100 upstream calls per UTC day per
application process**, with at least **one second between calls**. Restarting
resets this counter. This protects shared resources, not billing: the integration
uses no paid API. The service and either engine can become unavailable.
Exhausted limits, network failures, and invalid provider responses
produce generic public errors, never fabricated results.

## Shared scheduling in 0.5.0

Both modes share the same bounded executor and worker slots. A name HTTP request
does not create a separate worker pool. Cache identity includes session, mode,
normalized value, file type, and selected engine. Name progress counts a single provider request
(0/1 or 1/1), rather than Maigret sites checked.

- A fair queue shares search workers across browser sessions. Each available
  worker takes a search from the pending session served least recently, keeping
  submission order within each session.
- Each session can have two queued or running searches by default. Repeating an
  active search or reusing a fresh completed result does not consume another
  slot. A third distinct outstanding search receives HTTP `429`; a full global
  queue receives HTTP `503`. Both responses include `Retry-After: 5`.
- Pending results show their current queue position, which updates as searches
  finish and other sessions join. A queue position is an ordering hint, not a
  promised start time.
- Incremental profiles, reusable isolated workers, 60-second completed-result
  reuse, and periodic in-memory cleanup remain available. Search coverage,
  connection limits, and timeouts retain their existing defaults.

The scheduling, session boundaries, and update format are described in
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

Measurements and methodology are documented in
[`docs/PERFORMANCE.md`](docs/PERFORMANCE.md). Docker image size and performance
on external platforms must be measured in your own environment. Builds also use
temporary storage and Docker cache; a smaller runtime does not eliminate that
cost. Inspect local usage with `docker system df` and
`docker image inspect deeper:0.5.0 --format '{{.Size}}'`. Deeper does not run
global Docker or VPS cleanup commands.

## Python installation

Deeper targets Python **3.11 and 3.12**. Install the pinned, hashed dependencies
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

`/health` reports package availability; it does not check SecuritySearch or engine
connectivity or search coverage. A `.env` file is read by Compose, not automatically
by Python. Direct Python startup needs no provider key; export optional resource
settings explicitly when changing their defaults.
The commands above install the package from the
current checkout after installing its locked runtime dependencies.

## Searches, limits, and freshness

Username-mode defaults enable up to **500 sites**, **20 connections** per search, **two
simultaneous searches**, a **10-second per-site timeout**, and a **180-second
search deadline**. A watchdog terminates blocked processes after the deadline
plus 15 seconds for startup. Reusing a worker reduces startup overhead; it does
not make external sites respond faster. A cold search still pays the database
loading cost.

While a search is pending, new profiles are appended and progress updates about
once per second without a full-page reload. If JavaScript is disabled, use the
manual **Atualizar** link to get the latest server-rendered HTML; it does not
start another search. Select the title to return to the start page. If you
repeat a completed username in the same session within 60 seconds, the page
shows the result age; after that, it starts a new search. Set
`DEEPER_CACHE_TTL=0` to disable completed-result reuse. Results preserve the
distinction between CLAIMED, absent, and inconclusive.

At most two searches run at once by default; up to 64 queued or running jobs can
be accepted globally. A browser session may hold two of those outstanding slots.
When a worker becomes available, the session served least recently goes next,
with searches kept in submission order within each session. The current queue
position may change as other sessions join. These limits bound work; they do not
provide unlimited concurrent searches or guarantee public-site response times.

Jobs are private to the anonymous browser session and expire 15 minutes after
completion, with periodic cleanup within five seconds. Older completed results
may be evicted to free capacity. Warm workers retain memory until idle shutdown
or recycling. Restarting clears jobs and cache; without a persistent key, it also
invalidates sessions. Session quotas share capacity between browsers; they are
not identity verification or robust protection against bots opening new sessions.

Because jobs are held in memory, run a **single HTTP instance**;
`DEEPER_WORKERS` controls search concurrency. Sessions require cookies. There is
no recursive search, authenticated platform cookie support, or bypass
mechanism. Checks that require unconfigured DNS/Tor/I2P or an incompatible
username format may be skipped by Maigret and counted as processed checks.

## Configuration

| Variable | Default | Effect |
| --- | --- | --- |
| `DEEPER_NAME_DAILY_LIMIT` | `100` | Positive maximum upstream calls per UTC day per process; resets on restart. |
| `DEEPER_NAME_TIMEOUT` | `12` | Finite HTTP timeout in seconds, from `1` to `30`. |
| `DEEPER_TOP_SITES` | `500` | Username site limit; `0` checks every enabled site. |
| `DEEPER_SITE_TIMEOUT` | `10` | Seconds per site. |
| `DEEPER_SEARCH_TIMEOUT` | `180` | Search deadline in seconds. |
| `DEEPER_CONNECTIONS` | `20` | Connections per search. |
| `DEEPER_WORKERS` | `2` | Shared concurrent searches across both modes. |
| `DEEPER_MAX_JOBS` | `64` | In-memory jobs, including queue and cache. |
| `DEEPER_MAX_JOBS_PER_SESSION` | `2` | Maximum queued or running searches per browser session. |
| `DEEPER_RETENTION` | `900` | Seconds to retain a completed job. |
| `DEEPER_CACHE_TTL` | `60` | Reuse completed results in the same session; `0` disables it. |
| `DEEPER_WORKER_MAX_JOBS` | `25` | Recycle a process after this many searches. |
| `DEEPER_WORKER_IDLE_TIMEOUT` | `120` | Shut down an idle process after this many seconds. |
| `DEEPER_SECRET_KEY` | random at startup | Optional persistent session key for direct Python deployment. |
| `DEEPER_SECURE_COOKIE` | `0` | Set to `1` when serving exclusively over HTTPS. |

Compose accepts settings from the environment or a local `.env` file. Changing
site limits, extraction behavior, timeouts, or connection counts can affect
coverage and reliability. The fair queue changes admission and scheduling, while
preserving search coverage, extraction, timeouts, and connection defaults.

## Validation and license

[`docs/VALIDATION.md`](docs/VALIDATION.md) records the validation performed
for 0.5.0, distinguishing automated fixtures, actual provider observations, and
release/deployment qualification. The test suite uses real Maigret code against local HTTP
fixtures and controlled provider payloads; those are not live SecuritySearch evidence.
The browser QA scripts use Playwright externally, without adding scripts to the page.

Deeper is an independent interface and is not the official Maigret project.
The backend is **Maigret 0.6.6**, an MIT-licensed project by **Soxoj**. Thank
you to Soxoj for making the project available under the MIT license. See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), [`LICENSE`](LICENSE), and
[`LICENSE-MAIGRET`](LICENSE-MAIGRET) for attribution and license terms.
Thank you to [SecuritySearch](https://securityops.co) for the external search
service. Deeper calls its public endpoint; SecuritySearch code is not embedded
or covered by Deeper's MIT license.
Deeper itself is MIT-licensed. Source-link icons retain their own terms:
Forgejo CC BY-SA 4.0, Codeberg CC0, and GitHub's logo usage terms, documented
in the third-party notices.
