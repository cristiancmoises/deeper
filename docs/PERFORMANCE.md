# Deeper 0.3.0 — performance and storage

**English** | [Português (Brasil)](pt-BR/PERFORMANCE.md)

Historical search and storage measurements below compare 0.1.0 with 0.2.0.
The 0.3.0 progress-payload measurement is reported separately; it measures
local synthetic traffic, not response time at public sites.

## Historical 0.1.0 to 0.2.0 search and storage

Measurements taken on 9 October 2026, Linux x86_64, Python 3.12.14. The main
improvement was on subsequent searches in an already-loaded process.

| Measure | 0.1.0 | 0.2.0 |
| --- | ---: | ---: |
| First cold search, one sample | 2.593s | 2.521s |
| Subsequent searches, median of four samples | 2.705s | 1.130s |
| Same-session username repeat | 2.419s | 0.347ms (cache) |
| HTTP requests on repeat | 500 | 0 |
| Processes created, five searches + repeat | 6 | 1 |
| Peak worker RSS | 66.2 MiB | 66.3 MiB |
| Installed files in site-packages | 193.7 MiB | 128.3 MiB |

Subsequent search time was **58.2% lower**. Installed files were **33.8% smaller**,
a logical reduction of 65.4 MiB. MiB = 1,048,576 bytes. These are local samples,
not guaranteed response times for public sites.

## Incremental progress in 0.3.0

Measured on 10 October 2026 with Python 3.12.12, Linux x86_64 (kernel 7.2.9,
glibc 2.41), Maigret 0.6.6, 500 ranked sites, 20 connections, one worker, and a
local HTTP fixture with a 5ms response delay. Two searches each returned 50
claimed profiles, 400 absent sites, and 50 inconclusive checks.

| Measure | Observed |
| --- | ---: |
| Running progress messages, two searches | 14 |
| Incremental JSON-line payload total | 12,797 bytes |
| Cumulative-snapshot reference total | 37,373 bytes |
| Progress payload reduction | 65.8% |
| Cold / second synthetic search | 4.303s / 3.249s |
| Completed-result cache repeat | 0.305ms, 0 HTTP requests |
| Peak single worker RSS | 96.6 MiB |

The byte totals compare the actual emitted delta events with a reference that
repeats all profiles accumulated so far at each same progress event. In a
separate 100-site sample with only four progress messages, deltas were 434 bytes
versus 410 bytes cumulatively; that sparse sample did not benefit. The reduction
therefore depends on the number and size of progress events. These measurements
do not make Maigret's external checks faster and do not predict public-site
latency.

## Method and integrity

- The benchmark uses official **Maigret 0.6.6**, its official database selection
  and ranking, 500 sites, and 20 connections. Only endpoints for selected sites
  are replaced with local fixtures. The engine, parser, and process lifecycle
  are real.
- The local HTTP server responds after 5ms. Each search returns 50 CLAIMED,
  400 absent, and 50 inconclusive checks. The historical 0.1.0/0.2.0 comparison
  produced equivalent counts in all five runs; the 0.3.0 payload sample used
  two runs. No real people's usernames were searched.
- The first search includes imports and database loading. The next four use
  different usernames; the improvement comes from worker reuse, not result cache.
- The final repeat uses the same username and session: 0.2.0 reuses a completed
  result for up to 60 seconds. The measure includes backend submission/snapshot,
  **not** browser network or rendering time. A cache hit is not a new check.
- RSS is measured with `resource.getrusage(RUSAGE_SELF).ru_maxrss` in a Linux
  worker. It excludes the server, fixtures, queue, and cached jobs. Warm workers
  retain this memory until recycled or idle; the default allows two concurrent
  workers.
- Disk is the sum of regular-file sizes, excluding symbolic links, in clean
  Python 3.12 environments using the same lock. The baseline uses a normal pip
  install of 0.1.0; the new runtime uses `--no-compile`, version 0.2.0, and the
  runtime trimmer. Code, database, and licenses are retained. A smoke check after
  trimming runs real Maigret against local HTTP and checks health, HTML, and CSS
  from the installed wheel.
- Counts do not include Python/Linux base images, block overhead, downloads,
  image layers, or build cache. **The 0.3.0 Docker image was not built locally:**
  Compose configuration was checked, while image build and size are reserved
  for the IONOS deployment. A build also requires additional temporary storage.

## Reproduction

With the required version trees and their dependencies installed, run on Linux:

```sh
python scripts/benchmark.py --project /path/to/deeper-0.1.0 --output /path/to/baseline.json
python scripts/benchmark.py --project /path/to/deeper-0.2.0 --output /path/to/optimized.json
python scripts/benchmark.py --project /path/to/deeper-0.3.0 --output /path/to/progress.json --runs 2 --sites 500
```

Run sequentially to avoid overlap between scenarios. The script validates the
counts and shuts down all processes when finished. To measure an image on your
VPS, use `docker image inspect deeper:0.3.0 --format '{{.Size}}'` and
`docker system df`. Deeper does not run global cleanup commands.

## How storage is controlled

The runtime needs no database, history, frontend build, or browser. Docker
installs with hashes and without a download cache, then uses a final stage that
copies the trimmed environment. Unused dependency tests, bytecode, unused
`pycountry` translations, and installer tools are removed; required libraries
and their license files remain available.

`compose.yaml` rotates logs across three 2 MB files (approximately 6 MB plus
overhead), uses a read-only filesystem, and limits `/tmp` to a 32 MB tmpfs. These
limits apply to the Deeper container, not proxy or other service logs. The tmpfs
uses memory and may be paged to swap by the host. Previous Docker image versions
and build layers continue to count toward disk usage.

Official configuration references: [json-file log rotation](https://docs.docker.com/engine/logging/drivers/json-file/),
[tmpfs mounts](https://docs.docker.com/engine/storage/tmpfs/), and
[build cache](https://docs.docker.com/build/cache/).
