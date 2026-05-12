"""Merge newly discovered name-map entries into a main map."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class MergeNameMapsOptions:
    main_map: Path
    new_entries: Path | None
    backup: bool
    dry_run: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "MergeNameMapsOptions":
        return cls(
            main_map=Path(args.main_map),
            new_entries=None if args.new_entries is None else Path(args.new_entries),
            backup=bool(args.backup),
            dry_run=bool(args.dry_run),
        )


class MergeNameMapsService:
    @staticmethod
    def load_map(filepath: Path) -> dict[str, Any]:
        if not filepath.exists():
            raise FileNotFoundError(filepath)
        with filepath.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return data or {}

    @staticmethod
    def merge_maps(main_map: dict[str, Any], new_map: dict[str, Any]) -> dict[str, Any]:
        merged = dict(main_map)
        merged.update(new_map)
        return merged


class MergeNameMapsApp:
    def __init__(self, options: MergeNameMapsOptions) -> None:
        self.options = options
        self.service = MergeNameMapsService()

    def run(self) -> int:
        main_path = self.options.main_map
        new_entries_path = self.options.new_entries or Path(
            str(main_path).replace(".yml", "_new_entries.yml")
        )

        if not new_entries_path.exists():
            print(f"✗ New entries file not found: {new_entries_path}")
            return 1

        print(f"Loading main map: {main_path}")
        main_map = self.service.load_map(main_path)
        print(f"Loading new entries: {new_entries_path}")
        new_map = self.service.load_map(new_entries_path)

        if not new_map:
            print("✓ No new entries to merge")
            return 0

        print("\n📊 Merge Summary:")
        print(f"  Main map entries:  {len(main_map)}")
        print(f"  New entries:       {len(new_map)}")

        conflicts = [key for key in new_map if key in main_map]
        if conflicts:
            print(f"\n⚠️  Found {len(conflicts)} conflicting entries (will be overwritten):")
            for key in sorted(conflicts)[:10]:
                print(f"   • {key}")
            if len(conflicts) > 10:
                print(f"   ... and {len(conflicts) - 10} more")

        if self.options.dry_run:
            print(f"\n(dry-run) Would merge {len(new_map)} entries into {main_path}")
            return 0

        if self.options.backup:
            backup_path = Path(str(main_path).replace(".yml", ".backup.yml"))
            print(f"\n💾 Creating backup: {backup_path}")
            shutil.copy(main_path, backup_path)

        merged_map = self.service.merge_maps(main_map, new_map)
        print(f"\n✓ Merging {len(new_map)} entries into {main_path}...")
        with main_path.open("w", encoding="utf-8") as handle:
            yaml.dump(merged_map, handle, sort_keys=True, default_flow_style=False)

        print(f"✓ Total entries now: {len(merged_map)}")
        print(f"✓ Removing {new_entries_path}")
        new_entries_path.unlink()
        print("\n✓ Merge complete!")
        return 0


class MergeNameMapsCommand:
    name = "merge-name-maps"
    help = "Merge newly discovered naming map entries into the main map."

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.help
        parser.add_argument("main_map", help="Path to the main naming map file")
        parser.add_argument(
            "--new-entries",
            type=str,
            help="Path to new entries file (default: main_map with _new_entries.yml suffix)",
        )
        parser.add_argument(
            "--backup",
            action="store_true",
            help="Create a backup of the main map before merging",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be merged without actually merging",
        )

    def run(self, args: argparse.Namespace) -> int:
        return MergeNameMapsApp(MergeNameMapsOptions.from_namespace(args)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peripheralyzer merge-name-maps")
    command = MergeNameMapsCommand()
    command.configure_parser(parser)
    args = parser.parse_args(argv)
    return command.run(args)
