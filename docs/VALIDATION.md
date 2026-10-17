# Deeper 0.5.0: validation

**English** | [Português (Brasil)](pt-BR/VALIDATION.md)

Date: 17 October 2026. This release adds full-name/public-document references
through keyless SecuritySearch (free Brave by default, optional free Google CSE),
preserving Maigret 0.6.6 username mode. Local automated and browser checks passed,
including bounded actual-provider observations and installed-wheel verification.
Image verification and bounded production browser, security, and memory checks
also passed within the scope below. Live concurrency and sustained capacity were
not established. No provider account or key is required.

## Verified checks and production observations

| Check | Evidence and scope |
| --- | --- |
| Full automated suite | Merged tree: 262 tests passed in 14.12 seconds; exit 0. Controlled provider/app/job/UI contracts do not establish external coverage. |
| Static checks | Ruff, formatting, and Pyright passed on nine changed Python files; exit 0. |
| Browser QA | Sandboxed Chromium passed at widths 320, 768, 1024, and 1440, with 200% text and Unicode boundaries. Sixteen native-form cases covered both engines with JavaScript enabled and disabled. Controlled fixtures verify behavior, not provider findings. |
| Actual provider through local UI | Three bounded jobs through the real local application: Brave with quoted “GNU Guix”/PDF completed with 10 references; an accented full name with any file type completed with 10 references (private result contents not published); Google CSE with “GNU Guix”/PDF produced an honest unavailable error while retaining engine `google`. No paid fallback, automatic engine switch, page reload after initial result navigation, or browser errors were observed. |
| Dependency advisories | Fresh `pip-audit` checked 68 locked packages: zero known advisories and zero skipped packages; exit 0. A point-in-time check, not proof of vulnerability absence. |
| Compose and documentation | Parsing and rendered defaults passed: scheduling 2/64/2, cache 60 seconds, retention 900 seconds, provider 100/day and timeout 12 seconds, no provider key, private bind, read-only filesystem, dropped capabilities, PID limit 128, 512 MiB RAM / 1 GiB combined budget. TOML/version and local Markdown links passed. |
| Installed replacement wheel | `deeper_maigret-0.5.0-py3-none-any.whl`, SHA-256 `b38f3ac1070511bdaa1c8309bd264684304a2a96ef123be81c71ea8298417c28`, passed verification outside the checkout from installed `site-packages` on Python 3.12.12 with Maigret 0.6.6. The database check found 10 sites; actual Maigret with synthetic local HTTP fixtures completed 3 checks, 1 inconclusive result, and 1 found profile. Health/version, HTML/CSP, installed assets, and native free-engine forms passed. These local fixtures are not public-site findings. |
| Release image | Built on the backend host with Docker 26.1.5 using a 512 MiB RAM / 768 MiB combined build limit and 1 CPU. Source commit `af52f8623c2be4deb7f62bc187deff9b8eb3c5cf`; image ID `sha256:30a44f72adfdaaa51c11fa0d7239558a2241dbaeccd071caed4c75911b49fd35`; size 255,663,719 bytes. Verification inside the actual image passed with Python 3.12.15, Maigret 0.6.6, and installed `/opt/venv` site-packages: local synthetic Maigret 3 checks / 1 inconclusive / 1 profile, CSP, forms, assets, healthy container, and `OOMKilled=false`. Build limits are distinct from the unchanged runtime budget. |
| Further real-provider coverage | Production DOCX success and unavailability are recorded below. Legitimate empty results, every filter/name, and sustained provider availability were not established. Provider outcomes are intermittent; a failure is not an empty successful search. |
| Production activation and health | The image above was activated on the backend's existing private binding, preserving the IONOS front end and shared reverse-proxy route. Public HTTPS `/health` returned version 0.5.0 and status `ok`. Health alone does not qualify provider behavior or production capacity. |
| Production provider and username checks | Sandboxed Chromium 153 submitted exactly four name jobs and one username job, with no retries: quoted “GNU Guix”/PDF Brave completed with 10 references; username `gnu-guix` completed 500/500 checks with six profiles; “GNU Guix”/DOCX Brave returned unavailable with zero references (an error, not an empty success); “GNU Guix”/PDF Google CSE completed with 10 references; a separately selected Google CSE “Creative Commons”/DOCX job completed with four references. Actual engine labels were retained, with no paid fallback or automatic switch. No page reloads after initial result navigation, browser errors, or external browser requests were observed. These counts are index/profile observations, not identity or document-content verification. |
| Production security and session checks | HTTPS checks passed for CSP, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, and session-cookie Secure/HttpOnly/SameSite=Strict flags. Another session received HTTP 404 from the private updates API. No cookie values are published. |
| Mixed-mode scope | The same session accepted both modes, but the name job had already completed when the username job was submitted. No actual overlap, queued state, or sustained-capacity benchmark was observed. Automated tests cover scheduling and isolation contracts; this live run does not establish concurrency capacity. |
| Production memory and health | 38 samples from 19:06:48 to 19:10:16 UTC on 17 October recorded a peak of 143.3 MiB within the 512 MiB runtime limit; every sample was healthy, with no OOM and zero restarts. The final 19:11:36 UTC idle check recorded 50.7 MiB, healthy, zero restarts, and no OOM. This is a bounded observation, not a long-duration or load benchmark. |
| Transport preflight and deployment scope | The first 10-second health preflight timed out before any jobs; a 30-second preflight allowance worked without TLS or sandbox changes. No product defect was established. Only the Deeper backend changed; shared proxies were unchanged. The temporary candidate container and retired 0.4 container/image were removed by explicit identity; the 0.5 image was retained and only its release container remains running. The image source is the commit above; subsequent release edits are documentation only, with runtime and README unchanged. No further live jobs were submitted after the call budget was exhausted. |
| Public screenshots | Actual 0.5.0 local UI in sandboxed Chromium: name/PDF/Brave form with consent unchecked, and ten real Brave “GNU Guix”/PDF index references. The form does not claim document findings for its entered name. Public results use a non-personal example; file types are inferred from URLs, with no document download or content/MIME verification. |

The prior Serper candidate's 233-test baseline and installed-wheel/browser checks
are historical, not qualification for replacement artifacts or deployment.
Maigret fixtures use the real engine with local HTTP and synthetic profiles.
The actual-provider rows and public results screenshot represent external
observations; fixture results must not be presented as real findings.

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
