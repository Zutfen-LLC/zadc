"""Command-line interface for ZADC.

Implements only ``--help`` and ``--version`` with deterministic exit code 0.
Unknown arguments fail with a nonzero argparse-style usage error.
"""

from __future__ import annotations

import argparse
import sys

from zadc import get_version


def build_parser() -> argparse.ArgumentParser:
    """Build the ZADC argument parser."""
    parser = argparse.ArgumentParser(
        prog="zadc",
        description=(
            "ZADC — Zutfen Agentic Development Contract. "
            "An open contract and tooling for evidence-backed, "
            "human-authorized agentic software development."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"zadc {get_version()}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns exit code 0 on success, nonzero on error."""
    parser = build_parser()
    parser.parse_args(argv)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
