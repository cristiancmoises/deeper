# Deeper 0.5.0: validation

**English** | [Português (Brasil)](pt-BR/VALIDATION.md)

Date: 17 October 2026. This release adds full-name/public-document references
through Serper while preserving the Maigret 0.6.6 username mode. Automated
provider fixtures and browser tests are separate from real-provider evidence.
Real Serper qualification, production 0.5.0 qualification, and replacement
screenshots remain **pending** until the selected provider key is configured.

## Verified local qualification

| Check | Evidence and scope |
| --- | --- |
| Full automated suite | 233 tests passed in 12.68 seconds; exit 0. |
| Provider and application/job integration | The full suite includes controlled HTTP/provider payloads, query validation, response bounds, filtering, quota/errors, credential exclusion, consent, ownership, shared scheduling, and snapshots. These are not live Serper searches. |
| Installed 0.5.0 wheel | Built wheel installed in a private virtual environment; verifier ran from outside the checkout and confirmed import from installed `site-packages/deeper`, package/health version 0.5.0, HTML/CSS, both progress scripts, all three source SVG icons, and name-mode filter/required-consent controls; exit 0. |
| Real Maigret with local HTTP | Installed-wheel smoke completed three checks, with one inconclusive result and one synthetic profile found. Only loopback fixtures were queried. |
| Browser QA | Legacy username and new document QA passed in real Chromium; exit 0. Document checks covered widths 320, 768, 1024, and 1440 with controlled results. Nine Unicode-boundary checks also passed. Browser fixtures do not establish real-provider coverage. |
| Dependency advisories | `pip-audit` of the hash-locked dependencies checked 68 packages: zero known advisories, zero skipped packages; exit 0. This is a point-in-time advisory check, not proof of vulnerability absence. |
| Compose configuration | Configuration validation and rendered-setting checks passed: shared 2/64/2 limits, 60-second cache, 900-second retention, empty example key, provider defaults, 512 MiB RAM / 1 GiB combined budget, and existing confinement; exit 0. Production image/deployment qualification remains pending. |
| Real-provider smoke | Pending: bounded real full-name searches, including PDF, DOCX, non-ASCII names, legitimate empty results, errors, and filter behavior. |
| Production qualification | Pending: exact release artifact/version, `/health`, name search, mixed-mode concurrency, memory budget, session isolation, and no OOM on the Deeper deployment. |
| Public screenshots | Existing README images were captured for 0.4.0 username mode. Real 0.5.0 name/document captures have not replaced them. |

The local checks above passed; real-provider and production release gates remain
pending. Maigret tests use the real
engine with local HTTP fixtures and synthetic profiles. Serper tests use
controlled responses rather than credits or live accounts. Browser fixtures
test UI behavior; their results must not be published as real provider findings.

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
validate Serper credentials, credits, connectivity, or search coverage.

Real-provider checks require a privately configured `SERPER_API_KEY` and a
bounded call budget. Never print the credential or include it in test reports,
screenshots, command arguments, or source control. A missing key must produce
the unavailable state, never substitute fabricated references. Record actual
provider outcomes separately from fixtures before claiming live success.

## Limits of this evidence

- A quoted exact-name query and search-index reference do not prove identity,
  document contents, MIME type, availability, or completeness. Unknown file
  types remain unverified; empty responses do not prove absence.
- The provider timeout is a normal `urllib` HTTP timeout (12 seconds by default,
  configurable from 1 to 30), not the username process watchdog or a hard
  wall-clock bound. Responses are capped at 1 MiB with no automatic retries.
- The 100-call UTC daily guard applies per process and resets on restart. It
  cannot guarantee account-wide charges or control other clients. No credit
  purchase or automatic top-up is performed.
- Both modes share the 2-worker/64-global/2-session defaults, 60-second private
  cache, and 900-second completed-job retention. Run one HTTP application
  instance. Session limits are capacity controls, not robust bot identity checks.
- Previous benchmarks in [PERFORMANCE.md](PERFORMANCE.md) are historical local
  username measurements. They do not measure Serper latency, new-release image
  size, production throughput, or public-site coverage.
- Target support for Python 3.11/3.12 and documentation for Windows do not
  establish a fresh test on every OS/interpreter. Record actual release runs;
  Unix signal tests do not establish Windows behavior.
