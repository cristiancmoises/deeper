# Deeper 0.5.0: validation

**English** | [Português (Brasil)](pt-BR/VALIDATION.md)

Date: 17 October 2026. This release adds full-name/public-document references
through keyless SecuritySearch (free Brave by default, optional free Google CSE),
preserving Maigret 0.6.6 username mode. Local automated and browser checks passed,
including bounded actual-provider observations and installed-wheel verification.
Image and production qualification remain **pending**. No provider account or key is required.

## Verified local checks and open release gates

| Check | Evidence and scope |
| --- | --- |
| Full automated suite | 262 tests passed in 13.45 seconds; exit 0. Controlled provider/app/job/UI contracts do not establish external coverage. |
| Static checks | Ruff, formatting, and Pyright passed on nine changed Python files; exit 0. |
| Browser QA | Sandboxed Chromium passed at widths 320, 768, 1024, and 1440, with 200% text and Unicode boundaries. Sixteen native-form cases covered both engines with JavaScript enabled and disabled. Controlled fixtures verify behavior, not provider findings. |
| Actual provider through local UI | Three bounded jobs through the real local application: Brave with quoted “GNU Guix”/PDF completed with 10 references; an accented full name with any file type completed with 10 references (private result contents not published); Google CSE with “GNU Guix”/PDF produced an honest unavailable error while retaining engine `google`. No paid fallback, automatic engine switch, page reload after initial result navigation, or browser errors were observed. |
| Dependency advisories | Fresh `pip-audit` checked 68 locked packages: zero known advisories and zero skipped packages; exit 0. A point-in-time check, not proof of vulnerability absence. |
| Compose and documentation | Parsing and rendered defaults passed: scheduling 2/64/2, cache 60 seconds, retention 900 seconds, provider 100/day and timeout 12 seconds, no provider key, private bind, read-only filesystem, dropped capabilities, PID limit 128, 512 MiB RAM / 1 GiB combined budget. TOML/version and local Markdown links passed. |
| Installed replacement wheel | `deeper_maigret-0.5.0-py3-none-any.whl`, SHA-256 `b38f3ac1070511bdaa1c8309bd264684304a2a96ef123be81c71ea8298417c28`, passed verification outside the checkout from installed `site-packages` on Python 3.12.12 with Maigret 0.6.6. The database check found 10 sites; actual Maigret with synthetic local HTTP fixtures completed 3 checks, 1 inconclusive result, and 1 found profile. Health/version, HTML/CSP, installed assets, and native free-engine forms passed. These local fixtures are not public-site findings. |
| Release image | Pending build and checks of the exact replacement image. Installed-wheel evidence does not qualify the container or deployment. |
| Further real-provider coverage | Not established for DOCX, legitimate empty results, every filter/name, or sustained availability. The three observed jobs above are the actual integration evidence. |
| Production qualification | Pending exact artifact/version, `/health`, name search, mixed-mode concurrency, memory budget, session isolation, and no OOM. The live link does not certify this release. |
| Public screenshots | Actual 0.5.0 local UI in sandboxed Chromium: name/PDF/Brave form with consent unchecked, and ten real Brave “GNU Guix”/PDF index references. The form does not claim document findings for its entered name. Public results use a non-personal example; file types are inferred from URLs, with no document download or content/MIME verification. |

The prior Serper candidate's 233-test baseline and installed-wheel/browser checks
are historical, not qualification for replacement artifacts or deployment.
Maigret fixtures use the real engine with local HTTP and synthetic profiles.
Only the actual-provider row and its public results screenshot represent external
provider observations; fixture results must not be presented as real findings.

## Reproduction

Use the project's existing QA environment; browser and build tools are external
development tools, not new runtime dependencies:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_documents.py tests/test_name_jobs.py tests/test_name_app.py tests/test_document_ui.py
docker compose config --quiet
.venv/bin/python -m build --wheel
.venv/bin/python tests/verify_ui.py --browser /path/to/chromium --output /tmp/deeper-username-qa
.venv/bin/python tests/verify_documents_ui.py --browser /path/to/chromium --output /tmp/deeper-document-qa
```

Test the built wheel from a fresh environment outside the checkout with the
hash-locked runtime dependencies. Confirm the installed version, Maigret
database, `/health`, HTML/CSS, both progress scripts, source icons, and license
files. A package health response checks package availability; it does not
validate SecuritySearch or engine connectivity or search coverage.

Real-provider checks need a bounded call budget, not an account, API key, or paid
API. Record the selected engine and actual outcomes separately from fixtures.
Google CSE may rate-limit requests; HTTP 503 or bot protection must produce an
honest unavailable state. Do not retry via a paid mechanism, switch engines
automatically, reuse personal browser cookies, or solve CAPTCHA. HTTP 200 must
also have the valid successful JSON shape before it can count as success.

## Limits of this evidence

- A quoted exact-name query and search-index reference do not prove identity,
  document contents, MIME type, availability, or completeness. Unknown file
  types remain unverified; empty responses do not prove absence.
- The provider timeout is a normal `urllib` HTTP timeout (12 seconds by default,
  configurable from 1 to 30), not the username process watchdog or a hard
  wall-clock bound. Responses are capped at 1 MiB with no automatic retries.
- The 100-call UTC daily guard and one-second call spacing protect shared
  resources per process; the counter resets on restart. They are not billing
  controls. The integration uses no paid API or automatic engine fallback.
- Both modes share the 2-worker/64-global/2-session defaults, 60-second private
  cache, and 900-second completed-job retention. Run one HTTP application
  instance. Session limits are capacity controls, not robust bot identity checks.
- Previous benchmarks in [PERFORMANCE.md](PERFORMANCE.md) are historical local
  username measurements. They do not measure SecuritySearch latency, new-release image
  size, production throughput, or public-site coverage.
- Target support for Python 3.11/3.12 and documentation for Windows do not
  establish a fresh test on every OS/interpreter. Record actual release runs;
  Unix signal tests do not establish Windows behavior.
