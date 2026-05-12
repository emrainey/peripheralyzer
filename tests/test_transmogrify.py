"""Tests for the transmogrify command."""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import pytest

from peripheralyzer.transmogrify import TransmogrifyCommand


def test_transmogrify_command_exists() -> None:
    """Test that TransmogrifyCommand can be instantiated."""
    command = TransmogrifyCommand()
    assert command is not None


def test_transmogrify_command_name_and_help() -> None:
    """Test command name and help attributes."""
    command = TransmogrifyCommand()
    assert command.name == "transmogrify"
    assert len(command.help) > 0


def test_transmogrify_command_parser_configuration() -> None:
    """Test that TransmogrifyCommand configures parser correctly."""
    command = TransmogrifyCommand()
    parser = argparse.ArgumentParser()
    # Should not raise
    command.configure_parser(parser)


def test_transmogrify_command_parser_has_namespace_args() -> None:
    """Test that parser supports multiple namespace arguments."""
    command = TransmogrifyCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    with tempfile.TemporaryDirectory() as tmpdir:
        args = parser.parse_args([
            "-s", "test.svd",
            "-yr", tmpdir,
            "-ns", "namespace1",
            "-ns", "namespace2",
            "-nm", "name_map.yml",
        ])

        # Should have both namespaces
        assert hasattr(args, "namespace")
        assert isinstance(args.namespace, list)


def test_transmogrify_command_parser_has_optional_args() -> None:
    """Test that parser has all expected optional arguments."""
    command = TransmogrifyCommand()
    parser = argparse.ArgumentParser()
    command.configure_parser(parser)

    # Parser should recognize these flags without error
    help_text = parser.format_help()
    assert "-s" in help_text  # svd file
    assert "-yr" in help_text  # yaml root
    assert "-ns" in help_text  # namespace
    assert "-nm" in help_text  # name map
