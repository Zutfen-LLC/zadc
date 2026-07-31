# Contributing to ZADC

Thank you for your interest in contributing to ZADC. This project is in
early bootstrap (PRE-ALPHA).

## Local setup

Requires Python >= 3.11 and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Zutfen-LLC/zadc.git
cd zadc
uv sync --extra dev
```

## Development workflow

1. Create a feature branch from `main`.
2. Make your changes. Keep scope tight — one slice, one PR.
3. Run all checks locally:

```sh
make check
make workflow-lint
make build
make package-smoke
```

4. Commit using [conventional commits](https://www.conventionalcommits.org/):
   - `feat:` new feature
   - `fix:` bug fix
   - `chore:` maintenance/tooling
   - `docs:` documentation
   - `test:` test changes
   - `refactor:` code restructuring

5. Squash-merge is the expected merge strategy. Keep commits clean.

## Conventions

- **Python >= 3.11**, src layout.
- **Line length**: 100 characters.
- **Formatting**: `ruff format` (run `make format` to auto-format).
- **Linting**: `ruff check` with `E, F, I, UP, B, SIM` rules across `src`, `tests`, and `scripts`.
- **Typing**: `mypy --strict` over `src`, `tests`, and `scripts`.
- **Coverage**: >= 95% package coverage required.

## PR checklist

- [ ] Slice ID and packet/sentinel referenced in the PR body
- [ ] Expected and actual work-start SHAs documented
- [ ] Final head SHA documented
- [ ] All checks pass (`make check`, `make workflow-lint`, `make build`)
- [ ] CI green on the exact final head SHA
- [ ] No secrets or credentials committed
- [ ] No scope deviations beyond the authorized slice
- [ ] PR is explicitly marked unmerged; no merge performed

## Scope discipline

Do not implement functionality outside the authorized slice. ZADC-000 is
repository bootstrap only. ZADC-001A (canonical artifacts and rendering) is
a separate future slice. If you find yourself implementing protocol models,
schemas, validators, adapters, or integrations, stop and report it as a
proposed follow-up.

## Security reporting

See [SECURITY.md](SECURITY.md). Do not publicly disclose vulnerabilities.
Use GitHub's private vulnerability reporting.
