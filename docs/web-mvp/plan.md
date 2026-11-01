# Implementation Plan: APPuesta responsive web MVP

**Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)

## Summary

Deliver a private, responsive Liga MX analysis dashboard on a single Cloudflare Python Worker. The Worker serves static assets, exposes same-origin JSON endpoints, calls API-Sports and The Odds API using server-side secrets, and persists analysis runs and resolved picks in D1. A scheduled Worker syncs recent final scores. Until the user upgrades API-Sports, the application prominently labels its 2024 statistics and US-region odds as experimental.

## Technical Context

**Language/Version**: Python 3.14 via Cloudflare Python Workers / Pyodide; local business-logic tests remain compatible with Python 3.11.
**Primary Dependencies**: `workers-py`, `workers-runtime-sdk`; Worker uses Cloudflare runtime `fetch()` and D1 bindings, avoiding CPython socket dependencies.
**Storage**: Cloudflare D1 (SQLite) for immutable picks, runs, result statuses, and cached historical team statistics.
**Testing**: `unittest` for domain and persistence behavior; Wrangler/Pywrangler local runtime; browser validation at mobile and desktop viewport sizes.
**Target Platform**: Cloudflare Workers with static assets, D1, daily Cron Trigger, and Cloudflare Access on a custom hostname.
**Performance Goals**: Render the dashboard without blocking on provider calls; show scan progress; reuse cached API-Sports team data; never wait for unrelated provider calls to calculate history.
**Constraints**: API-Sports account currently permits 2024 statistics only. The tested Odds API plan rejected `mx`, so MVP uses `us`. The model is experimental, not current-form analysis. Cloudflare account, D1 ID, Access hostname/policy, and deployment secrets must be supplied by the user before remote deployment.

## Constitution Check

- **Secrets stay out of source and browser bundles**: PASS — local `.dev.vars` and Cloudflare Worker secrets are used.
- **Do not fabricate data or hide failures**: PASS — provider/data errors are explicit, and missing stats do not use demo values.
- **Do not promise returns**: PASS — historical-data and small-sample warnings are visible.
- **Keep personal use private**: PASS — the deployment requires Cloudflare Access and disables the unprotected `workers.dev` route.
- **Preserve existing analysis**: PASS — the existing Python CLI remains usable and the web implementation shares the domain model.

## Applied Guidelines

- No Struts/Spring or other framework-migration guidelines apply.
- Cloudflare Python Workers guidance: use Python `WorkerEntrypoint`, the FFI for native `fetch()` and D1 bindings, and Python-pure packages only.
- Cloudflare D1 guidance: use prepared statements and versioned SQL migrations.

## Implementation Steps

### Step 1: [Cross-cutting] Add Cloudflare Worker scaffold and data schema
- **Requirements**: REQ-001, REQ-005, REQ-008, REQ-009
- **Design inputs**: User-selected Python Workers; Cloudflare Python Worker and D1 documentation.
- **Description**: Add a Pywrangler project, static asset binding, D1 migration, local secret example, and a D1 store. Keep the existing backend CLI intact.

### Step 2: [Cross-cutting] Implement shared analysis and provider adapters
- **Requirements**: REQ-002, REQ-003, REQ-004, REQ-006
- **Design inputs**: Current `backend/app/analysis/value_model.py`, API-Sports and Odds API response shapes, Odds API scores endpoint.
- **Description**: Reuse the Python analysis model; fetch external APIs via Worker `fetch()`; cache season-tagged historical stats; model totals pushes correctly; make prediction creation and final-score settlement deterministic and idempotent.

### Step 3: [US1] Build responsive scan dashboard
- **Requirements**: REQ-001, REQ-002, REQ-003, REQ-004
- **Design inputs**: [spec.md](./spec.md), the existing TopValuePick data contract, responsive single-user workflow.
- **Description**: Build the mobile-first home page, accessible search button, visible progress/error/empty states, pick cards, and provenance warning.

### Step 4: [US2] Persist, settle, and report historical hit rate
- **Requirements**: REQ-005, REQ-006, REQ-007
- **Design inputs**: [spec.md](./spec.md), The Odds API completed-score feed.
- **Description**: Persist one prediction per event/market/outcome/line, settle completed fixtures in the scheduled job and on explicit refresh, and render deduplicated historical results plus hit rate based only on wins and losses.

### Step 5: [US3] Secure and prepare the GitHub-to-Cloudflare deployment
- **Requirements**: REQ-001, REQ-008, REQ-009
- **Design inputs**: User-selected Cloudflare Access and single-Worker architecture.
- **Description**: Add deployment automation and exact setup instructions. Require a D1 database and Cloudflare credentials; document custom-hostname Access setup and disable `workers.dev`.

