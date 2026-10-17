# Deeper 0.5.0 — search architecture

**English** | [Português (Brasil)](pt-BR/ARCHITECTURE.md)

Deeper runs one HTTP application with an in-memory job manager and a bounded
executor shared by username and full-name jobs. Username searches use isolated
Maigret processes; full-name searches make a bounded SecuritySearch HTTP request inside
the same executor slot. The HTTP application owns session
privacy, admission, scheduling, progress, and temporary results. A worker loads
the Maigret database once and uses an independent site copy for each username search.

## Modes and provider boundary

`GET /?mode=name` selects the server-rendered full-name form. `POST /search`
retains the legacy `username` field and adds `mode`, `file_type`, and `engine`; omitted
fields preserve username behavior. Name mode requires `consent=1` before sending
the name and file-type query to SecuritySearch and the selected engine. `engine`
is allowlisted to `brave` (free Brave, default) or `google` (free Google CSE),
validated before network I/O, and may be preselected with `?mode=name&engine=google`.
The native selector also works without JavaScript. Names are normalized to Unicode
NFC and collapsed spaces, must have at least two words and 2–120 characters,
and admit only letters, combining marks, spaces, apostrophes, hyphens, and
periods. Raw oversized inputs, quotes, controls, and query operators are rejected.
Names never generate guessed usernames.

The file-type allowlist is `any`, `pdf`, `doc`, `docx`, `xls`, `xlsx`, `ppt`,
`pptx`, `odt`, `ods`, `odp`, `rtf`, `txt`, and `csv`. The query quotes the entire
name and appends only the selected allowlisted `filetype:` operator. Each
uncached name job makes exactly one GET to the fixed
`https://securityops.co/api/v1/web` endpoint, with `s` holding the quoted query,
`scraper` holding the selected engine, and `extendedsearch=no`.
There is no provider account, API key, paid API, automatic retry, redirect
following, engine fallback, document download, preview, or result-URL fetch.
Brave uses the free search mechanism; `google` selects Google CSE, never the paid
`google_api` mechanism. Google CSE may rate-limit requests. Results visibly name
the actual engine. The optional external Google query link opens additional
results outside the application; it does not label Brave results as Google.

`SecuritySearch.from_env()` loads resource limits without reading a provider key.
`DEEPER_NAME_DAILY_LIMIT` defaults to 100 calls per UTC day per application
process, with at least one second between upstream calls. Restart resets the
counter; this protects shared resources rather than billing. No paid API is used.
`DEEPER_NAME_TIMEOUT` defaults
to 12 seconds and accepts finite values from 1 to 30. It is a normal `urllib`
HTTP timeout, not a process-enforced wall-clock deadline. Responses are bounded
to 1 MiB. HTTP 200 alone is insufficient: JSON must be an object with `status=ok`
and a `web` list. Only a bounded initial set of records is examined; `title`,
`description`, and `url` pass through the metadata and URL validation below.
Unavailable service/engines (including HTTP 401/403/503), exhausted quotas
(including HTTP 429), network errors, and malformed payloads produce fixed public
unavailable/quota/failure messages without upstream text or invented results.
Bot protection must result in honest unavailability, never cookie reuse,
CAPTCHA solving, or disabled protection.

## Reference contract and limits of evidence

Name jobs return at most ten references, each with `id` (the canonical URL
without its fragment), `title` (up to 300 characters), `url` (up to 2048),
`snippet` (up to 1600), `source` (hostname, up to 253), and `file_type` inferred from the URL
or labeled unknown/HTML. Unsafe HTTP(S) reference URLs are rejected. Duplicate
URLs collapse; equal titles or hosts do not. Known document extensions that
disagree with the filter are removed, while unknown types remain unverified.

References are search-index metadata. Neither a quoted exact-name query, an
extension, nor a search filter proves identity, MIME type, current availability,
or document contents. An empty search does not establish absence. Results are
links for the user to evaluate, with no content verification or document fetch.

## Admission and fair scheduling

The default limits are two running searches, 64 outstanding jobs globally, and
two outstanding jobs per anonymous browser session. Outstanding means queued
or running. `DEEPER_WORKERS`, `DEEPER_MAX_JOBS`, and
`DEEPER_MAX_JOBS_PER_SESSION` configure those limits.

A submission first reuses the same session's active job for the same mode,
normalized value, file type, and (for name mode) engine, or a
successful result completed within the cache TTL. Reuse does not create another
job and is checked before either quota. Errors and partial results are not
reused. For a new job, the session limit is checked before global capacity.
Completed jobs do not count toward the session limit; older completed results
may be evicted to keep the total retained jobs within the global budget.

| New submission | HTTP response |
| --- | --- |
| Session already has two outstanding jobs | `429 Too Many Requests`, `Retry-After: 5` |
| Global capacity has no room after completed-job eviction | `503 Service Unavailable`, `Retry-After: 5` |
| Accepted or reused | `303 See Other` to the private results page |

When a search worker becomes available, the manager selects the pending session
served least recently. Within that session it starts the oldest pending job.
The manager assigns work only when a worker is available, so searches from one
session cannot reserve all future worker turns in an executor backlog. Running
searches finish normally; fairness chooses the next job and does not interrupt
an active search.

For example, with one worker, if session A has A1 running and A2 queued before
session B submits B1, B1 gets the next turn, followed by A2. With two workers,
up to two searches may already be running before B arrives; B waits for a worker
to become available. The session quota is an anonymous capacity-sharing rule,
not an identity system or robust bot rate limiter: clients can create new
sessions. The queue requires no external service or IP logging.

## Queue position and progressive results

The results HTML and same-origin updates report a job's current queue position.
Snapshots and update responses include `queue_position`: a positive integer for
a queued job, or `0` when the job is running or terminal. Position is calculated
from the current fair scheduling order. Other sessions joining can change it;
it is neither a global submission sequence nor a time estimate.

Pending pages request progress about once per second. Updates use a cursor and
return new username profile records instead of repeating all earlier profiles.
The existing `search-progress.js` handles username jobs. Name jobs use separate
`document-progress.js` polling on the same private endpoint: each snapshot
contains the full bounded `references` list, `mode`, and `file_type`. The browser
deduplicates references by URL; name jobs have no reference cursor and retain
legacy profile cursor `0`. Their `checked`/`total` means provider requests
(0/1 or 1/1), not sites checked. A page
refresh renders a full current snapshot on the server. The search landing page
requires no JavaScript; without JavaScript, the results page provides manual
refresh. Results retain CSRF checks, ownership-based `404` responses, security
headers, and `no-store`. All result and update lookups require the owning browser
session. Document rendering uses inert text and validated links, with keyboard
access, polite progress announcements, and visible empty/failure/retry states.

## Worker and result lifecycle

Username workers start on demand, are recycled after 25 searches, and exit after 120 idle
seconds by default. Searches check up to 500 sites with 20 connections, a
10-second site timeout, and a 180-second overall deadline. A watchdog can kill a
blocked worker after that deadline plus 15 seconds for startup. Search limits
and extraction behavior are independent of fair scheduling.

Successful completed results can be reused for 60 seconds in the same session.
Jobs expire 15 minutes after completion, with periodic cleanup within five
seconds. Results, queues, and cache remain in memory and disappear on restart;
searches create no persistent history or reports.

Run a single HTTP application instance. Multiple independent HTTP instances
would have separate jobs and scheduling state; a shared session secret alone
does not share those jobs. `DEEPER_WORKERS` controls shared search slots, not HTTP
application instances. The default Compose resource budget and the optional
single-worker profile are described in [Performance and storage](PERFORMANCE.md).
