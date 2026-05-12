"""Integration tests for the peripheralyzer package."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from peripheralyzer.cli import CLICommandGroup, default_commands


def test_all_commands_registered() -> None:
    """Test that all expected commands and groups are registered."""
    commands = default_commands()
    command_names = [cmd.name if not isinstance(cmd, CLICommandGroup) else cmd.name for cmd in commands]
    expected_commands = [
        "generate",
        "transmogrify",
        "name-map",
        "find-duplicates",
    ]

    # All expected commands should be in the list
    for expected in expected_commands:
        assert expected in command_names, \
            f"Command '{expected}' not found in {command_names}"


def test_name_map_group_has_subcommands() -> None:
    """Test that name-map command group has expected subcommands."""
    from peripheralyzer.cli import CLICommandGroup

    commands = default_commands()
    name_map_group = next((cmd for cmd in commands if isinstance(cmd, CLICommandGroup) and cmd.name == "name-map"), None)

    assert name_map_group is not None, "name-map group not found"
    assert len(name_map_group.subcommands) == 4, f"Expected 4 subcommands, got {len(name_map_group.subcommands)}"

    expected_subcommands = {"diff", "merge", "verify", "track"}
    actual_subcommands = set(name_map_group.subcommands.keys())
    assert actual_subcommands == expected_subcommands, \
        f"Expected subcommands {expected_subcommands}, got {actual_subcommands}"


def test_all_commands_have_required_attributes() -> None:
    """Test that all commands have required attributes."""
    commands = default_commands()

    for item in commands:
        if isinstance(item, CLICommandGroup):
            # Groups have name, help, and subcommands
            assert hasattr(item, "name")
            assert hasattr(item, "help")
            assert hasattr(item, "subcommands")
            # Check that subcommands are valid
            for subcmd in item.subcommands.values():
                assert hasattr(subcmd, "configure_parser"), f"Subcommand missing 'configure_parser' method"
                assert hasattr(subcmd, "run"), f"Subcommand missing 'run' method"
        else:
            # Regular commands have name, help, configure_parser, and run
            assert hasattr(item, "name"), f"Command missing 'name' attribute"
            assert hasattr(item, "help"), f"Command missing 'help' attribute"
            assert hasattr(item, "configure_parser"), f"Command missing 'configure_parser' method"
            assert hasattr(item, "run"), f"Command missing 'run' method"


def test_command_names_are_unique() -> None:
    """Test that all command names are unique (including groups and their subcommands)."""
    commands = default_commands()
    all_names = []

    for item in commands:
        if isinstance(item, CLICommandGroup):
            all_names.append(item.name)
            # Also track subcommand names within groups
            for subcmd in item.subcommands.values():
                all_names.append(f"{item.name}.{subcmd.name}")
        else:
            all_names.append(item.name)

    assert len(all_names) == len(set(all_names)), "Duplicate command names found"


def test_command_help_not_empty() -> None:
    """Test that all commands and groups have non-empty help text."""
    commands = default_commands()

    for item in commands:
        if isinstance(item, CLICommandGroup):
            assert item.help, f"Group '{item.name}' has empty help text"
            assert len(item.help) > 10, f"Group '{item.name}' help text too short: {item.help}"
            # Check subcommands too
            for subcmd in item.subcommands.values():
                assert subcmd.help, f"Subcommand '{subcmd.name}' has empty help text"
                assert len(subcmd.help) > 10, f"Subcommand '{subcmd.name}' help text too short: {subcmd.help}"
        else:
            assert item.help, f"Command '{item.name}' has empty help text"
            assert len(item.help) > 10, f"Command '{item.name}' help text too short: {item.help}"



def test_create_multiple_command_instances() -> None:
    """Test that we can create multiple instances of commands without interference."""
    import argparse
    from peripheralyzer.generate import GenerateCommand
    from peripheralyzer.transmogrify import TransmogrifyCommand

    # Create multiple instances
    gen1 = GenerateCommand()
    gen2 = GenerateCommand()
    trans1 = TransmogrifyCommand()
    trans2 = TransmogrifyCommand()

    # Each should be independent
    assert gen1 is not gen2
    assert trans1 is not trans2
    assert gen1.name == gen2.name
    assert trans1.name == trans2.name

    # Each should be able to configure a parser independently
    parser1 = argparse.ArgumentParser()
    parser2 = argparse.ArgumentParser()
    gen1.configure_parser(parser1)
    gen2.configure_parser(parser2)

    # Both should work
    args1 = parser1.parse_args(["-y", "test.yml", "-t", "test.jinja"])
    args2 = parser2.parse_args(["-y", "other.yml", "-t", "other.jinja"])

    assert args1.yaml == ["test.yml"]
    assert args2.yaml == ["other.yml"]


def test_package_import_structure() -> None:
    """Test that package structure allows clean imports."""
    # These should all work without errors
    from peripheralyzer import cli
    from peripheralyzer.paths import package_templates_root
    from peripheralyzer.generate import GenerateCommand
    from peripheralyzer.transmogrify import TransmogrifyCommand

    # Verify key items are accessible
    assert callable(cli.main)
    assert callable(package_templates_root)
    assert GenerateCommand is not None
    assert TransmogrifyCommand is not None