### Step 6: [Cross-cutting] Validate user journeys and analysis correctness
- **Requirements**: REQ-001 through REQ-009
- **Design inputs**: [spec.md](./spec.md), repository QA charter.
- **Description**: Run unit tests, D1 migration checks, local Worker integration, responsive browser checks, secret-exposure scan, and the independent QA review. Record any account-only validation that cannot run locally.

## Project Structure

```text
APPuesta/
├── .github/
│   └── workflows/deploy-web.yml
├── backend/
│   ├── app/analysis/value_model.py
│   └── tests/
├── cloudflare/
│   ├── migrations/0001_initial.sql
│   ├── public/{index.html,styles.css,app.js}
│   ├── src/{entry.py,analysis.py,providers.py,store.py}
│   ├── .dev.vars.example
│   ├── pyproject.toml
│   └── wrangler.toml
└── docs/
    ├── arquitectura-app.md
    └── web-mvp/{spec.md,plan.md,requirements-checklist.md,checkpoints/}
```

## Testing Strategy

- **appType**: Mixed — static responsive single-page interface and JSON API.
- **Critical user journeys**:
  1. Load a dashboard on desktop and mobile; view the experimental-data notice.
  2. Run a mocked scan; display five or fewer picks and handle empty/error states.
  3. Save a pick, process its completed score more than once, and verify idempotent win/loss/push settlement.
  4. Verify wins / (wins + losses) and sample size while pending, push, and void records remain excluded.
  5. Confirm unauthenticated external access is not enabled by the deployment configuration.
- **primaryValidationStack**: Python `unittest`, local Pywrangler/Wrangler with D1 local, browser automation for UI.
- **fallbackMatrix**:
  - `infra-tier`: Cloudflare D1 local → SQLite-backed Wrangler D1. Prerequisite: Node.js and Pywrangler.
  - `browser-tier`: browser automation at desktop and mobile viewports → static markup checks. Prerequisite: VS Code browser tooling.
- **Environment requirements**: Python 3.13+, `uv`, Node.js, internet access for provider smoke tests. Cloudflare account/zone required only for deployed Access and remote D1 validation.
- **knownGaps**: Without Cloudflare credentials, remote deployment, Access policy, and production D1 cannot be proven. Without API-Sports Pro, predictions use stale 2024 data. Odds are from the US region.
- **Test data strategy**: Mock provider payloads with deterministic fixtures; isolated D1 local database; no real API keys in tests or logs.
- **Acceptance criteria**: All automated tests pass; the Worker serves the page locally; scan and settlement scenarios return expected shapes; the responsive layout is readable; no provider secrets appear in the browser or tracked files.
- **Validation review expectations**: QA confirms settlement rules, score-source matching, hit-rate denominator, failure visibility, and that stale estimates are not presented as dependable recommendations.

## Phase 1: Setup

- [x] T001 [Plan:1.1] Scaffold Python Worker, Wrangler asset binding, D1 binding, local secret example, and project commands in `cloudflare/pyproject.toml`, `cloudflare/wrangler.toml`, and `cloudflare/.dev.vars.example`.
- [x] T002 [Plan:1.1] Create a versioned D1 schema for analysis runs, cached team data, and unique pick history in `cloudflare/migrations/0001_initial.sql`.

## Phase 2: Foundational

- [x] T003 [P] [Plan:2.1] Implement native-fetch provider adapters and historical team/stat caches in `cloudflare/src/providers.py`.
- [x] T004 [P] [Plan:2.1] Correct shared whole-goal-line probabilities and expected value for pushes in `backend/app/analysis/value_model.py`.
- [x] T005 [Plan:1.1,2.1] Implement prepared-statement D1 operations for cached stats, scans, picks, and history in `cloudflare/src/store.py`.
- [x] T006 [Plan:2.1] Implement response-to-pick mapping, event matching, and top-five filtering in `cloudflare/src/analysis.py`.

## Phase 3: User Story 1 — Scan upcoming games

- [x] T007 [US1] [Plan:2.1] Implement same-origin health, dashboard, and analysis endpoints in `cloudflare/src/entry.py`.
- [x] T008 [P] [US1] [Plan:3.1] Build the responsive Spanish home screen, warning banner, scan control, and pick cards in `cloudflare/public/index.html`, `cloudflare/public/styles.css`, and `cloudflare/public/app.js`.
- [x] T009 [US1] [Plan:2.1,3.1] Cover scan success, no-events, provider error, missing stats, and duplicate pick scenarios with deterministic tests in `cloudflare/tests/`.

