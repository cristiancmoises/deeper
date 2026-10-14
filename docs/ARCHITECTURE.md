# Deeper 0.4.0 — search architecture

**English** | [Português (Brasil)](pt-BR/ARCHITECTURE.md)

Deeper runs one HTTP application with an in-memory job manager and a bounded
pool of isolated Maigret search processes. The HTTP application owns session
privacy, admission, scheduling, progress, and temporary results. A worker loads
the Maigret database once and uses an independent site copy for each search.

## Admission and fair scheduling

The default limits are two running searches, 64 outstanding jobs globally, and
two outstanding jobs per anonymous browser session. Outstanding means queued
or running. `DEEPER_WORKERS`, `DEEPER_MAX_JOBS`, and
`DEEPER_MAX_JOBS_PER_SESSION` configure those limits.

A submission first reuses the same session's active job for that username or a
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
return new profile records instead of repeating all earlier profiles. A page
refresh renders a full current snapshot on the server. The search landing page
requires no JavaScript; without JavaScript, the results page provides manual
refresh. All result and update lookups require the job's owning browser session.

## Worker and result lifecycle

Workers start on demand, are recycled after 25 searches, and exit after 120 idle
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
does not share those jobs. `DEEPER_WORKERS` controls search processes, not HTTP
application instances. The default Compose resource budget and the optional
single-worker profile are described in [Performance and storage](PERFORMANCE.md).
