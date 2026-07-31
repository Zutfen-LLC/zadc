<!--
ZADC Pull Request Template
-->

## Slice

- **Slice ID:** <!-- e.g., ZADC-000 -->
- **Packet/Sentinel:** <!-- packet_id + sentinel from the authorized packet -->

## SHAs

- **Expected work-start SHA:** <!-- pinned expected_work_start_sha from packet -->
- **Actual work-start SHA:** <!-- resolved from the live PR head at work start -->
- **Final head SHA:** <!-- the exact final commit SHA on this branch -->

## Summary

<!-- Brief description of what this PR implements -->

## Scope

<!-- What is in scope? What is explicitly out of scope? -->

## Scope deviations

<!-- Any deviations from the packet. None expected unless noted. -->

## Verification

<!-- Commands run and their results -->

- [ ] `make check` passes
- [ ] `make workflow-lint` passes
- [ ] `make build` passes
- [ ] `make package-smoke` passes
- [ ] CI green on exact final head SHA

## Security impact

<!-- Any security-relevant changes. None expected unless noted. -->

## No merge

This PR is **unmerged**. Auto-merge is **disabled**. This PR is a **draft**
open for human review. No agent has merged or authorized merge.
