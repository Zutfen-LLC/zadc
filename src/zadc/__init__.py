"""ZADC — Zutfen Agentic Development Contract.

A minimal, installable Python package scaffold. No protocol functionality
(artifacts, schemas, validators, lifecycle, adapters, or integrations) is
implemented in this bootstrap slice.
"""

from importlib.metadata import PackageNotFoundError, version


def get_version() -> str:
    """Return the installed package version via importlib.metadata.

    This is the single runtime version source. No hard-coded ``__version__``
    constant is duplicated.
    """
    try:
        return version("zutfen-zadc")
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"


__all__ = ["get_version"]
