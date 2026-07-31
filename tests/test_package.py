"""Tests for package metadata and importability."""

from __future__ import annotations

import importlib.metadata
from importlib.metadata import PackageNotFoundError

import zadc


class TestImportability:
    def test_zadc_importable(self) -> None:
        """``import zadc`` succeeds."""
        assert zadc is not None

    def test_cli_module_importable(self) -> None:
        """``from zadc.cli import main`` succeeds."""
        from zadc.cli import main

        assert callable(main)


class TestVersion:
    def test_get_version_returns_string(self) -> None:
        result = zadc.get_version()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_version_is_metadata_sourced(self) -> None:
        """``get_version()`` must match ``importlib.metadata.version``."""
        try:
            expected = importlib.metadata.version("zutfen-zadc")
            assert zadc.get_version() == expected
        except PackageNotFoundError:
            assert "unknown" in zadc.get_version().lower()


class TestRuntimeDependencies:
    def test_pydantic_is_only_runtime_dependency(self) -> None:
        """The package must declare exactly one runtime dependency: pydantic v2."""
        metadata = importlib.metadata.metadata("zutfen-zadc")
        requires = metadata.get_all("Requires-Dist") or []
        # Filter out optional (dev) extras; only check unconditional runtime deps
        runtime_requires = [r for r in requires if "extra ==" not in r]
        assert len(runtime_requires) == 1, (
            f"Expected exactly 1 runtime dep (pydantic), found: {runtime_requires}"
        )
        dep = runtime_requires[0]
        assert "pydantic" in dep.lower(), f"Expected pydantic, found: {dep}"

    def test_py_typed_marker_present(self) -> None:
        """``py.typed`` marker must be present for type checking."""
        import importlib.resources

        # The py.typed file should exist in the package
        files = importlib.resources.files("zadc")
        py_typed = files.joinpath("py.typed")
        assert py_typed.is_file()


class TestDistributionMetadata:
    def test_distribution_name(self) -> None:
        """Distribution name must be ``zutfen-zadc``."""
        metadata = importlib.metadata.metadata("zutfen-zadc")
        assert metadata["Name"] == "zutfen-zadc"

    def test_import_name(self) -> None:
        """Import name must be ``zadc``."""
        import zadc

        assert zadc.__name__ == "zadc"

    def test_requires_python(self) -> None:
        """Must require Python >=3.11."""
        metadata = importlib.metadata.metadata("zutfen-zadc")
        assert metadata["Requires-Python"] is not None
        assert ">=3.11" in metadata["Requires-Python"]

    def test_console_script_entry_point(self) -> None:
        """Console script ``zadc`` must map to ``zadc.cli:main``."""
        eps = importlib.metadata.entry_points()
        zadc_eps: list[importlib.metadata.EntryPoint] = list(
            eps.select(group="console_scripts", name="zadc")
        )
        assert len(zadc_eps) == 1
        ep = zadc_eps[0]
        assert ep.value == "zadc.cli:main"
