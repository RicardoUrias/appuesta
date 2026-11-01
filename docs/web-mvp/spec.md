# Feature Specification: APPuesta responsive web MVP

> Governed by: project-specific principles documented in the repository README and QA charter.

**Feature Branch**: `web-mvp`
**Created**: 2026-10-31
**Status**: Approved for MVP implementation
**Input**: User requests a personal responsive website to scan upcoming Liga MX matches, display five experimental value picks, record settled outcomes, and show historical hit rate. The chosen runtime is Cloudflare Python Workers with Cloudflare Access; until API-Sports Pro is available, use 2024 historical statistics and US-region odds with explicit warnings.

## Scope Baseline

- **Discovery method**: User requirements and current repository/API behavior.
- **Total items discovered**: 9 requirements.
- **Items in scope**: 9.
- **Out of scope**: Android app, automatic bet placement, real-money/stake management, public multi-user accounts, and claims that stale-data picks are reliable recommendations.

## User Scenarios & Testing

### User Story 1 - Scan upcoming games (Priority: P1)

As the sole user, I want a responsive home page with a search button so I can request current Liga MX matches, bookmaker odds, and a ranked Top 5 without exposing provider credentials.

**Why this priority**: The scan is the primary workflow and provides the data used by the remaining journeys.

**Independent Test**: Open the site on a phone-sized and desktop viewport, run a scan against mocked API responses, and verify loading, success, empty, and error states.

**Acceptance Scenarios**:

1. **Given** available events and valid provider data, **When** I press the search button, **Then** the page shows up to five ranked picks with match, kickoff, market, selection, bookmaker, odds, model probability, implied probability, edge, and expected value.
2. **Given** missing credentials, unavailable provider data, or no upcoming events, **When** I request a scan, **Then** the page shows a clear recoverable message and does not fabricate picks.
3. **Given** the page is opened at a mobile viewport, **When** I view a pick, **Then** its essential data remains readable without horizontal scrolling.

### User Story 2 - Review reliability (Priority: P2)

As the sole user, I want a persistent prediction history and hit-rate summary so I can evaluate the prototype against completed match outcomes.

**Why this priority**: A historical result is necessary to judge whether the analysis is useful before paying for current API-Sports data.

**Independent Test**: Seed a prediction, sync a completed game score, and verify its status, history row, and aggregate rate.

**Acceptance Scenarios**:

1. **Given** a previously saved prediction, **When** its event appears as completed in the scores feed, **Then** the system settles it as won, lost, push, or void using the saved market and line.
2. **Given** settled picks, **When** I open the home page, **Then** it shows wins, losses, pending/push counts, hit rate, and the number of decisive results used in that rate.
3. **Given** the same analysis or score is processed more than once, **When** it is saved, **Then** duplicate predictions do not inflate history or change an already settled result.

### User Story 3 - Understand data limitations (Priority: P1)

As the sole user, I want the age and origin of the data visible beside the analysis so I do not mistake an experimental estimate for a current or guaranteed recommendation.

**Why this priority**: The MVP compares current odds with historical 2024 statistics and non-Mexican-region odds.

**Independent Test**: Load the home page and verify that the experimental status, statistics season, and odds region are visible before any pick is interpreted.

**Acceptance Scenarios**:

1. **Given** the MVP is configured with historical 2024 statistics and US-region odds, **When** the page loads or displays picks, **Then** it prominently labels that data combination as experimental and not a betting recommendation.
2. **Given** there are too few settled predictions, **When** the page displays the hit rate, **Then** it also displays the sample size and does not imply statistical reliability.

### Edge Cases

- API provider returns a non-success status, an invalid body, no events, missing odds, or missing team statistics.
- API-Sports free-tier rate limits are reached; already cached statistics remain available and no fallback demo data is used.
- Team names differ in accents, punctuation, or common club abbreviations.
- A totals market uses an unsupported quarter-goal line; it is omitted rather than settled incorrectly.
- A completed event has no score, or a score cannot be matched to the event; no win/loss is invented.
- The same match offers multiple markets, bookmakers, or outcomes; each event/market/outcome/line is recorded at most once.
- D1 is unavailable or not migrated; return an explicit service error instead of a success-shaped empty history.
- A user accesses the deployed hostname outside the configured Cloudflare Access policy; deployment must not expose the app through a public bypass hostname.

## Requirements

### Functional Requirements

- **REQ-001**: The system MUST present a responsive personal dashboard that works on mobile and desktop, and the deployed application MUST be protected by Cloudflare Access.
- **REQ-002**: The user MUST be able to request upcoming Liga MX matches and a ranked list of up to five picks; the page MUST expose loading, empty, success, and recoverable error states.
- **REQ-003**: Each pick MUST show the match and kickoff, market and selection, bookmaker and decimal odds, estimated model probability, implied probability, edge, and expected value.
- **REQ-004**: The system MUST label picks as experimental while statistics are from season 2024 or odds are from the US region, and MUST NOT describe them as guaranteed or reliable recommendations.
- **REQ-005**: The system MUST persist selected picks across visits and retain enough immutable event, market, line, odds, and model data to evaluate each saved prediction later.
- **REQ-006**: The system MUST automatically settle completed saved picks from the provider scores feed, with correct win/loss/push/void handling for 1X2 and supported totals markets; settlement MUST be idempotent.
- **REQ-007**: The home page MUST show a persistent history and hit rate calculated as wins / (wins + losses); pending, push, and void picks MUST be excluded from that denominator and the decisive sample size MUST be shown.
- **REQ-008**: Provider credentials MUST remain server-side as local development secrets or Cloudflare Worker secrets and MUST NOT be committed or returned to the browser.
- **REQ-009**: The repository MUST include repeatable local development, tests, D1 migrations, and a GitHub Actions deployment workflow; remote deployment MUST require explicit Cloudflare account/database configuration and credentials.

### Key Entities

- **Analysis run**: Timestamped scan, configuration/data provenance, event count, and selected-pick count.
- **Pick**: One saved event/market/outcome/line prediction with bookmaker, odds, model metrics, source season/region, and immutable settlement state.
- **Settled result**: Final score and outcome status (`pending`, `won`, `lost`, `push`, or `void`) for a pick.
- **Reliability summary**: Wins, losses, excluded outcomes, decisive sample size, and hit rate derived from persisted picks.

## Success Criteria

### Measurable Outcomes

- **SC-001**: The user can reach the home dashboard and request an analysis from phone and desktop layouts without horizontal page scrolling.
- **SC-002**: A successful scan displays no more than five picks, and every displayed pick has a corresponding persisted record.
- **SC-003**: Reprocessing the same event, outcome, and line leaves the history count and settled status unchanged.
- **SC-004**: Won/lost/push/void result tests match final score rules for 1X2, half-goal totals, and whole-goal totals.
- **SC-005**: The displayed hit-rate denominator equals wins plus losses; pending, push, and void counts do not affect it.
- **SC-006**: No provider key appears in static assets, API responses, or Git-tracked local configuration.
