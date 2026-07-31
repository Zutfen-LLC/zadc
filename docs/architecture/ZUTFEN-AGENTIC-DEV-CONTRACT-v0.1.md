# Zutfen Agentic Development Contract v0.1

**Document ID:** `ZUTFEN-AGENTIC-DEV-CONTRACT-v0.1`  
**Abbreviation:** `ZADC`  
**Status:** Draft — implementation baseline  
**Contract version:** `0.1.0`  
**Owner:** Zutfen LLC  
**Canonical repository:** `Zutfen-LLC/zadc`  
**Python distribution / import / CLI:** `zutfen-zadc` / `zadc` / `zadc`  
**Decision authority:** Human project owner or explicitly delegated human maintainer  
**Intended consumers:** Humans, Hermes, Codex, Claude, other coding/review agents, CI systems, Git/GitHub adapters, Engram, and future Flowstate tooling

Normative terms **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are used as requirements.

---

## 1. Executive summary

The Zutfen Agentic Development Contract is a vendor-neutral, machine-readable contract for governing AI-assisted software work from authorization through merge.

It externalizes the semantics that are otherwise repeatedly reconstructed from prompts:

- what work was authorized;
- which repository state the work began from;
- which exact commit contains the implementation;
- which exact commit was tested;
- which evidence supports each completion claim;
- which exact commit was independently reviewed;
- which findings remain unresolved;
- which human accepted the result or its residual risk;
- whether the live repository state still matches the approved state.

The contract does not attempt to make language models deterministic. It treats models as probabilistic workers that may interpret, propose, implement, and review. Deterministic software validates structure, identity, ancestry, evidence, policy, and state transitions. A human remains the final product and merge authority.

The governing principle is:

> **Models propose and interpret. Tools observe. Validators constrain. Evidence proves. Humans authorize.**

---

## 2. Problem statement

The current multi-agent workflow already separates planning, execution, testing, independent review, and human merge decisions. However, a large portion of the workflow contract remains encoded in prose, conventions, and accumulated shared context.

Terms such as the following have precise operational meanings but are not yet represented by one canonical machine-readable model:

- expected work-start SHA;
- actual work-start SHA;
- implementation head;
- certified code SHA;
- evidence carrier commit;
- exact-head CI;
- synthetic merge verification;
- mandatory versus advisory lanes;
- unresolved blocker;
- stale review;
- external merge observed;
- merge-worthy;
- landed;
- completion report;
- correction packet.

This creates predictable failure modes:

1. An executor reports success for a different commit than the current PR head.
2. CI passes, but it tested a stale or synthetic ref that is not identified correctly.
3. Evidence is committed after tests, changing the PR head and invalidating “exact-head” claims.
4. A review is accurate when written but stale after a subsequent fix.
5. Multiple agents agree on an interpretation that was never encoded as policy.
6. A fresh agent session reconstructs terminology differently from earlier sessions.
7. Engram retains an observation as durable context even after the live external fact changes.
8. An agent claims that a PR is merged, a key is revoked, or CI is green without consulting the authoritative live system.
9. A PR modifies the policy or CI logic that is supposed to validate that same PR.
10. A completion report is treated as proof rather than as an executor-authored claim.

ZADC addresses these failures by defining typed artifacts, identities, authority boundaries, state derivation rules, and executable invariants shared by every participant.

---

## 3. Goals

ZADC v0.1 MUST:

1. Define a canonical lifecycle for authorized agentic software work.
2. Define machine-readable artifacts for work authorization, completion claims, verification evidence, independent review, and human decisions.
3. Bind every material claim to an exact repository subject and provenance source.
4. Distinguish reported claims, observed facts, verified facts, human judgments, and live mutable state.
5. Support exact-commit, pull-request-head, and synthetic-merge verification.
6. Model evidence-only descendant commits without silently weakening exact-head guarantees.
7. Support cross-repository dependency pins, including Portal-to-Core style contracts.
8. Prevent an implementation or review agent from self-authorizing a merge.
9. Permit deterministic policy evaluation locally and in CI.
10. Preserve human override authority through explicit, auditable exception records.
11. Remain independent of any one model vendor, agent framework, CI provider, or programming language.
12. Produce both machine-readable results and concise human-readable summaries.

---

## 4. Non-goals for v0.1

ZADC v0.1 does not attempt to:

- replace Git, GitHub, CI, issue trackers, or Engram;
- define product-domain ontologies for Engram, Ruinstead, Starbeast Sanctuary, or Engram Portal;
- prove that tests are sufficient or that product intent is correct;
- allow an AI agent to become the final merge authority;
- require RDF, OWL, SHACL, a graph database, or a policy-engine service;
- standardize every possible software-development methodology;
- provide a web UI;
- provide cryptographic artifact signing in the initial slice;
- autonomously merge pull requests;
- treat stored historical observations as substitutes for live source reconciliation.

A graph projection, SHACL validation, signed attestations, and Flowstate UI MAY be added after the core contract is proven useful.

---

## 5. Design principles

### 5.1 Externalized semantics

A model MUST NOT be the sole location where the meaning of workflow states, evidence requirements, or merge conditions exists.

### 5.2 Exact subjects

Every implementation, verification, review, and decision artifact MUST identify the exact commit or ref it concerns.

### 5.3 Claims are not facts

An agent-authored completion report is evidence of what the agent claims, not proof that the claim is true.

### 5.4 Live systems remain authoritative

Git, GitHub, the CI provider, the deployment target, the billing provider, or another designated source remains authoritative for mutable external state. Engram may retain timestamped observations of that state but MUST NOT silently convert them into timeless facts.

### 5.5 Human authority is explicit

