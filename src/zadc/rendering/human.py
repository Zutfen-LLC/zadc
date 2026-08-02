"""The human-readable Markdown renderer (A3A-07).

Produces a deterministic, non-authoritative Markdown projection of any of the
eight canonical ZADC artifacts. The output is deliberately structured so that
no source-controlled prose can alter the surrounding document structure:

- A fixed, renderer-authored header carries the non-authoritative notice,
  render metadata, and the verified source identity/producer/provenance/
  policy fields as labeled inline-code values. Every displayed source value
  uses a single-line JSON string escape before a backtick-run-aware fence is
  selected. Pipes, headings, HTML, links, line breaks, and other Markdown
  content cannot escape into the document structure.
- The complete canonical JSON of the source artifact is rendered inside a
  single dynamically-fenced code block. The fence length is chosen strictly
  longer than the longest run of backticks anywhere in that JSON, so
  arbitrary source prose containing one-to-five backticks or triple-backtick
  fences remains data, never surrounding Markdown structure.

The canonical JSON block also guarantees complete, untruncated,
unredacted, unnormalized, ordering-preserving reproduction of every source
body field (lists/tuples render as JSON arrays in their original order, and
keys are recursively sorted for hash-order independence).

This renderer never calls the clock, never mutates its source, and never
seals, repairs, normalizes, or reinterprets the source artifact. It is
invoked only after :func:`zadc.rendering.render_artifact` has verified the
source content digest.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Literal, cast

from zadc.canonical import canonical_json_text
from zadc.models.artifact_union import ZadcArtifact
from zadc.rendering.models import RENDERED_VIEW_VERSION, RendererReference
from zadc.types import MediaType


def _max_backtick_run(text: str) -> int:
    """Return the length of the longest run of consecutive backticks in ``text``."""
    longest = 0
    current = 0
    for ch in text:
        if ch == "`":
            current += 1
            if current > longest:
                longest = current
        else:
            current = 0
    return longest


def _inline_code(value: str) -> str:
    """Render ``value`` as escaped, single-line Markdown inline code.

    First, encode the value as a JSON string and remove the outer quotes. This
    makes line breaks and control characters visible escape sequences. Then,
    use a backtick fence one tick longer than the longest backtick run in the
    escaped value. Add one space of padding when the escaped value starts or
    ends with a backtick. This keeps the inline-code span unambiguous.
    """
    escaped = _escape_summary_value(value)
    run = _max_backtick_run(escaped)
    fence = "`" * (run + 1)
    pad = " " if escaped and (escaped[0] == "`" or escaped[-1] == "`") else ""
    return f"{fence}{pad}{escaped}{pad}{fence}"


def _escape_summary_value(value: str) -> str:
    """Return a reversible, single-line JSON string escape without outer quotes."""
    return json.dumps(value, ensure_ascii=False)[1:-1]


def _code_fence_for(text: str) -> str:
    """Return a Markdown code-fence (>= 3 backticks) strictly longer than any
    backtick run in ``text``, so the block cannot be closed by source content."""
    return "`" * max(3, _max_backtick_run(text) + 1)


def _kv(label: str, value: str) -> str:
    """Format one labeled inline-code list item."""
    return f"- **{label}:** {_inline_code(value)}"


def _format_optional(value: str | None) -> str:
    return _inline_code(value) if value is not None else "(none)"


_HUMAN_RENDERER_REFERENCE = RendererReference(
    renderer_id="zadc-human-markdown",
    renderer_version=RENDERED_VIEW_VERSION,
)

_NON_AUTHORITATIVE_NOTICE = """# NON-AUTHORITATIVE RENDERED VIEW

