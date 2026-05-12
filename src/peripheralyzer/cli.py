"""Unified command line interface for peripheralyzer."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .generate import GenerateCommand
from .map_diff import MapDiffCommand
from .merge_name_maps import MergeNameMapsCommand
from .peripheral_duplicate_finder import PeripheralDuplicateFinderCommand
from .track_name_map_changes import TrackNameMapChangesCommand
from .transmogrify import TransmogrifyCommand
from .verify_name_map import VerifyNameMapCommand


class CLICommand:
    """Base interface for CLI subcommands."""

    name: str
    help: str

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        raise NotImplementedError

    def run(self, args: argparse.Namespace) -> int:
        raise NotImplementedError


@dataclass(slots=True)
class CLICommandGroup:
    """A group of related CLI commands with a common namespace."""

    name: str
    help: str
    subcommands: dict[str, CLICommand]


@dataclass(slots=True)
class PeripheralyzerCLI:
    commands: Sequence[CLICommand | CLICommandGroup]

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog="peripheralyzer",
            description="Generate code and manage name maps for memory-mapped peripherals.",
        )
        subparsers = parser.add_subparsers(dest="command", required=True)

        for item in self.commands:
            if isinstance(item, CLICommandGroup):
                # Create a subparser group
                group_parser = subparsers.add_parser(
                    item.name,
                    help=item.help,
                )
                group_subparsers = group_parser.add_subparsers(
                    dest="subcommand",
                    required=True,
                )

                # Add subcommands to the group
                for subcommand in item.subcommands.values():
                    sub_parser = group_subparsers.add_parser(
                        subcommand.name,
                        help=subcommand.help,
                    )
                    subcommand.configure_parser(sub_parser)
                    sub_parser.set_defaults(_command=subcommand)
            else:
                # Create a regular subparser
                subparser = subparsers.add_parser(item.name, help=item.help)
                item.configure_parser(subparser)
                subparser.set_defaults(_command=item)

        return parser

    def run(self, argv: Sequence[str] | None = None) -> int:
        parser = self.build_parser()
        args = parser.parse_args(list(argv) if argv is not None else None)
        return int(args._command.run(args))


def default_commands() -> tuple[CLICommand | CLICommandGroup, ...]:
    # Rename the name-map commands to simpler names
    map_diff_cmd = MapDiffCommand()
    map_diff_cmd.name = "diff"

    merge_maps_cmd = MergeNameMapsCommand()
    merge_maps_cmd.name = "merge"

    verify_map_cmd = VerifyNameMapCommand()
    verify_map_cmd.name = "verify"

    track_changes_cmd = TrackNameMapChangesCommand()
    track_changes_cmd.name = "track"

    # Create the name-map command group
    name_map_group = CLICommandGroup(
        name="name-map",
        help="Manage naming maps for peripherals.",
        subcommands={
            "diff": map_diff_cmd,
            "merge": merge_maps_cmd,
            "verify": verify_map_cmd,
            "track": track_changes_cmd,
        },
    )

    return (
        GenerateCommand(),
        TransmogrifyCommand(),
        name_map_group,
        PeripheralDuplicateFinderCommand(),
    )


def main(argv: Iterable[str] | None = None) -> int:
    cli = PeripheralyzerCLI(default_commands())
    return cli.run(list(argv) if argv is not None else None)