Only a trusted human identity MAY issue a merge-approval or risk-acceptance decision. Human authority MAY be delegated, but the delegation itself MUST be explicit and auditable.

### 5.6 Policy is versioned and pinned

Every validation result MUST identify the contract version and policy version used. A PR MUST NOT be able to weaken the policy that validates itself without an explicit trusted-policy-change path.

### 5.7 Evidence is portable

Evidence MUST be addressable by stable identifiers and content hashes so that another agent or human can independently inspect the same inputs.

### 5.8 Models are replaceable

Hermes, Codex, Claude, ChatGPT, or another model MAY fill planning, execution, or review roles without changing the contract semantics.

### 5.9 State is derived, not self-declared

No artifact may simply declare a slice “verified,” “approved,” or “merged.” Those states are derived from valid artifacts and live reconciled facts.

### 5.10 Fail closed on authority, fail explicit on availability

When authoritative evidence is unavailable, the result MUST be `INCONCLUSIVE` or `BLOCKED`, not silently `PASS`.

---

## 6. Actors and trust boundaries

| Actor | Permitted responsibilities | Not authoritative for |
|---|---|---|
| Human product owner | Product intent, scope authorization, risk acceptance, final merge decision | Mechanical test execution unless separately evidenced |
| Planning agent | Interpret intent, draft packets, identify risks and acceptance criteria | Live repository state, final authorization |
| Execution agent | Modify code, run tools, emit completion claims and local evidence | Its own correctness, merge approval |
| Review agent | Adversarial inspection, semantic review, finding generation | Mechanical CI truth, final merge approval |
| CI system | Execute pinned workflows, produce run results and artifacts | Product intent, review judgment |
| Git/GitHub adapter | Resolve commits, ancestry, PR state, checks, merge state | Product correctness |
| Validator | Enforce schema, referential integrity, policy, and state rules | Human risk acceptance |
| Engram | Retain typed context, observations, provenance, decisions, and relationships | Current mutable external state unless freshly reconciled |
| Flowstate or UI | Present derived state and workflow controls | Underlying truth absent validated sources |

An actor identity MUST include an actor type and stable identifier. Agent identities SHOULD additionally include model, provider, agent framework, and run identifier. Identity fields supplied only by an untrusted agent MUST be treated as claims until bound by a trusted runtime or adapter.

---

## 7. Source-of-truth matrix

| Fact | Authoritative source |
|---|---|
| Commit existence, tree, parentage, ancestry, and diff | Git object database |
| Current PR head, base, draft/open/merged state, merge SHA | GitHub or configured SCM provider |
| CI run status, tested SHA/ref, workflow identity, artifacts | CI provider |
| Deployed runtime behavior | Designated deployment target and its authenticated observation tooling |
| Authorized product intent and accepted risk | Human decision record |
| Contract semantics | Pinned ZADC schema and policy version |
| Historical context, prior observations, and provenance | Engram or another ledger, with timestamps and source references |

A cached or recalled value MUST NOT be presented as current unless its freshness policy is satisfied and the authoritative source is either queried or explicitly unavailable.

---

## 8. Core entity model

ZADC v0.1 defines the following entities.

### 8.1 Project

A product or bounded program of work, such as Engram, Engram Portal, Ruinstead, or Starbeast Sanctuary.

### 8.2 Repository

A source repository identified by provider, owner, name, and immutable repository ID where available.

### 8.3 Slice definition

A durable description of a bounded workstream, such as `ENG-PORTAL-RECEIPTS-001A`.

### 8.4 Slice instance

One authorized execution attempt of a slice definition. Re-runs and correction passes receive distinct slice-instance or run identifiers while retaining lineage to the parent slice.

### 8.5 Packet

The authoritative, human-approved work contract presented to an execution agent.

### 8.6 Agent run

A bounded execution by Hermes, Codex, or another worker against one packet.

### 8.7 Commit reference

An immutable Git commit identity plus its semantic role, such as work start, implementation subject, verification subject, review subject, or merge candidate.

### 8.8 Verification run

A local or CI execution that tests an exact subject under a defined environment and policy.

### 8.9 Evidence artifact

A log, manifest, report, binary, screenshot, trace, or other content-addressed proof produced by a verification run or observation tool.

### 8.10 Review

An independent evaluation of an exact subject, packet, evidence bundle, and known findings.

### 8.11 Finding

A review issue with severity, status, location, rationale, and resolution evidence.

### 8.12 Decision record

A trusted human decision to request changes, approve, reject, merge, accept risk, or supersede prior authorization.

### 8.13 Policy

A versioned set of deterministic requirements governing artifacts, evidence, review independence, freshness, and state transitions.

### 8.14 Observation

A timestamped statement derived from a named source, such as “GitHub reported PR #10 head SHA X at time T.” An observation is not automatically a timeless fact.

### 8.15 Workflow bundle

The canonical aggregate for one slice instance. It links the authorized packet, agent runs, completion reports, certification manifests, reviews, findings, human decisions, live observations, and current derived state. Tools SHOULD accept a workflow bundle as the normal day-to-day unit so operators do not have to manually assemble disconnected artifacts.

### 8.16 Rendered view

A purpose-specific projection of a canonical artifact or workflow bundle for a human, Hermes, Codex, Claude, CI, or another consumer. A rendered view is not authoritative and MUST carry the canonical artifact identifier and digest from which it was produced. Different renderings MAY optimize format and instructions for different consumers but MUST NOT alter requirements or authority semantics.

---

## 9. Canonical identifiers

Every artifact MUST carry stable identifiers.

Recommended forms:

