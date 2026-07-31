# Bootstrap Trust Model

## The seed exception

ZADC-000 creates a new repository (`Zutfen-LLC/zadc`) where none previously
existed. The bootstrap seed commit (`chore: initialize ZADC repository`) is
committed directly to `main` and pushed. This is the **only** permitted
direct-to-main commit in the repository's lifecycle.

Rationale: A new repository requires an initial commit to establish the
default branch. No prior state exists to branch from. Once the seed is
pushed, all subsequent work flows through pull requests on feature branches.

## Manual trust bootstrap for the initial release

The initial ZADC release (when it occurs) will require a **manual trust
bootstrap**. Because there is no prior trusted ZADC release to validate
candidate changes, the human project owner must:

1. Manually review the initial codebase and its commit history.
2. Verify the repository identity, license, and structure match the
   contract.
3. Verify the authoritative design document digest matches the pinned
   SHA-256.
4. Manually approve the initial release.

This is analogous to verifying a root of trust before it can sign anything.

## Future requirement: trusted-release validation

Once a ZADC release exists and is trusted, candidate ZADC changes **must**
be validated by the latest trusted release and its base policy — not only
by candidate code in the same PR. This prevents a PR from weakening the
policy that validates itself (the self-validation problem documented in
the authoritative design, Section 2, failure mode 9).

The trusted-release validation path is deferred to a future slice and is
not implemented in ZADC-000.
