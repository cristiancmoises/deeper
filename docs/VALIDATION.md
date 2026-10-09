# Deeper 0.2.0: validation

**English** | [Português (Brasil)](pt-BR/VALIDATION.md)

Date: 9 October 2026. The optimization was applied to the Deeper 0.1.0 package
verified by SHA256. This validation did not access or publish to a VPS.

## Results

| Check | Result |
| --- | --- |
| Python 3.12.14 suite | 63 tests passed. |
| Python 3.11.17 suite, dependencies installed with hashes | 63 tests passed. |
| Real Maigret against local HTTP | Found/absent/unknown remained distinct; source/mirror counted once. |
| Session cache | Reuse, different session, expired/disabled TTL, and error/partial bypass passed. |
| Periodic cleanup | Expired in-memory jobs were removed without page visits. |
| Real workers | PID/database reuse, independent sites, recycling, idle timeout, EOF, deadline, and close passed. |
| Real SIGTERM | Child process exited and was collected. |
| Security | Private session, CSRF, escaping, and HTTP/HTTPS-only links preserved. |
| JavaScript-free UI | Enter key, desktop 1440×900 and mobile 390×844; zero scripts or script requests. |
| Accessibility | Reduced motion and 200% text at 320px without overflow. |
| Benchmark | 500 sites, 20 connections, same ranking and local responses; equivalent reports. |
| Runtime trimmer | Preserves code/data/licenses and does not follow links outside the root. |

`docs/PERFORMANCE.md` distinguishes cold searches, reused processes, result-cache
hits, and installed bytes. Validation profiles and endpoints were synthetic and
local.

## Reproduction

```sh
python -m pytest -q
python -m build --wheel
python tests/verify_ui.py --browser /path/to/chromium
python scripts/benchmark.py --project /path/to/deeper --output /path/to/result.json
```

Run `tests/verify_installation.py` with the Python interpreter from the
environment containing the wheel, from a directory outside the project. It
checks the installed module path, version 0.2.0, official database, local HTTP
search, health endpoint, HTML, and CSS.

The benchmark uses Linux `resource.getrusage` to measure peak worker RSS; this
does not measure all server or VPS memory. Visual QA used Chromium 153.0.8010.0
with JavaScript disabled. Playwright and this browser are not part of the Docker
runtime, and the page does not deliver JavaScript.

## Limitations

- Docker was unavailable in this environment: the image build, execution, and
  final image size **were not measured**. Disk numbers refer to installed
  `site-packages` files, excluding the Python base, Docker layers, and build cache.
- Public sites were not queried. Network conditions, blocks, and platform
  response times may dominate performance. A cold search still loads Maigret's
  database.
- The result cache may serve data obtained up to 60 seconds earlier; the page
  shows its age. Only completed searches in the same session are reused. Setting
  the TTL to zero disables reuse.
- Reused processes retain memory until recycling or up to 120 seconds idle;
  periodic scanning runs within five seconds. The job count bounds retention; a
  single HTTP instance is still required.
- Checks incompatible with a username or requiring unconfigured protocols may
  be skipped by Maigret and counted among processed items.
- Windows was not tested. The SIGTERM check is Unix-specific.