```text
project_id          zutfen:project:engram-portal
repository_id       github:Zutfen-LLC/engram-portal
slice_id            ENG-PORTAL-RECEIPTS-001A
slice_instance_id   ENG-PORTAL-RECEIPTS-001A-FIX1
packet_id           urn:uuid:<uuid>
run_id              urn:uuid:<uuid>
verification_id     urn:uuid:<uuid>
review_id           urn:uuid:<uuid>
decision_id         urn:uuid:<uuid>
artifact_id         urn:uuid:<uuid>
policy_id           zutfen:zadc-policy:standard@0.1.0
```

Human-friendly slice identifiers MUST NOT substitute for globally unique artifact and run identifiers.

---

## 10. Common artifact envelope

Every ZADC artifact MUST include a common envelope.

```json
{
  "schema": "https://schemas.zutfen.com/zadc/0.1/artifact.schema.json",
  "contract_version": "0.1.0",
  "artifact_type": "packet",
  "artifact_id": "urn:uuid:...",
  "created_at": "2026-07-30T23:00:00Z",
  "producer": {
    "actor_type": "human|agent|ci|validator|service",
    "actor_id": "...",
    "run_id": "urn:uuid:...",
    "model": "optional",
    "provider": "optional"
  },
  "project_id": "zutfen:project:...",
  "slice_id": "...",
  "slice_instance_id": "...",
  "policy": {
    "policy_id": "zutfen:zadc-policy:standard@0.1.0",
    "policy_source_sha": "<trusted commit SHA>",
    "policy_digest": "sha256:..."
  },
  "provenance": {
    "parent_artifact_ids": [],
    "content_digest": "sha256:..."
  }
}
```

Timestamps MUST be UTC RFC 3339. Content digests MUST be computed over a canonical serialization that excludes the digest field itself.

---

## 11. Required artifact types

### 11.1 Work packet

The packet is the authoritative work authorization.

Required content:

```yaml
artifact_type: packet
authorization:
  authorized_by: <trusted human actor ID>
  authorized_at: <timestamp>
  expires_at: <optional timestamp>
repository:
  provider: github
  owner: Zutfen-LLC
  name: <repo>
  pull_request: <optional number>
work_start:
  expected_sha: <40-char SHA>
  mismatch_policy: abort | reconcile_with_record
intent:
  problem_statement: <text>
  desired_outcome: <text>
scope:
  allowed_paths: []
  prohibited_paths: []
  allowed_operations: []
  prohibited_operations: []
requirements:
  - requirement_id: REQ-1
    statement: <normative requirement>
    acceptance_criteria: []
dependency_pins:
  - repository: github:Zutfen-LLC/engram
    sha: <40-char SHA>
    cleanliness_required: true
verification:
  mandatory_lanes: []
  advisory_lanes: []
  exact_subject_policy: final_pr_head | certified_code_with_evidence_tail
  synthetic_merge_required: false
review:
  independent_review_required: true
  minimum_severity_blocking: blocker
stop_conditions: []
deliverables: []
completion_report_requirements: []
```

The packet MUST be immutable after authorization. A substantive change creates a new packet revision with a new artifact ID and explicit `supersedes` relationship.

### 11.2 Completion report

The completion report is produced by the execution agent. It records claims and local observations but does not confer verified status.

Required content:

```yaml
artifact_type: completion_report
packet_id: <authorized packet ID>
run_id: <agent run ID>
work_start:
  expected_sha: <from packet>
  actual_sha: <observed SHA>
  match: true | false
repository_state:
  base_sha: <SHA>
  implementation_sha: <SHA>
  pr_head_sha_observed: <SHA>
  branch: <name>
changes:
  commits: []
  files_changed: []
  dependency_pins_resolved: []
verification_claims:
  commands_run: []
  local_results: []
deviations: []
known_limitations: []
open_issues: []
executor_recommendation: green_for_review | red | blocked | inconclusive
```

All statements in this artifact default to epistemic status `AGENT_REPORTED` unless supported by separately addressable evidence.

### 11.3 Certification manifest

The certification manifest is produced by trusted CI or a trusted local verifier. It binds test results and evidence to exact subjects.

Required content:

```yaml
artifact_type: certification_manifest
packet_id: <packet ID>
run_id: <verification run ID>
subject:
  repository: github:owner/name
  subject_kind: commit | pr_head | synthetic_merge | merge_commit
  subject_sha: <exact tested SHA>
  base_sha: <optional SHA>
  head_sha: <optional SHA>
  synthetic_merge_sha: <optional SHA>
environment:
  runner_identity: <trusted runner ID>
  os: <value>
  architecture: <value>
  toolchain: []
  container_digests: []
policy:
  policy_id: <ID>
  policy_digest: <digest>
lanes:
  - lane_id: <stable ID>
    classification: mandatory | advisory
    conclusion: pass | fail | skipped | cancelled | timed_out | unavailable
    started_at: <timestamp>
    completed_at: <timestamp>
    command_or_workflow: <identifier>
    evidence_refs: []
evidence:
  - artifact_id: <ID>
    media_type: <type>
    digest: sha256:...
    location: <trusted URI or provider reference>
result: pass | fail | inconclusive
```

A manifest MUST NOT report `pass` unless every mandatory lane required by the pinned packet and policy passed or was explicitly waived by a prior trusted decision that permits the waiver.

### 11.4 Review report

The review report is produced by a reviewer that is independent under the active policy.

Required content:

