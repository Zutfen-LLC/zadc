# ZADC Roadmap

This roadmap tracks the phased implementation of the Zutfen Agentic
Development Contract. Each work slice is governed by an authorized packet
and must be independently reviewed before advancement.

## ZADC-000 — Universal Repository Bootstrap

**Status:** In progress

Create the universal ZADC repository, establish a clean installable Python
foundation, configure CI/CD, and open a draft PR. No protocol functionality
is implemented.

## ZADC-001 — Contract Core

### ZADC-001A — Canonical artifacts and rendering

Define the canonical artifact model: packet, completion report,
certification manifest, review report, human decision record. Implement
common envelope, canonical serialization, content digests, and rendered
views for multiple consumers (Hermes, Codex, Claude, CI, human).

### ZADC-001B — Workflow bundles and derived lifecycle

Implement workflow bundle management and lifecycle state derivation:
expected vs actual work-start SHA, implementation head, certified code SHA,
evidence carrier commit, exact-head CI, synthetic merge verification, and
state transition rules. State is derived, not self-declared.

### ZADC-001C — Git subject and evidence validation

Implement Git subject validation, evidence binding to exact subjects,
schema validation, referential integrity checks, policy evaluation, and
deterministic state derivation. Version and pin policy identifiers. Prevent
self-validation (PR modifying the policy that validates itself).

### ZADC-001D — GitHub and GitHub Actions reconciliation

Implement adapters that resolve commits, ancestry, PR state, checks, and
merge state from Git and GitHub Actions. These are observation tools, not
authority sources.

### ZADC-001E — Review, correction, and human-decision workflow

Implement independent review reports, finding management, correction
packets, human decision records, and the workflow bundle aggregate that
links all artifacts for a slice instance.

### ZADC-001F — First live project dogfood

Exercise the full contract end-to-end on a real project, validating the
toolchain, artifact flow, and review workflow under live conditions.

## ZADC-002 — Engram provenance integration

Engram integration for provenance, context retention with freshness
reconciliation, and cross-repository dependency pinning.

## ZADC-003 — Flowstate orchestration integration

Flowstate integration for derived state presentation and workflow controls.
