"""Track before/after changes to a name-map file."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class TrackNameMapChangesOptions:
    name_map: Path
    before: bool
    after: bool
    backup: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "TrackNameMapChangesOptions":
        return cls(
            name_map=Path(args.name_map),
            before=bool(args.before),
            after=bool(args.after),
            backup=bool(args.backup),
        )


class NameMapSnapshotService:
    @staticmethod
    def compute_hash(data: dict[str, Any]) -> str:
        yaml_str = yaml.dump(data, sort_keys=True, default_flow_style=False)
        return hashlib.md5(yaml_str.encode()).hexdigest()

    @staticmethod
    def load_map(filepath: Path) -> dict[str, Any]:
        if not filepath.exists():
            return {}
        with filepath.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        return data or {}

    @staticmethod
    def compare_maps(original: dict[str, Any], modified: dict[str, Any]) -> dict[str, Any]:
        changes: dict[str, Any] = {"added": [], "removed": [], "modified": []}

        for key, modified_value in modified.items():
            if key not in original:
                changes["added"].append(key)
            elif original[key] != modified_value:
                changes["modified"].append(
                    {"key": key, "original": original[key], "new": modified_value}
                )

        for key in original:
            if key not in modified:
                changes["removed"].append(key)

        return changes


class TrackNameMapChangesApp:
    def __init__(self, options: TrackNameMapChangesOptions) -> None:
        self.options = options
        self.service = NameMapSnapshotService()

    def run(self) -> int:
        map_file = self.options.name_map
        snapshot_file = map_file.with_suffix(".snapshot.yml")
        hash_file = map_file.with_suffix(".hash")
        backup_file = map_file.with_suffix(".backup.yml")

        if self.options.before:
            print(f"📸 Creating snapshot before processing: {snapshot_file}")
            data = self.service.load_map(map_file)
            hash_val = self.service.compute_hash(data)

            with snapshot_file.open("w", encoding="utf-8") as handle:
                yaml.dump(data, handle, sort_keys=True, default_flow_style=False)

            with hash_file.open("w", encoding="utf-8") as handle:
                handle.write(hash_val)

            print(f"   Hash: {hash_val}")
            print(f"   Entries: {len(data)}")

            if self.options.backup:
                shutil.copy(map_file, backup_file)
                print(f"✓ Backup created: {backup_file}")
            return 0

        if self.options.after:
            if not snapshot_file.exists():
                print("✗ No snapshot found. Run with --before first.")
                return 1

            print("🔍 Comparing changes after processing...")
            original = self.service.load_map(snapshot_file)
            modified = self.service.load_map(map_file)
            original_hash = hash_file.read_text(encoding="utf-8").strip()
            modified_hash = self.service.compute_hash(modified)

            if original_hash == modified_hash:
                print("✓ No changes detected!")
                return 0

            changes = self.service.compare_maps(original, modified)
            print("\n📊 Change Summary:")
            print(f"   Added:    {len(changes['added'])} entries")
            print(f"   Removed:  {len(changes['removed'])} entries")
            print(f"   Modified: {len(changes['modified'])} entries")

            if changes["added"]:
                print(f"\n➕ Added entries ({len(changes['added'])}):")
                for key in sorted(changes["added"])[:10]:
                    entry = modified[key]
                    print(
                        f"   • {key} → as_type: {entry.get('as_type')}, as_variable: {entry.get('as_variable')}"
                    )
                if len(changes["added"]) > 10:
                    print(f"   ... and {len(changes['added']) - 10} more")

            if changes["removed"]:
                print(f"\n➖ Removed entries ({len(changes['removed'])}):")
                for key in sorted(changes["removed"])[:10]:
                    print(f"   • {key}")
                if len(changes["removed"]) > 10:
                    print(f"   ... and {len(changes['removed']) - 10} more")

            if changes["modified"]:
                print(f"\n✏️  Modified entries ({len(changes['modified'])}):")
                for change in sorted(changes["modified"], key=lambda item: item["key"])[:5]:
                    original_entry = change["original"]
                    new_entry = change["new"]
                    print(f"   • {change['key']}")
                    if original_entry.get("as_type") != new_entry.get("as_type"):
                        print(f"     type: {original_entry.get('as_type')} → {new_entry.get('as_type')}")
                    if original_entry.get("as_variable") != new_entry.get("as_variable"):
                        print(
                            f"     var:  {original_entry.get('as_variable')} → {new_entry.get('as_variable')}"
                        )
                if len(changes["modified"]) > 5:
                    print(f"   ... and {len(changes['modified']) - 5} more")

            print(f"\n💾 To restore from backup: cp {backup_file} {map_file}")
            return 1

        print("✗ Specify either --before or --after.")
        return 2


class TrackNameMapChangesCommand:
    name = "track-name-map-changes"
    help = "Track changes to naming maps during transmogrify processing."

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.help
        parser.add_argument("name_map", help="Path to naming map YAML file")
        parser.add_argument(
            "--before",
            action="store_true",
            help="Save pre-processing snapshot (run before transmogrify)",
        )
        parser.add_argument(
            "--after",
            action="store_true",
            help="Compare after processing (run after transmogrify)",
        )
        parser.add_argument(
            "--backup",
            action="store_true",
            help="Create a backup before processing",
        )

    def run(self, args: argparse.Namespace) -> int:
        return TrackNameMapChangesApp(TrackNameMapChangesOptions.from_namespace(args)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peripheralyzer track-name-map-changes")
    command = TrackNameMapChangesCommand()
    command.configure_parser(parser)
    args = parser.parse_args(argv)
    return command.run(args)