```yaml
artifact_type: review_report
packet_id: <packet ID>
review_id: <review ID>
reviewer:
  actor_id: <ID>
  actor_type: human | agent
  model: <optional>
independence:
  executor_actor_id: <ID>
  satisfied: true | false
subject:
  repository: github:owner/name
  review_subject_sha: <exact SHA>
  packet_digest: <digest>
  certification_manifest_ids: []
inputs_reviewed:
  diffs: []
  files: []
  evidence_artifacts: []
findings:
  - finding_id: <stable ID>
    severity: blocker | major | minor | note
    status: open | resolved | accepted_risk | invalid | superseded
    location: <file/range/artifact>
    statement: <issue>
    rationale: <why it matters>
    resolution_refs: []
limitations: []
reviewer_recommendation: green_for_merge | green_for_review | red | blocked | inconclusive
```

A reviewer recommendation is a judgment, not a merge authorization.

### 11.5 Human decision record

The decision record is the only artifact that can authorize a merge or accept unresolved risk.

Required content:

```yaml
artifact_type: decision_record
decision_id: <ID>
decided_by:
  actor_type: human
  actor_id: <trusted human identity>
decided_at: <timestamp>
subject:
  repository: github:owner/name
  pull_request: <number>
  decision_subject_sha: <exact SHA>
  current_pr_head_sha_observed: <SHA>
  review_report_ids: []
  certification_manifest_ids: []
decision: request_changes | approve_for_merge | reject | accept_risk | supersede
accepted_risks:
  - finding_id: <ID>
    rationale: <required>
    scope: <required>
    expires_at: <optional>
conditions: []
rationale: <text>
```

A decision record MUST be bound to a trusted human identity by the system that stores or validates it. An agent-supplied `actor_type: human` field is insufficient.

### 11.6 Workflow bundle

The workflow bundle is the canonical transport and status unit for a slice instance. It MUST reference artifacts by stable ID and digest, MUST preserve lineage and supersession, and MAY embed artifacts for portable offline validation.

Required content includes:

```yaml
artifact_type: workflow_bundle
bundle_id: <ID>
slice_instance_id: <ID>
packet_ref: <artifact ID + digest>
agent_run_refs: []
completion_report_refs: []
certification_manifest_refs: []
review_report_refs: []
decision_record_refs: []
observation_refs: []
derived_state:
  state: <derived state>
  blockers: []
  stale_artifacts: []
  next_admissible_actions: []
```

A bundle MUST NOT override the contents of referenced artifacts. Its `derived_state` is reproducible output from a pinned validator and policy, not an operator-authored assertion.

---

## 12. Epistemic status model

Every material claim SHOULD use one of the following statuses:

| Status | Meaning |
|---|---|
| `PROPOSED` | A possibility or plan not yet executed |
| `AGENT_REPORTED` | Asserted by a planning, execution, or review agent |
| `LOCALLY_OBSERVED` | Observed by a local tool with captured output |
| `CI_OBSERVED` | Reported by a trusted CI run |
| `LIVE_SOURCE_OBSERVED` | Freshly read from the authoritative external system |
| `INDEPENDENTLY_REPRODUCED` | Reproduced by a distinct trusted run or reviewer |
| `VERIFIED` | Satisfies the active evidence and policy rules |
| `CONTRADICTED` | Conflicts with stronger or newer evidence |
| `STALE` | Was valid or observed but exceeds freshness policy |
| `SUPERSEDED` | Replaced by a newer authoritative artifact or decision |

A claim MUST NOT be upgraded merely because multiple language models repeat it. Upgrades require evidence or human judgment defined by policy.

---

## 13. Commit and subject semantics

ZADC distinguishes the following commit roles:

- `expected_work_start_sha`: SHA authorized by the packet.
- `actual_work_start_sha`: SHA observed when execution begins.
- `implementation_sha`: last commit containing implementation-relevant changes for the run.
- `verification_subject_sha`: exact commit tested by a verification run.
- `review_subject_sha`: exact commit reviewed.
- `decision_subject_sha`: exact commit approved or rejected by the human.
- `pr_head_sha_observed`: PR head reported by the live SCM at a timestamp.
- `synthetic_merge_sha`: merge result generated by the SCM or trusted tooling for base-plus-head testing.
- `merge_commit_sha`: actual merge commit reported by the SCM after merge.
- `evidence_carrier_sha`: optional descendant commit that carries only evidence metadata.

### 13.1 Standard exact-head policy

Under `final_pr_head`, the following MUST be equal at decision time:

```text
verification_subject_sha
review_subject_sha
decision_subject_sha
current live PR head SHA
```

If synthetic-merge verification is required, the manifest MUST additionally identify the current base SHA, current head SHA, and exact synthetic merge SHA.

### 13.2 Evidence-only tail policy

The `certified_code_with_evidence_tail` policy MAY permit the live PR head to be a descendant of the certified code SHA only when all of the following are true:

1. Every intervening commit is explicitly classified as evidence-only.
2. Every changed path is allowed by a trusted evidence-only path policy.
3. No workflow, build configuration, dependency lock, source, test, generated runtime asset, executable documentation, or policy file is changed.
4. The validator recomputes the entire intervening diff from Git rather than trusting an agent report.
5. An integrity lane runs against the final PR head and verifies the evidence-only classification.
6. The review report identifies both the certified code SHA and final evidence carrier SHA.
7. The decision record approves the current final PR head, not merely the earlier code SHA.

The default v0.1 recommendation is to store dynamic evidence outside the implementation branch in CI artifacts, GitHub checks, or Engram. Evidence-carrier commits are supported for existing workflows but are not the preferred default.

---

## 14. Deterministic invariants

The validator MUST enforce at least the following invariants.

### INV-001: Packet authorization

Execution cannot enter an authorized state without a valid packet bound to a trusted human authorization.

### INV-002: Work-start identity

