"""A2A-05: the CompletionReport artifact and its supporting models."""

import pytest
from pydantic import ValidationError

from tests.a2a_factories import SHA_A, SHA_B, SHA_C, build_completion_report
from zadc.models.completion_report import (
    Changes,
    DependencyPinResolution,
    Reconciliation,
    ReconciliationCommit,
    WorkStartObservation,
)


class TestCompletionReportConstruction:
    def test_valid(self) -> None:
        report = build_completion_report()
        assert report.artifact_type == "completion_report"
        assert report.executor_recommendation == "green_for_review"

    def test_rejects_wrong_artifact_type(self) -> None:
        with pytest.raises(ValidationError):
            build_completion_report(artifact_type="packet")

    def test_rejects_extra_top_level_field(self) -> None:
        with pytest.raises(ValidationError):
            build_completion_report(unexpected="nope")


class TestWorkStartObservationInvariants:
    def test_match_true_requires_equal_shas(self) -> None:
        obs = WorkStartObservation(expected_sha=SHA_A, actual_sha=SHA_A, match=True)
        assert obs.reconciliation is None

    def test_rejects_match_true_with_different_shas(self) -> None:
        with pytest.raises(ValidationError, match="match"):
            WorkStartObservation(expected_sha=SHA_A, actual_sha=SHA_B, match=True)

    def test_rejects_match_false_with_equal_shas(self) -> None:
        with pytest.raises(ValidationError, match="match"):
            WorkStartObservation(expected_sha=SHA_A, actual_sha=SHA_A, match=False)

    def test_match_false_requires_reconciliation(self) -> None:
        with pytest.raises(ValidationError, match="reconciliation"):
            WorkStartObservation(expected_sha=SHA_A, actual_sha=SHA_B, match=False)

    def test_match_false_with_reconciliation_is_valid(self) -> None:
        obs = WorkStartObservation(
            expected_sha=SHA_A,
            actual_sha=SHA_B,
            match=False,
            reconciliation=Reconciliation(
                intervening_commits=(
                    ReconciliationCommit(
                        sha=SHA_C, disposition="benign hotfix", rationale="urgent security patch"
                    ),
                )
            ),
        )
        assert obs.reconciliation is not None
        assert len(obs.reconciliation.intervening_commits) == 1

    def test_rejects_match_true_with_reconciliation(self) -> None:
        with pytest.raises(ValidationError, match="reconciliation"):
            WorkStartObservation(
                expected_sha=SHA_A,
                actual_sha=SHA_A,
                match=True,
                reconciliation=Reconciliation(
                    intervening_commits=(
                        ReconciliationCommit(sha=SHA_C, disposition="x", rationale="y"),
                    )
                ),
            )


class TestReconciliationInvariants:
    def test_rejects_empty_intervening_commits(self) -> None:
        with pytest.raises(ValidationError):
            Reconciliation(intervening_commits=())

    def test_rejects_duplicate_intervening_commit_shas(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            Reconciliation(
                intervening_commits=(
                    ReconciliationCommit(
                        sha=SHA_C, disposition="benign hotfix", rationale="urgent patch"
                    ),
                    ReconciliationCommit(
                        sha=SHA_C, disposition="evidence-only", rationale="ci log added"
                    ),
                )
            )

    def test_accepts_unique_intervening_commits(self) -> None:
        reconciliation = Reconciliation(
            intervening_commits=(
                ReconciliationCommit(sha=SHA_A, disposition="a", rationale="x"),
                ReconciliationCommit(sha=SHA_C, disposition="b", rationale="y"),
            )
        )
        assert len(reconciliation.intervening_commits) == 2


class TestChangesInvariants:
    def test_valid_unique_commits_and_files(self) -> None:
        changes = Changes(
            commits=(SHA_A, SHA_B),
            files_changed=("a.py", "b.py"),
            dependency_pins_resolved=(),
        )
        assert changes.commits == (SHA_A, SHA_B)

    def test_rejects_duplicate_commits(self) -> None:
        with pytest.raises(ValidationError, match="commits"):
            Changes(commits=(SHA_A, SHA_A), files_changed=(), dependency_pins_resolved=())

    def test_rejects_duplicate_files(self) -> None:
        with pytest.raises(ValidationError, match="files_changed"):
            Changes(
                commits=(),
                files_changed=("a.py", "a.py"),
                dependency_pins_resolved=(),
            )

    def test_dependency_pins_resolved(self) -> None:
        changes = Changes(
            commits=(),
            files_changed=(),
            dependency_pins_resolved=(
                DependencyPinResolution(
                    repository_id="github:Zutfen-LLC/engram", sha=SHA_C, clean=True
                ),
            ),
        )
        assert changes.dependency_pins_resolved[0].clean is True


class TestReconciliationCommit:
    def test_valid(self) -> None:
        commit = ReconciliationCommit(sha=SHA_A, disposition="evidence-only", rationale="ci log")
        assert commit.sha == SHA_A


class TestCompletionReportCanonicalizationDeterminism:
    def test_list_and_tuple_inputs_equivalent(self) -> None:
        r1 = build_completion_report(deviations=[])
        r2 = build_completion_report(deviations=())
        from zadc.canonical import canonical_json_text

        assert canonical_json_text(r1) == canonical_json_text(r2)
