# ZADC

**Status: PRE-ALPHA / BOOTSTRAP**

> No stable release is available. This project is in early bootstrap and must
> not be used for production purposes.

---

ZADC (Zutfen Agentic Development Contract) is a vendor-neutral,
machine-readable contract for governing evidence-backed, human-authorized
AI-assisted software development.

This repository contains the open contract specification and a Python
foundation with concrete canonical artifact models: **Packet**,
**CompletionReport**, **CertificationManifest**, **EvidenceArtifact**,
**Observation**, **ReviewReport**, **DecisionRecord**, and
**WorkflowBundle** — each strict, frozen, deterministically canonicalized,
digest-sealed, and backed by a generated JSON Schema — plus a global,
`artifact_type`-discriminated `ZadcArtifact` union covering all eight. See
[docs/api-a1-foundation.md](docs/api-a1-foundation.md),
[docs/api-a2a-execution-evidence-artifacts.md](docs/api-a2a-execution-evidence-artifacts.md),
[docs/api-a2b1-review-decision-artifacts.md](docs/api-a2b1-review-decision-artifacts.md),
and
[docs/api-a2b2-workflow-bundle-union.md](docs/api-a2b2-workflow-bundle-union.md).

`ReviewReport` and `DecisionRecord` preserve the distinction between
reviewer judgment and authenticated human authority: a structurally valid
artifact does not, by itself, authenticate reviewer or human-decider
identity, prove reviewer independence, or confer merge authorization.
`WorkflowBundle` links the other seven artifacts by stable ID and content
digest and carries a recorded `derived_state` snapshot; it does not
recompute, trust-bind, or verify that snapshot, and does not verify that a
typed reference collection's members resolve to a sealed artifact of the
claimed type.

Lifecycle state derivation, policy evaluation, Git/GitHub reconciliation,
consumer-specific renderers, and Engram/Flowstate integration are **not yet
implemented** and are intentionally deferred to subsequent work slices.

## Identity

| Item | Value |
|---|---|
| GitHub repository | `Zutfen-LLC/zadc` |
| Python distribution | `zutfen-zadc` |
| Python import | `zadc` |
| CLI command | `zadc` |
| License | Apache-2.0 |

## Development setup

Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Zutfen-LLC/zadc.git
cd zadc
uv sync --extra dev
```

## Checks

```sh
make check          # ruff + mypy + pytest
make workflow-lint  # actionlint + zizmor
make build          # wheel + sdist
make package-smoke  # install wheel in clean venv and smoke-test
```

## Architecture

The authoritative design input is committed at
[docs/architecture/ZUTFEN-AGENTIC-DEV-CONTRACT-v0.1.md](docs/architecture/ZUTFEN-AGENTIC-DEV-CONTRACT-v0.1.md).

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the full roadmap including
ZADC-000 through ZADC-003.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). One slice, one PR. Conventional
commits required.

## Security

See [SECURITY.md](SECURITY.md). Report vulnerabilities through GitHub
private vulnerability reporting.

## License

Apache-2.0. See [LICENSE.md](LICENSE.md).

---

> ZADC does not currently validate workflows. No claim is made that this
> repository provides functional artifact validation, lifecycle derivation,
> or merge governance.
