"""Path helpers for installed peripheralyzer resources."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parent


def package_templates_root() -> Path:
    return Path(str(files("peripheralyzer").joinpath("templates")))