`actual_work_start_sha` MUST equal `expected_work_start_sha` unless the packet explicitly permits reconciliation and a reconciliation record enumerates all intervening commits and their disposition.

### INV-003: Packet immutability

The packet digest consumed by the executor, verifier, reviewer, and decision-maker MUST match the authorized packet digest.

### INV-004: Repository identity

All artifacts in a lifecycle MUST refer to the same immutable repository identity, not merely a matching display name.

### INV-005: Ancestry

The implementation subject MUST be the expected work start or a descendant of it. Unrelated histories are a blocker.

### INV-006: Dependency pins

Every required cross-repository dependency pin MUST resolve to the packet-specified SHA. A dirty or substituted dependency is a blocker when cleanliness is required.

### INV-007: Verification binding

Every mandatory verification result MUST identify the exact subject SHA and trusted workflow or command identity.

### INV-008: Mandatory-lane satisfaction

All mandatory lanes MUST pass. Missing, cancelled, skipped, unavailable, stale, or unbound mandatory lanes produce `FAIL` or `INCONCLUSIVE` according to policy.

### INV-009: Evidence integrity

Every referenced evidence artifact MUST exist, match its declared content digest, and be retrievable by the validator or explicitly marked unavailable. Missing evidence cannot yield `VERIFIED`.

### INV-010: Policy trust

Validation policy MUST be loaded from a trusted source and pinned by digest. A PR that changes its own validator, policy, or required workflows MUST be evaluated by a trusted bootstrap policy from outside the untrusted change.

### INV-011: Review freshness

A review MUST concern the current decision subject. A new implementation-relevant commit invalidates prior review approval unless the policy permits and verifies a non-semantic tail.

### INV-012: Review independence

The review actor or run MUST satisfy the active independence policy. The executor run cannot certify itself as independently reviewed.

### INV-013: Finding closure

No open finding at or above the policy’s blocking threshold may remain at approval time unless a trusted human decision explicitly accepts the risk.

### INV-014: No agent authorization

No agent, model, executor, reviewer, CI job, or validator may issue a human merge authorization.

### INV-015: Live reconciliation

Before `APPROVED_FOR_MERGE` is derived, the validator MUST freshly query the live SCM for PR head, base, open/draft status, mergeability state where available, and required checks.

### INV-016: Decision freshness

A human decision becomes stale when the live PR head changes, a blocking finding is reopened, a mandatory check regresses, or the packet is superseded.

### INV-017: Merge observation

`MERGED` may be derived only from a live SCM observation. An executor or reviewer statement that a PR was merged is insufficient.

### INV-018: Approved-subject containment

The actual merged result MUST contain the approved subject according to the repository’s merge strategy and policy. Unexpected substitution or rewritten content is a blocker for certification.

### INV-019: No secret material

Artifacts MUST NOT contain credentials, raw tokens, private keys, session cookies, production DSNs, or unrestricted environment dumps.

### INV-020: Temporal provenance

Every external observation MUST include an observation timestamp and source identity. Mutable facts exceeding their freshness window MUST be marked `STALE`.

---

## 15. Derived lifecycle state

Lifecycle state is computed from artifacts and live facts; it is not directly set by an agent.

| Derived state | Minimum conditions |
|---|---|
| `PLANNED` | Draft packet exists |
| `AUTHORIZED` | Packet valid and trusted human authorization present |
| `EXECUTING` | Agent run references authorized packet and work-start check is valid |
| `IMPLEMENTATION_REPORTED` | Completion report exists for the run |
| `MECHANICALLY_VERIFIED` | Certification manifest passes all mandatory lanes for the current subject |
| `INDEPENDENTLY_REVIEWED` | Fresh independent review exists for the current subject |
| `APPROVED_FOR_MERGE` | Fresh human approval exists; all policy invariants pass |
| `MERGED` | Live SCM reports merge and approved-subject containment passes |
| `BLOCKED` | One or more blocking invariants fail or required authority is unavailable |
| `REJECTED` | Trusted human rejection exists |
| `SUPERSEDED` | A newer packet, run, review, or decision explicitly supersedes the lifecycle |

The validator SHOULD also return orthogonal flags, including:

- `has_open_blockers`;
- `review_stale`;
- `verification_stale`;
- `live_reconciliation_unavailable`;
- `policy_changed_in_subject`;
- `evidence_incomplete`;
- `human_decision_required`.

---

## 16. Policy profiles

The contract defines semantics. Project policy defines required assurance.

A policy document SHOULD include:

```yaml
policy_id: zutfen:zadc-policy:standard@0.1.0
contract_version: 0.1.0
risk_class: prototype | standard | security_sensitive
work_start:
  mismatch_policy: abort
verification:
  exact_subject_policy: final_pr_head
  synthetic_merge_required: false
  mandatory_lanes: []
review:
  independence_rule: distinct_run
  blocking_threshold: blocker
  distinct_model_provider_required: false
freshness:
  scm_observation_seconds: 300
  ci_observation_seconds: 900
  review_invalidated_by_new_commit: true
human_authority:
  approval_required: true
  accepted_risk_allowed: true
trusted_sources:
  policy_source_repository: <repo>
  policy_source_sha: <SHA>
evidence_only_paths:
  enabled: false
  allowlist: []
```

Suggested profiles:

- `prototype`: lower-cost checks, but still exact subject binding and human authority.
- `standard`: mandatory CI, independent review, live reconciliation, and explicit approval.
- `security_sensitive`: trusted bootstrap validation, stricter reviewer independence, expanded evidence, and restricted waiver policy.

---

## 17. Validator architecture

ZADC SHOULD be implemented first as a small Python package and CLI using Pydantic models with generated JSON Schemas.

