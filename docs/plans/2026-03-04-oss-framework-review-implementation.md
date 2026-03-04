# OSS Framework Readiness Review (Implementation Snapshot)

## Objective

Execute a practical, evidence-based review of what currently works, what does not, what is critical, and what should be prioritized next to evolve Neural Sieve into an open source framework for shareable context networks and trusted insight delivery.

## Evidence Collected

- `uv run pytest -q` -> `229 passed`
- `npm test --prefix extension` -> `497 passed`
- `npm run build --prefix extension` -> Chrome/Firefox/Safari builds pass
- `uv run ruff check` -> clean after import cleanup

## What Works (Confirmed)

1. Backend API stability: core auth, capsules, social, discover, feed, import, and skills flows are passing tests.
2. Extension reliability: unit tests pass and production builds generate installable artifacts for all supported browsers.
3. Security posture improvements are present:
   - CORS origins are now configurable (`settings.cors_origins`).
   - Capture scraper validates DNS/IP targets and re-validates redirect targets.
4. Social/feed parity fixes are present:
   - HTMX follow requires public target sieves.
   - HTMX feed/discover now filter inactive capsules.

## What Did Not Work (Now Fixed in This Implementation Pass)

1. Context-menu selection capture semantics were ambiguous.
   - Fixed by introducing explicit capture modes (`page`, `selection`, `auto`) in extension background capture flow.
2. Feed empty-state CTA pointed to a non-existent `/capture` page.
   - Fixed to route users to `/` (feed page with quick capture).
3. README auth note was stale.
   - Updated account setup note to reflect API key use for extension quick capture, while MCP/CLI use email + DB URL.
4. Ruff quality gate failed due to unused imports in tests.
   - Cleaned unused imports in affected test files.

## Current Severity Assessment

### Critical

- None currently blocking local reliability or build/test execution in this snapshot.

### High

1. Production hardening gaps still need explicit policy and enforcement:
   - secure cookie behavior by environment.
   - non-placeholder JWT secret policy in deploy pipelines.
2. OSS stability needs explicit API compatibility/versioning policy before broad external adoption.

### Medium

1. Extension capture behavior should gain targeted tests for mode-specific semantics:
   - page capture ignores selection preference.
   - selection capture prefers selected text/html.
2. Bundle size warnings are persistent; should be addressed with code splitting/optimization.
3. HTMX parity should keep dedicated regression tests for future changes.

### Low

1. Remaining documentation polish and contributor onboarding streamlining.
2. Optional cleanup of warning noise in tests (e.g. cookie deprecation warnings from httpx usage pattern).

## 30-Day Backlog (Stabilization + OSS Foundation)

## Week 1: Reliability and Security Gates

1. Add/lock env-aware auth cookie security defaults.
2. Enforce non-default JWT secret in non-local environments.
3. Add regression tests for HTMX follow privacy + active capsule filtering.

## Week 2: Extension Capture Correctness

1. Add tests for capture mode semantics (`page`/`selection`/`auto`).
2. Add tests for context menu selection path using `selectionText`.
3. Validate consistent API-key error handling UX across quick capture flows.

## Week 3: OSS Interface Hardening

1. Publish API compatibility/versioning strategy.
2. Document extension auth contract and MCP setup contract.
3. Define framework module boundaries (capture, storage, ranking, export, sharing).

## Week 4: Trusted Insight Layer Foundations

1. Add explicit source attribution contract for surfaced insights:
   - source URL
   - source identity/author
   - capture timestamp
   - provenance flags
2. Add acceptance tests for attribution presence in retrieval surfaces.
3. Define ranking transparency minimums for “right person insight” recommendations.

## Acceptance Criteria for OSS Launch Candidate (Initial)

1. Build/test/lint all green in CI.
2. No critical findings open in security/privacy/auth domains.
3. Public API contract documented with versioning and deprecation rules.
4. Extension quick capture and selection capture are behaviorally deterministic and tested.
5. Source attribution is present and auditable in user-facing insight flows.