## Phase 4: User Story 2 — Review reliability

- [x] T010 [US2] [Plan:2.1,4.1] Implement score-feed retrieval and idempotent 1X2/totals settlement in `cloudflare/src/providers.py`, `cloudflare/src/analysis.py`, and `cloudflare/src/store.py`.
- [x] T011 [US2] [Plan:4.1] Add daily scheduled score synchronization and a manual refresh endpoint in `cloudflare/src/entry.py` and `cloudflare/wrangler.toml`.
- [x] T012 [US2] [Plan:4.1] Add historical pick list, wins/losses/pending/push counts, hit rate, and sample size to the dashboard in `cloudflare/src/store.py` and `cloudflare/public/app.js`.
- [x] T013 [US2] [Plan:4.1] Test won/lost/push/void and the wins/(wins+losses) denominator in `cloudflare/tests/`.

## Phase 5: User Story 3 — Understand experimental data

- [x] T014 [US3] [Plan:3.1] Render statistics season, odds region, experimental status, and small-sample messaging in `cloudflare/public/index.html` and `cloudflare/public/app.js`.
- [x] T015 [US3] [Plan:3.1] Verify mobile/desktop layout, semantic labels, keyboard interaction, and visible API/D1 error states in `cloudflare/public/styles.css` and `cloudflare/tests/`.

## Phase 6: Security, deployment, and QA

- [x] T016 [Plan:5.1] Add a push-to-main GitHub Actions workflow for remote migrations and Worker deployment in `.github/workflows/deploy-web.yml`.
- [x] T017 [Plan:5.1] Document local setup, D1 creation, Cloudflare secrets, custom hostname, Access policy, GitHub secrets, and deployment in `README.md` and `docs/arquitectura-app.md`.
- [x] T018 [Plan:6.1] Run backend/Worker tests, local D1 migration, local browser validation, and secret/config review; record QA results and external deployment prerequisites.

## QA Evidence and Deployment Gate

- Worker/domain/storage suite: 12 tests passed. Existing backend regression suite: 10 tests passed.
- Wrangler applied `0001_initial.sql` locally; the actual Worker served the page, health and dashboard endpoints, persisted four picks from one live scan, and returned four pending picks with four distinct event IDs. Manual score sync checked four events and settled none because they had no final scores.
- Browser validation covered the real Worker and a deterministic UI mock: keyboard activation, explicit missing-secret and simulated D1 error states, pick metrics, and widths 320–1280 px without horizontal overflow.
- QA found that the dashboard could repeat an event after separate scans. The pending-picks query now ranks one pick per event and a regression test covers that case.
- Remote deployment remains gated on a real D1 database ID, Cloudflare account/token, custom hostname, Cloudflare Access policy, and Worker provider secrets. No remote deployment was attempted.

## Requirement Mapping

| REQ ID | Description | Plan Items | Implementation Evidence |
|--------|-------------|------------|--------------------------|
| REQ-001 | Private responsive dashboard | 1.1, 3.1, 5.1 | `cloudflare/public/*`, `cloudflare/src/entry.py`, `cloudflare/wrangler.toml` |
| REQ-002 | On-demand scan and explicit states | 2.1, 3.1 | `cloudflare/src/providers.py`, `cloudflare/src/entry.py`, `cloudflare/public/app.js` |
| REQ-003 | Complete metrics for each pick | 2.1, 3.1 | `cloudflare/src/analysis.py`, `cloudflare/public/app.js` |
| REQ-004 | Historical-data experiment warning | 3.1 | `cloudflare/public/index.html`, `cloudflare/public/app.js` |
| REQ-005 | Durable deduplicated prediction history | 1.1, 2.1, 4.1 | `cloudflare/migrations/0001_initial.sql`, `cloudflare/src/store.py` |
| REQ-006 | Automatic idempotent settlement | 2.1, 4.1 | `cloudflare/src/providers.py`, `cloudflare/src/analysis.py`, `cloudflare/src/entry.py` |
| REQ-007 | Correct hit rate and sample size | 4.1 | `cloudflare/src/store.py`, `cloudflare/public/app.js`, `cloudflare/tests/` |
| REQ-008 | Server-side secrets | 1.1, 5.1 | `cloudflare/.dev.vars.example`, `cloudflare/src/entry.py`, `.gitignore` |
| REQ-009 | Reproducible tests and deployment | 1.1, 5.1, 6.1 | `cloudflare/pyproject.toml`, `cloudflare/migrations/`, `.github/workflows/deploy-web.yml`, `README.md` |