Suggested package and command names:

```text
distribution: zutfen-zadc
import: zadc
command: zadc
```

### 17.1 Validation phases

1. **Schema validation** — types, required fields, enum values, timestamps, identifiers.
2. **Referential integrity** — artifact links, packet/run lineage, digest matching.
3. **Git validation** — commit existence, ancestry, tree and diff inspection, evidence-only classification.
4. **Provider reconciliation** — GitHub PR state, CI runs, current head/base, merge state.
5. **Policy evaluation** — mandatory lanes, freshness, review independence, blockers, exceptions.
6. **State derivation** — current lifecycle state, flags, blockers, and next admissible transitions.

### 17.2 Initial CLI surface

```text
zadc validate <artifact-or-bundle>
zadc validate-packet <packet.json>
zadc validate-run <completion-report.json>
zadc validate-evidence <certification-manifest.json>
zadc validate-review <review-report.json>
zadc reconcile-git --repo <path> --bundle <bundle.json>
zadc reconcile-github --repo <owner/name> --pr <number> --bundle <bundle.json>
zadc derive-state <bundle.json>
zadc render-summary <bundle.json>
zadc schema export --output <directory>
```

### 17.3 Exit codes

```text
0  valid and policy PASS
2  schema or artifact-integrity failure
3  policy FAIL / blocking invariant
4  INCONCLUSIVE due to missing evidence
5  authoritative source unavailable
6  authorization failure
```

Offline validation MAY verify schema, digests, and local Git state, but MUST NOT yield `APPROVED_FOR_MERGE` or `MERGED` without fresh authoritative reconciliation.

---

## 18. Storage and repository layout

The canonical schemas and validator SHOULD live in a dedicated, versioned repository or package independent of any product repository.

A consuming repository MAY use:

```text
.zadc/
  project.yaml
  contract.yaml
  policies/
    standard.yaml
  packets/
    <slice-instance-id>.packet.json
  templates/
    completion-report.template.json
    review-report.template.json
```

Dynamic completion reports, CI evidence, and review artifacts SHOULD default to trusted external storage such as:

- CI artifacts;
- GitHub check-run output;
- GitHub issue or PR attachments with immutable digests;
- Engram’s provenance ledger;
- a future Flowstate artifact store.

Dynamic evidence SHOULD NOT normally be committed to the implementation branch. Where existing certification workflows require evidence commits, the evidence-only tail policy applies.

---

## 19. Agent integrations

### 19.0 Canonical artifacts and rendered views

The canonical packet and workflow bundle are the source artifacts. Human prompts and agent-specific instructions are rendered views. Hermes, Codex, Claude, and human renderings MAY differ in presentation, tool guidance, and verbosity, but every rendering MUST include the canonical artifact ID and digest and MUST be reproducibly generated from the same source.

The normal operator path SHOULD be:

```text
discuss -> authorize packet -> render for executor -> ingest completion ->
certify exact subject -> render review bundle -> ingest review ->
human decision or authenticated merge -> reconcile live state
```

Operators SHOULD NOT be required to hand-author JSON artifacts, digests, decision records, or lifecycle transitions. Authenticated actions in Flowstate, GitHub, or another trusted coordinator MAY generate the corresponding canonical records.

### 19.1 Hermes

Hermes SHOULD receive the authorized packet as a file or structured payload rather than only prose. It MAY render the packet into a compact prompt, but the packet digest MUST remain available.

Hermes MUST emit a completion report and MUST NOT emit a human decision record. Tooling SHOULD capture actual work-start SHA, final SHA, changed files, command results, and produced artifacts independently where possible.

### 19.2 Codex

Codex SHOULD consume the same packet model and produce the same completion-report format. Bounded correction packets SHOULD use `supersedes`, `parent_run_id`, and explicit expected-head identity rather than relying on conversational continuity.

### 19.3 Claude

Claude or another review model SHOULD receive:

- the packet;
- the exact subject diff;
- the completion report;
- the certification manifest;
- referenced evidence;
- prior findings and their claimed resolutions.

It SHOULD emit only a review report. A review recommendation MUST remain distinct from a human decision.

### 19.4 ChatGPT planning and coordination

Planning systems SHOULD generate packets from human intent, but packet authorization MUST be bound to a trusted human action. Planning systems MAY generate correction packets from review findings, preserving artifact lineage and exact-head requirements.

### 19.5 AGENTS.md

`AGENTS.md` SHOULD be a human-readable projection of the canonical policy and local repository rules. Rules that materially affect admissible state transitions MUST also exist in machine-enforceable policy or CI. A consistency check SHOULD detect divergence between generated guidance and pinned policy.

### 19.6 Authenticated human-action capture

A trusted coordinator MAY create a human decision record from an authenticated user action rather than requiring manual artifact authoring. Supported examples include a Flowstate approval, a GitHub review approval, a GitHub merge performed by an authorized human, or an authenticated coordinator command. The generated record MUST bind the human identity, timestamp, exact decision subject, source system, and source event identifier.

An observed human GitHub merge MAY serve as the merge authorization and merge observation when policy permits, provided the approved-subject containment and freshness invariants pass.

---

## 20. GitHub and CI integration

A GitHub adapter SHOULD:

1. resolve immutable repository identity;
2. fetch current PR head and base SHAs;
3. distinguish PR-head and synthetic-merge refs;
4. enumerate required and observed check runs;
5. bind workflow runs to exact SHAs;
6. observe draft/open/closed/merged state;
7. retrieve merge commit SHA;
8. verify approved-subject containment;
9. record timestamps for every live observation.

