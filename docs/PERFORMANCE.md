# Deeper 0.2.0 — performance and storage

**English** | [Português (Brasil)](pt-BR/PERFORMANCE.md)

Local measurements taken on 9 October 2026, Linux x86_64, Python 3.12.14. The
main improvement is on subsequent searches in an already-loaded process.

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

## Method and integrity

- The benchmark uses official **Maigret 0.6.6**, its official database selection
  and ranking, 500 sites, and 20 connections. Only endpoints for selected sites
  are replaced with local fixtures. The engine, parser, and process lifecycle
  are real.
- The local HTTP server responds after 5ms. Each search returns 50 CLAIMED,
  400 absent, and 50 inconclusive profiles. Both versions produced equivalent
  counts in all five runs. No real people's usernames were searched.
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
  image layers, or build cache. **Docker image size was not measured:** Docker
  was unavailable. A build also requires additional temporary storage on the
  VPS.

## Reproduction

With both version trees and their dependencies installed, run on Linux:

```sh
python scripts/benchmark.py --project /path/to/deeper-0.1.0 --output /path/to/baseline.json
python scripts/benchmark.py --project /path/to/deeper-0.2.0 --output /path/to/optimized.json
```

Run sequentially to avoid overlap between scenarios. The script validates the
counts and shuts down all processes when finished. To measure an image on your
VPS, use `docker image inspect deeper:0.2.0 --format '{{.Size}}'` and
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
