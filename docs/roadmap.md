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

### ZADC-001A — Canonical Artifacts and Rendering

Define the canonical artifact model: packet, completion report,
certification manifest, review report, human decision record. Implement
common envelope, canonical serialization, content digests, and rendered
views for multiple consumers (Hermes, Codex, Claude, CI, human).

### ZADC-001B — Lifecycle State and Transitions

Implement lifecycle state derivation: expected vs actual work-start SHA,
implementation head, certified code SHA, evidence carrier commit,
exact-head CI, synthetic merge verification, and state transition rules
(per Section 5.9: state is derived, not self-declared).

### ZADC-001C — Validation and Policy

Implement schema validation, referential integrity checks, policy
evaluation, and deterministic state derivation. Version and pin policy
identifiers. Prevent self-validation (PR modifying the policy that
validates itself).

### ZADC-001D — Git and GitHub Adapters

Implement adapters that resolve commits, ancestry, PR state, checks, and
merge state from Git and GitHub. These are observation tools, not
authority sources.

### ZADC-001E — Evidence and Certification

Implement evidence artifact management: content-addressed storage,
portable identifiers, evidence binding to exact subjects, and
certification manifest generation from trusted CI.

### ZADC-001F — Review and Decision Workflows

Implement independent review reports, finding management, human decision
records, and the workflow bundle aggregate that links all artifacts for a
slice instance.

## ZADC-002 — Integration

Engram integration (provenance, context retention with freshness
reconciliation), Flowstate integration (derived state presentation and
workflow controls), and cross-repository dependency pinning.

## ZADC-003 — Governance and Operations

Policy versioning and trusted-release validation path, organizational
governance, audit trail, and operational runbooks. The trusted-release
validation path ensures candidate changes are validated by the latest
trusted release, not only by candidate code.
