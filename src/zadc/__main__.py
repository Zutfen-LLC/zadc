"""Allow ``python -m zadc`` as a parity alias for ``zadc``."""

from zadc.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