CI workflows SHOULD produce a certification manifest as a final artifact. The manifest SHOULD be generated by a trusted action or pinned tool version after all lanes finish, not handwritten by the execution agent.

A PR that modifies validation workflows, ZADC policy, or the validator itself MUST receive a bootstrap evaluation using the trusted version from the base branch or another immutable trusted source.

---

## 21. Engram integration

Engram SHOULD retain ZADC artifacts and relationships as typed, provenance-aware records.

Recommended relationships include:

```text
Packet AUTHORIZES SliceInstance
AgentRun EXECUTES Packet
CompletionReport REPORTS AgentRun
AgentRun PRODUCES Commit
CertificationManifest VERIFIES Commit
EvidenceArtifact SUPPORTS CertificationManifest
ReviewReport REVIEWS Commit
Finding BLOCKS Decision
DecisionRecord AUTHORIZES PullRequest
Observation OBSERVES ExternalState
Artifact SUPERSEDES Artifact
```

Engram SHOULD retain mutable external facts as timestamped observations:

```text
“GitHub reported PR #10 head = 7446755... at 2026-07-28T...”
```

It MUST NOT reinterpret that historical observation as current without reconciliation.

Engram’s profile, principal, and scope controls SHOULD determine which agents can read packets, evidence, reviews, product decisions, or security-sensitive observations. Agent membership and skill access MAY later be expressed against the same identities.

---

## 22. Flowstate integration

A future Flowstate layer SHOULD consume the derived contract graph rather than inventing its own lifecycle semantics.

It may present:

- current slice state;
- exact subject identities;
- stale evidence or review warnings;
- open findings;
- admissible next actions;
- human approval controls;
- cross-agent handoff history;
- provenance and evidence links.

Flowstate controls MUST invoke trusted adapters and validators. UI state alone is not authoritative.

---

## 23. Security considerations

1. **Policy substitution:** Policy and schema digests must be pinned to trusted sources.
2. **Self-modifying CI:** Validation changes require bootstrap validation from outside the subject change.
3. **Identity spoofing:** Agent-provided actor types are untrusted until bound by platform identity.
4. **Evidence tampering:** All evidence requires content hashes and trusted location metadata.
5. **Secret leakage:** Environment captures and logs require allowlisting and redaction.
6. **Artifact replay:** Artifacts must include repository, subject, packet, policy, and timestamp bindings.
7. **Stale approval:** Any subject-changing commit invalidates prior approval by default.
8. **Cross-repo substitution:** Dependency pins must be resolved and recorded exactly.
9. **Runner trust:** Self-hosted runner identity and relevant environment must be recorded; policy may distinguish trusted and untrusted runners.
10. **Prompt injection in repository content:** Review and execution agents must treat repository text as untrusted input unless the packet or policy delegates authority to it.

Cryptographic signatures and supply-chain attestations are deferred but the artifact envelope SHOULD reserve optional signature fields.

---

## 24. Human override and exceptions

Humans retain authority to accept risk, but overrides MUST be explicit.

A valid accepted-risk decision MUST include:

- the exact finding or invariant being overridden;
- the exact decision subject SHA;
- a rationale;
- the scope of the exception;
- any conditions or expiry;
- the trusted human identity;
- the observation time.

A broad statement such as “merge anyway” is insufficient for machine-derived `APPROVED_FOR_MERGE` unless converted into a valid decision record.

Policy MAY prohibit waivers for selected invariants, such as repository identity mismatch, unknown decision subject, or untrusted human identity.

---

## 25. Human-readable status output

The validator SHOULD emit concise output suitable for PR comments and agent handoffs.

Example:

```text
ZADC RESULT: BLOCKED
Slice: ENG-PORTAL-RECEIPTS-001A-FIX1
Packet: sha256:...
Current PR head: 7446755d3e610b932d47043965542b34379a7300
Verified subject: 7446755d3e610b932d47043965542b34379a7300
Reviewed subject: 7446755d3e610b932d47043965542b34379a7300
Mandatory lanes: 5/5 PASS
Open blockers: 1
  - ZADC-INV-006: Core dependency pin does not provide the required profile-bound credential path.
Human approval: absent
Next admissible action: correction packet or explicit human risk decision
```

The summary MUST distinguish verified facts from agent recommendations.

---

## 26. v0.1 acceptance criteria

The first production-usable ZADC release is complete when all of the following are demonstrated.

### AC-01: Typed artifact validation

Valid packet, completion, certification, review, and decision artifacts pass generated JSON Schema and Pydantic validation. Invalid fixtures fail with stable machine-readable error codes.

### AC-02: Work-start mismatch rejection

A run whose actual work-start SHA differs from the packet’s expected SHA is blocked unless an allowed reconciliation artifact exists.

### AC-03: Exact-subject enforcement

Certification or review against a stale SHA cannot produce `APPROVED_FOR_MERGE` when the current PR head differs.

### AC-04: Evidence-only tail enforcement

An allowed evidence-only descendant is accepted only when the Git-computed diff is confined to trusted paths and the final-head integrity lane passes. A source, test, workflow, lockfile, or policy change in the tail is rejected.

### AC-05: Mandatory-lane enforcement

Any missing or failing mandatory lane blocks mechanical verification.

### AC-06: Review freshness

A review becomes stale after an implementation-relevant commit and must be renewed.

### AC-07: Finding closure

An open blocking finding prevents approval unless a valid human accepted-risk decision references it.

### AC-08: Human authority

No agent-authored artifact can independently produce `APPROVED_FOR_MERGE`.

### AC-09: Live GitHub reconciliation

The validator can reconcile a real PR’s current head, base, checks, draft state, and merge state, with observations timestamped and source-bound.

### AC-10: Cross-repository pinning