> **WARNING — this is a non-authoritative projection.** This document is NOT a
> canonical ZADC artifact. It carries no independent artifact identity, content
> digest, producer, authority, approval, or lifecycle state of its own. Every
> value below is quoted from the single source artifact identified in the
> "Source artifact identity" section. Rendering does not authenticate
> identities, reconcile live state, evaluate policy, derive lifecycle state,
> accept risk, or authorize any merge. All authority resides with the
> canonical source artifact identified below."""

_CAVEATS: dict[str, str] = {
    "review_report": (
        "> **Caveat — reviewer judgment, not authorization.** The "
        "`reviewer_recommendation` value is a recorded reviewer judgment quoted "
        "from the source. Rendering does not authenticate the reviewer, prove "
        "reviewer independence, or treat the recorded recommendation as a merge "
        "decision."
    ),
    "decision_record": (
        "> **Caveat — recorded decision claim.** The `decision` and `decided_by` "
        "values are recorded decision claims quoted from the source. Rendering "
        "does not authenticate the human identity, reconcile live repository "
        "state, or treat the recorded decision as an authorized merge outcome."
    ),
    "workflow_bundle": (
        "> **Caveat — recorded snapshot, not recomputed.** The `derived_state` "
        "value is a recorded snapshot quoted from the source. Rendering did not "
        "recompute the recorded state, blockers, stale references, or admissible "
        "actions from the referenced artifacts."
    ),
}


@dataclass(frozen=True, slots=True)
class HumanMarkdownRenderer:
    """Deterministic human-readable Markdown renderer for all eight artifacts.

    Identity: consumer ``human``, media type ``text/markdown``,
    ``zadc-human-markdown @ 0.1.0``. Stateless — output depends only on the
    verified source artifact and the renderer version.

    The identity fields (``consumer``, ``media_type``, ``renderer``) are
    :func:`~dataclasses.field` declarations with ``init=False`` and fixed
    defaults. The generated constructor therefore takes no arguments, so the
    documented identity can be neither replaced at construction nor changed
    afterward, and the render metadata displayed in the Markdown projection
    always matches the enclosing view.
    """

    consumer: Literal["human"] = field(default="human", init=False)
    media_type: MediaType = field(default="text/markdown", init=False)
    renderer: RendererReference = field(default=_HUMAN_RENDERER_REFERENCE, init=False)

    def render_content(self, artifact: ZadcArtifact) -> str:
        """Return the deterministic Markdown projection of ``artifact``.

        ``artifact`` MUST already be content-digest verified by
        :func:`zadc.rendering.render_artifact`; this method does not re-verify
        and never mutates its input.
        """
        producer = artifact.producer
        # render_artifact verifies the artifact before invoking this renderer,
        # so content_digest is guaranteed present and matches the recomputed
        # digest. The cast records that precondition for the type checker.
        digest_text = cast("str", artifact.provenance.content_digest)
        caveat = _CAVEATS.get(artifact.artifact_type, "")

        body_json = canonical_json_text(artifact)
        fence = _code_fence_for(body_json)

        lines: list[str] = [_NON_AUTHORITATIVE_NOTICE, "", "## Render metadata", ""]
        lines.append(_kv("Consumer", self.consumer))
        lines.append(
            _kv("Renderer", f"{self.renderer.renderer_id} @ {self.renderer.renderer_version}")
        )
        lines.append(_kv("Media type", self.media_type))
        lines.append("")
        lines.append("## Source artifact identity")
        lines.append("")
        lines.append(_kv("Artifact ID", artifact.artifact_id))
        lines.append(_kv("Content digest", digest_text))
        lines.append(_kv("Artifact type", artifact.artifact_type))
        lines.append(_kv("Contract version", artifact.contract_version))
        lines.append(_kv("Project ID", artifact.project_id))
        lines.append(_kv("Slice ID", artifact.slice_id))
        lines.append(_kv("Slice instance ID", artifact.slice_instance_id))
        lines.append(_kv("Created at", artifact.created_at.isoformat().replace("+00:00", "Z")))
        lines.append("")
        lines.append("## Source producer")
        lines.append("")
        lines.append(_kv("Actor type", producer.actor_type))
        lines.append(_kv("Actor ID", producer.actor_id))
        lines.append(f"- **Run ID:** {_format_optional(producer.run_id)}")
        lines.append(f"- **Model:** {_format_optional(producer.model)}")
        lines.append(f"- **Provider:** {_format_optional(producer.provider)}")
        lines.append("")
        lines.append("## Source provenance")
        lines.append("")
        parent_ids = artifact.provenance.parent_artifact_ids
        if parent_ids:
            lines.append("- **Parent artifact IDs:**")
            for parent_id in parent_ids:
                lines.append(f"  - {_inline_code(parent_id)}")
        else:
            lines.append("- **Parent artifact IDs:** (none)")
        lines.append(_kv("Content digest", digest_text))
        lines.append("")
        lines.append("## Source policy")
        lines.append("")
        lines.append(_kv("Policy ID", artifact.policy.policy_id))
        lines.append(_kv("Policy source SHA", artifact.policy.policy_source_sha))
        lines.append(_kv("Policy digest", artifact.policy.policy_digest))
        if caveat:
            lines.append("")
            lines.append(caveat)
        lines.append("")
        lines.append("## Source artifact body (canonical JSON)")
        lines.append("")
        lines.append(
            "The complete, unmodified canonical JSON of the source artifact follows. "
            "All source-controlled prose is data inside this block."
        )
        lines.append("")
        lines.append(f"{fence}json")
        lines.append(body_json)
        lines.append(f"{fence}")
        lines.append("")
        return "\n".join(lines)


__all__ = ["HumanMarkdownRenderer"]
