# Releasing ZADC

## Versioning

ZADC follows [Semantic Versioning](https://semver.org/) (SemVer).

- **MAJOR**: Breaking contract or API changes.
- **MINOR**: Backward-compatible feature additions.
- **PATCH**: Backward-compatible bug fixes.

During pre-alpha development, the version is `0.1.0.dev0`. No stable
release exists yet.

## Git tags

Releases are tagged with a `v` prefix:

```text
v0.1.0
v0.2.0
v1.0.0
```

## Build and check prerequisites

Before creating a release, a trusted human must verify:

1. `make check` passes (ruff, mypy, pytest with coverage).
2. `make workflow-lint` passes (actionlint, zizmor).
3. `make build` produces wheel and sdist.
4. `make package-smoke` passes (clean-venv install + smoke test).
5. CI is green on the exact release commit SHA.
6. The authoritative design document digest is unchanged or explicitly
   updated.
7. `uv.lock` is in sync.

## Trusted human release authority

Only a trusted human identity may create a release. Agents do not publish
releases. The release process is:

1. Human verifies all prerequisites above.
2. Human creates and pushes a `v*` Git tag on the release commit.
3. Human builds the distribution artifacts locally.
4. Human publishes to PyPI using trusted credentials.

## Deferred automation

GitHub Release creation, PyPI publication, package signing, and release
credential management are **explicitly deferred** from the ZADC-000 slice.
No release automation is implemented. Future slices may add trusted
release workflows after the manual trust bootstrap is complete.