A Portal-style run can prove the exact Core SHA used and block certification when the pin differs or the dependency worktree is dirty under a cleanliness-required policy.

### AC-11: Trusted-policy bootstrap

A PR that modifies ZADC policy or CI validation is evaluated using the pinned trusted policy from outside the subject change.

### AC-12: Human-readable rendering

A single command produces a concise status report identifying state, exact SHAs, passed lanes, blockers, stale artifacts, and next admissible action.

### AC-13: Secret safety

Fixture and integration tests prove that common token, key, DSN, and cookie patterns are redacted or rejected from artifacts.

### AC-14: Agent portability

At least one Hermes run and one Codex run consume the same packet schema and emit valid completion reports. At least one Claude review emits a valid review report against the same lifecycle.

### AC-15: Engram provenance pilot

A complete lifecycle can be stored and recalled from Engram with artifact identities, relationships, timestamps, and epistemic states preserved without treating historical GitHub observations as current facts.

---

## 27. Recommended implementation slices

### ZADC-000 — Universal repository bootstrap

Deliver:

- the public `Zutfen-LLC/zadc` repository;
- Python distribution `zutfen-zadc`, import package `zadc`, and CLI `zadc`;
- Apache-2.0 licensing and open-source governance;
- minimal installable package and CLI version/help smoke path;
- `uv`-managed development environment, strict linting, typing, tests, and package build verification;
- immutable-action-pinned GitHub Actions CI with least privilege;
- contribution, security, release, architecture, roadmap, and agent guidance;
- documented bootstrap trust exception and future self-validation rule;
- no artifact model or provider integration yet.

### ZADC-001A — Canonical artifacts and rendering

Deliver:

- Pydantic models for the required artifacts and workflow bundle;
- generated JSON Schemas;
- canonical serialization and digesting;
- fixture suite;
- static validation CLI;
- generic human-readable renderer;
- Hermes, Codex, and Claude rendering interfaces sufficient to prove that multiple views retain the same packet digest.

No GitHub, Engram, or live-provider integration in this slice.

### ZADC-001B — Workflow bundles and derived lifecycle

Deliver:

- bundle assembly and replay;
- referential integrity and lineage;
- finding and correction linkage;
- freshness and supersession semantics;
- deterministic lifecycle derivation;
- blockers and next-admissible-action summaries.

### ZADC-001C — Git subject and evidence validation

Deliver:

- immutable repository identity;
- commit existence and ancestry;
- work-start validation;
- changed-file computation;
- evidence-only tail classification;
- cross-repository pin validation;
- exact-subject state derivation.

### ZADC-001D — GitHub and GitHub Actions reconciliation

Deliver:

- PR head/base/draft/merge-state observations;
- check-run and workflow binding;
- synthetic merge modeling;
- live freshness rules;
- trusted-policy bootstrap checks;
- authenticated GitHub human-action capture.

### ZADC-001E — Review, correction, and human-decision workflow

Deliver:

- structured findings and resolution evidence;
- correction packet generation from open findings;
- review invalidation after head changes;
- human approval, rejection, and accepted-risk records;
- policy-controlled external merge observation.

### ZADC-001F — First live project dogfood

Deliver:

- a parallel, non-authoritative ZADC integration in Engram Portal;
- exact Portal/Core dependency-pin proof;
- canonical packet rendered for at least two agent roles;
- CI certification, independent review, correction lineage, and human merge observation;
- documented false-positive, false-negative, and operator-friction findings.

### ZADC-002 — Engram provenance integration

Deliver:

- artifact storage and retrieval;
- relationship graph;
- epistemic status mapping;
- live-versus-historical observation safeguards;
- profile and principal access rules.

### ZADC-003 — Flowstate orchestration integration

Deliver:

- derived lifecycle API;
- admissible-action API;
- blockers and freshness API;
- authenticated human decision submission;
- UI-independent state contract.

---

## 28. Pilot recommendation

The first end-to-end pilot SHOULD run against the next bounded Engram Portal slice because it exercises cross-repository Core pins, security-sensitive service contracts, exact-head CI, completion and correction packets, independent review, and live GitHub reconciliation.

The second pilot SHOULD run against Ruinstead to add a materially different evidence model: self-hosted GPU execution, rendered versus headless behavior, evidence manifests, and source-commit versus evidence-carrier distinctions.

Both pilots SHOULD preserve the existing human/Hermes-or-Codex/reviewer workflow, with ZADC operating as a parallel validator. ZADC should become authoritative only after it correctly detects known failure cases without generating false green results or unacceptable operator burden.

---

## 29. Decisions deferred beyond v0.1

The following are intentionally deferred:

- RDF/OWL/SHACL representation and graph inference;
- cryptographic signatures and Sigstore-style attestations;
- organization-wide policy service;
- autonomous scheduling or agent dispatch;
- automated merge execution;
- generalized product-domain ontologies;
- economic routing between frontier and lower-cost models;
- formal verification of workflow policy;
- retention and deletion policy for large evidence artifacts.

The v0.1 artifact model SHOULD remain compatible with later graph projection by using stable identifiers and explicit typed relationships.

---

## 30. Final design position

ZADC is not another agent and not another layer of prompt prose. It is the shared semantic and evidentiary contract within which agents operate.

Hermes and Codex may implement. Claude and other models may review. ChatGPT may plan and coordinate. CI may execute deterministic checks. GitHub may expose live repository state. Engram may preserve provenance and continuity. Flowstate may present and orchestrate the lifecycle.

None of those components individually decides what the workflow means.

That meaning belongs in a versioned external contract, and consequential state changes remain bound to deterministic evidence and explicit human authority.
