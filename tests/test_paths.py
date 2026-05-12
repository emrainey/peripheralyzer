"""Tests for paths module and resource discovery."""
from __future__ import annotations

from pathlib import Path

from peripheralyzer.paths import package_templates_root


def test_package_templates_root_returns_path() -> None:
    """Test that package_templates_root returns a Path object."""
    root = package_templates_root()
    assert isinstance(root, Path)


def test_package_templates_root_exists() -> None:
    """Test that the template root directory exists."""
    root = package_templates_root()
    assert root.exists(), f"Template root does not exist: {root}"
    assert root.is_dir(), f"Template root is not a directory: {root}"


def test_package_templates_contains_jinja_files() -> None:
    """Test that template directory contains .jinja files."""
    root = package_templates_root()
    jinja_files = list(root.glob("*.jinja"))
    assert len(jinja_files) > 0, f"No .jinja files found in {root}"


def test_package_templates_has_required_templates() -> None:
    """Test that all required template files exist."""
    root = package_templates_root()
    required_templates = [
        "peripheral.hpp.jinja",
        "peripheral.h.jinja",
        "enum.h.jinja",
        "structure.h.jinja",
        "register.h.jinja",
    ]
    for template in required_templates:
        template_path = root / template
        assert template_path.exists(), f"Required template not found: {template}"


def test_package_templates_consistency() -> None:
    """Test that template paths are consistent and accessible."""
    root = package_templates_root()
    # Verify multiple calls return consistent paths
    root2 = package_templates_root()
    assert root == root2, "Inconsistent template root paths"
