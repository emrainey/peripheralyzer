"""Tests for CLI module and command registry."""
from __future__ import annotations

import argparse

import pytest

from peripheralyzer.cli import CLICommandGroup, PeripheralyzerCLI, default_commands


def test_default_commands_returns_tuple() -> None:
    """Test that default_commands returns a tuple of commands and groups."""
    commands = default_commands()
    assert isinstance(commands, tuple)
    assert len(commands) >= 4  # generate, transmogrify, name-map group, find-duplicates


def test_peripheralyzer_cli_initialization() -> None:
    """Test that PeripheralyzerCLI can be initialized with commands."""
    commands = default_commands()
    cli = PeripheralyzerCLI(commands)
    assert cli.commands == commands


def test_all_subcommands_have_names_and_help() -> None:
    """Test that all commands and groups have names and help text."""
    commands = default_commands()
    for item in commands:
        assert hasattr(item, "name")
        assert hasattr(item, "help")
        assert len(item.name) > 0
        assert len(item.help) > 0


def test_name_map_group_structure() -> None:
    """Test that name-map group is properly structured."""
    commands = default_commands()
    name_map = next((cmd for cmd in commands if isinstance(cmd, CLICommandGroup)), None)

    assert name_map is not None, "name-map group not found"
    assert name_map.name == "name-map"
    assert len(name_map.subcommands) == 4
    assert all(hasattr(cmd, "name") and hasattr(cmd, "help") for cmd in name_map.subcommands.values())


def test_main_help_displays() -> None:
    """Test that main --help displays without crashing."""
    commands = default_commands()
    cli = PeripheralyzerCLI(commands)
    parser = cli.build_parser()

    # Test that --help is recognized and creates help text
    help_text = parser.format_help()
    assert "generate" in help_text
    assert "transmogrify" in help_text
    assert "name-map" in help_text
    assert "find-duplicates" in help_text


def test_generate_command_help() -> None:
    """Test that generate command --help works."""
    commands = default_commands()
    cli = PeripheralyzerCLI(commands)
    parser = cli.build_parser()

    # Parse with generate --help should be captured by argparse
    # We verify the subparser was created correctly
    subparsers_action = None
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_action = action
            break

    assert subparsers_action is not None
    assert "generate" in subparsers_action.choices


def test_name_map_group_help() -> None:
    """Test that name-map group --help displays subcommands."""
    commands = default_commands()
    cli = PeripheralyzerCLI(commands)
    parser = cli.build_parser()

    # Find the name-map subparser
    subparsers_action = None
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_action = action
            break

    assert subparsers_action is not None
    assert "name-map" in subparsers_action.choices

    # Get the name-map subparser
    name_map_subparser = subparsers_action.choices["name-map"]

    # Verify it has subcommands
    has_subparsers = False
    for action in name_map_subparser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            has_subparsers = True
            expected = {"diff", "merge", "verify", "track"}
            actual = set(action.choices.keys())
            assert actual == expected, f"Expected subcommands {expected}, got {actual}"
            break

    assert has_subparsers, "name-map group has no subcommands"


def test_name_map_diff_subcommand_help() -> None:
    """Test that name-map diff subcommand --help works."""
    commands = default_commands()
    cli = PeripheralyzerCLI(commands)
    parser = cli.build_parser()

    # Navigate to name-map subparser
    subparsers_action = None
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_action = action
            break

    assert subparsers_action is not None
    name_map_subparser = subparsers_action.choices["name-map"]

    # Find diff subcommand
    for action in name_map_subparser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            assert "diff" in action.choices
            diff_parser = action.choices["diff"]

            # Verify diff parser has expected arguments
            help_text = diff_parser.format_help()
            assert "left" in help_text or "positional arguments" in help_text
            assert "right" in help_text or "positional arguments" in help_text
            break


def test_all_nested_commands_have_parsers() -> None:
    """Test that all nested commands can generate parsers."""
    commands = default_commands()
    cli = PeripheralyzerCLI(commands)
    parser = cli.build_parser()

    # Verify all top-level commands/groups have valid subparsers
    subparsers_action = None
    for action in parser._subparsers._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers_action = action
            break

    assert subparsers_action is not None

    for name, subparser in subparsers_action.choices.items():
        # Each subparser should be valid and have help
        assert subparser is not None
        help_text = subparser.format_help()
        assert len(help_text) > 0, f"Subparser for '{name}' generated empty help"
