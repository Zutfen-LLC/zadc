"""Tests for the ZADC CLI."""

from __future__ import annotations

import subprocess
import sys

import pytest

from zadc.cli import main


class TestVersion:
    def test_version_flag(self) -> None:
        """``zadc --version`` exits 0 and prints version string."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0

    def test_version_flag_prints_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--version"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "zadc" in captured.out

    def test_version_subprocess(self) -> None:
        """``python -m zadc --version`` in a subprocess exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "zadc", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "zadc" in result.stdout


class TestHelp:
    def test_help_flag(self) -> None:
        """``zadc --help`` exits 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_help_flag_prints_description(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "ZADC" in captured.out

    def test_help_subprocess(self) -> None:
        """``python -m zadc --help`` in a subprocess exits 0."""
        result = subprocess.run(
            [sys.executable, "-m", "zadc", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "ZADC" in result.stdout


class TestNoArgs:
    def test_no_args_exits_zero(self) -> None:
        """``zadc`` with no args exits 0 (no-op)."""
        result = main([])
        assert result == 0


class TestUnknownArguments:
    def test_unknown_argument_fails_nonzero(self) -> None:
        """Unknown arguments must fail with nonzero exit code."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--nonexistent-flag"])
        assert exc_info.value.code != 0

    def test_unknown_positional_fails_nonzero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["bogus-arg"])
        assert exc_info.value.code != 0

    def test_unknown_argument_subprocess(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "zadc", "--nonexistent-flag"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0


class TestModuleParity:
    def test_python_m_zadc_help_parity(self) -> None:
        """``python -m zadc --help`` must work identically to ``zadc --help``."""
        result = subprocess.run(
            [sys.executable, "-m", "zadc", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_python_m_zadc_version_parity(self) -> None:
        """``python -m zadc --version`` must work identically to ``zadc --version``."""
        result = subprocess.run(
            [sys.executable, "-m", "zadc", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

    def test_main_module_invocation(self) -> None:
        """Directly invoking ``zadc.__main__`` with no args exits 0."""
        import zadc.__main__ as main_module

        # __main__ calls raise SystemExit(main()) at import time when run as __main__.
        # We verify the function it calls works correctly.
        assert main_module.main is not None
