from __future__ import annotations

import argparse
from pathlib import Path

from peripheralyzer.generate import GenerateCommand
from peripheralyzer.paths import package_templates_root


def test_package_templates_root_exists() -> None:
    template_root = package_templates_root()
    assert template_root.exists()
    assert (template_root / "peripheral.hpp.jinja").exists()


def test_generate_defaults_to_packaged_templates() -> None:
    command = GenerateCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)
    args = parser.parse_args([
        "-y",
        "peripheral_test.yml",
        "-t",
        "peripheral.hpp.jinja",
    ])
    assert Path(args.template_root) == package_templates_root()
