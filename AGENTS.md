# Coding Agent Rules — ZADC

## Authority

The authoritative design input is at
`docs/architecture/ZUTFEN-AGENTIC-DEV-CONTRACT-v0.1.md`. Follow it. Do not
paraphrase or silently revise contract semantics.

## Conventions

- **Language**: Python >= 3.11, src layout (`src/zadc/`).
- **Package manager**: `uv`. Lock file is committed (`uv.lock`).
- **Formatting**: `ruff format`, line length 100, LF endings.
- **Linting**: `ruff check` with rules `E, F, I, UP, B, SIM` across `src`, `tests`, and `scripts`.
- **Typing**: `mypy --strict` over `src`, `tests`, and `scripts`. All code is typed.
- **Testing**: `pytest` with coverage. Maintain >= 95% package coverage.
- **Commits**: Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`).

## Workflow Rules

1. **One slice, one PR.** Do not bundle multiple work items.
2. **Exact-SHA reporting.** Every completion claim must reference exact commit SHAs.
3. **No merge.** Agents do not merge. Humans merge.
4. **No secrets.** Never commit secrets, tokens, credentials, or API keys.
5. **No speculative protocol work.** Do not implement ZADC artifact models,
   schemas, validators, lifecycle state, Git/GitHub adapters, Engram
   integration, or Flowstate integration until authorized in a future slice.

## Checks

```sh
make check          # ruff check + ruff format --check + mypy --strict + pytest
make workflow-lint  # actionlint + zizmor
make build          # wheel + sdist
make package-smoke  # clean-venv install + smoke test
```
