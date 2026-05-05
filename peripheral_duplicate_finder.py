#!/usr/bin/env python3
"""Find peripheral YAML definitions that appear structurally duplicated.

This script scans a folder of generated YAML files (for example
out/stm32/f4xx/ymls) and groups peripherals that have the same layout,
register shapes, and sizing information while allowing names to differ
(e.g. I2C1 vs I2C2).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


def to_int(value: Any, default: int = 0) -> int:
    """Convert decimal/hex strings and ints to int, with a safe default."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        return int(text, 0)
    return default


def freeze_enum_signature(enum_data: dict[str, Any]) -> tuple[Any, ...]:
    """Build a canonical enum signature that ignores naming-only differences."""
    symbols = enum_data.get("symbols", [])
    symbol_signature = tuple(
        sorted((to_int(symbol.get("value"), 0),) for symbol in symbols if isinstance(symbol, dict))
    )
    return (
        to_int(enum_data.get("default_depth"), 0),
        str(enum_data.get("type", "")),
        symbol_signature,
    )


def freeze_register_signature(register_data: dict[str, Any]) -> tuple[Any, ...]:
    """Build a canonical register signature independent of register name/file."""
    fields = register_data.get("fields", [])
    field_signature = tuple(
        sorted(
            (
                to_int(field.get("offset"), 0),
                to_int(field.get("count"), 1),
                str(field.get("type", "")),
            )
            for field in fields
            if isinstance(field, dict)
        )
    )

    enums = register_data.get("enums", [])
    enum_signature = []
    for enum in enums:
        if isinstance(enum, dict):
            enum_signature.append(freeze_enum_signature(enum))
    enum_signature_tuple = tuple(sorted(enum_signature))

    return (
        to_int(register_data.get("sizeof"), 0),
        to_int(register_data.get("default_depth"), 0),
        str(register_data.get("default_type", "")),
        field_signature,
        enum_signature_tuple,
    )


def freeze_member_shape(member: dict[str, Any]) -> tuple[Any, ...]:
    """Build a canonical member shape that ignores names/comments/type labels."""
    if member.get("is_union", False):
        union_members = member.get("members", [])
        union_member_shapes = []
        for inner in union_members:
            if isinstance(inner, dict):
                union_member_shapes.append(
                    (
                        to_int(inner.get("offset"), 0),
                        to_int(inner.get("count"), 1),
                        to_int(inner.get("sizeof"), 0),
                    )
                )
        return (
            "union",
            to_int(member.get("offset"), 0),
            to_int(member.get("sizeof"), 0),
            tuple(sorted(union_member_shapes)),
        )

    return (
        "member",
        to_int(member.get("offset"), 0),
        to_int(member.get("count"), 1),
        to_int(member.get("sizeof"), 0),
    )


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@dataclass(frozen=True)
class PeripheralRecord:
    path: Path
    raw_name: str
    name: str
    base: str
    member_count: int
    register_count: int
    signature: tuple[Any, ...]


def load_register_signatures(yaml_dir: Path) -> dict[str, tuple[Any, ...]]:
    """Load signatures for all register_*.yml files in a directory."""
    signatures: dict[str, tuple[Any, ...]] = {}
    for register_path in sorted(yaml_dir.glob("register_*.yml")):
        data = load_yaml(register_path)
        if isinstance(data, dict):
            signatures[register_path.name] = freeze_register_signature(data)
    return signatures


def build_peripheral_signature(
    peripheral: dict[str, Any], register_signatures: dict[str, tuple[Any, ...]]
) -> tuple[Any, ...]:
    members = peripheral.get("members", [])
    member_shapes = tuple(
        sorted(
            freeze_member_shape(member)
            for member in members
            if isinstance(member, dict)
        )
    )

    registers = peripheral.get("registers", [])
    register_counter: Counter[tuple[Any, ...]] = Counter()
    for register_ref in registers:
        if not isinstance(register_ref, str):
            continue
        signature = register_signatures.get(register_ref)
        if signature is not None:
            register_counter[signature] += 1

    register_shapes = tuple(
        sorted((signature, count) for signature, count in register_counter.items())
    )

    return (
        to_int(peripheral.get("sizeof"), 0),
        to_int(peripheral.get("default_depth"), 0),
        str(peripheral.get("default_type", "")),
        member_shapes,
        register_shapes,
    )


def detect_family_name(names: Iterable[str]) -> tuple[str, str]:
    """Find a shared base family name from numbered or lettered instances."""
    normalized = [name for name in names if name]
    if not normalized:
        return "", ""

    digit_stripped = [re.sub(r"\d+$", "", name) for name in normalized]
    if all(a != b for a, b in zip(normalized, digit_stripped, strict=True)):
        first = digit_stripped[0]
        if first and all(name == first for name in digit_stripped):
            return first, f"{first}\\d+"

    letter_stripped = [re.sub(r"[A-Z]$", "", name) for name in normalized]
    if all(a != b for a, b in zip(normalized, letter_stripped, strict=True)):
        first = letter_stripped[0]
        if first and all(name == first for name in letter_stripped):
            return first, f"{first}[A-Z]"

    return "", ""


def extract_family_suffixes(names: Iterable[str], family: str) -> list[str]:
    """Extract sortable instance suffixes for names in a detected family."""
    if not family:
        return []

    pattern = re.compile(rf"^{re.escape(family)}(?P<suffix>\d+|[A-Z])$")
    suffixes: list[str] = []
    for name in names:
        match = pattern.match(name)
        if not match:
            return []
        suffixes.append(match.group("suffix"))

    unique_suffixes = sorted(set(suffixes))
    if all(suffix.isdigit() for suffix in unique_suffixes):
        return sorted(unique_suffixes, key=lambda value: int(value))
    return unique_suffixes


def make_collision_safe_name(
    family: str,
    group: list[PeripheralRecord],
    family_collision_count: int,
) -> str:
    """Create a shared-type suggestion that avoids collisions across groups."""
    if not family:
        return ""

    if family_collision_count <= 1:
        return family

    raw_suffixes = extract_family_suffixes((item.raw_name for item in group), family)
    if raw_suffixes:
        return f"{family}_{'_'.join(raw_suffixes)}"

    display_suffixes = extract_family_suffixes((item.name for item in group), family)
    if display_suffixes:
        return f"{family}_{'_'.join(display_suffixes)}"

    return family


def collect_peripherals(yaml_dir: Path) -> list[PeripheralRecord]:
    register_signatures = load_register_signatures(yaml_dir)
    records: list[PeripheralRecord] = []

    for path in sorted(yaml_dir.glob("peripheral_*.yml")):
        data = load_yaml(path)
        if not isinstance(data, dict):
            continue

        peripheral = data.get("peripheral")
        if not isinstance(peripheral, dict):
            continue

        signature = build_peripheral_signature(peripheral, register_signatures)
        records.append(
            PeripheralRecord(
                path=path,
                raw_name=path.stem.removeprefix("peripheral_"),
                name=str(peripheral.get("name", path.stem.removeprefix("peripheral_"))),
                base=str(peripheral.get("base", "")),
                member_count=len(peripheral.get("members", []) or []),
                register_count=len(peripheral.get("registers", []) or []),
                signature=signature,
            )
        )

    return records


def print_report(records: list[PeripheralRecord], min_group_size: int) -> int:
    grouped: dict[tuple[Any, ...], list[PeripheralRecord]] = defaultdict(list)
    for record in records:
        grouped[record.signature].append(record)

    duplicate_groups = [
        sorted(group, key=lambda item: item.name)
        for group in grouped.values()
        if len(group) >= min_group_size
    ]
    duplicate_groups.sort(key=lambda group: (-len(group), group[0].name))

    if not duplicate_groups:
        print("No duplicated peripheral shapes were found.")
        return 0

    potential_savings = sum(len(group) - 1 for group in duplicate_groups)

    print(f"Scanned peripherals: {len(records)}")
    print(f"Duplicate shape groups: {len(duplicate_groups)}")
    print(f"Potential type reductions: {potential_savings}")
    print()

    group_families: list[tuple[str, str]] = []
    for group in duplicate_groups:
        names = [item.name for item in group]
        raw_names = [item.raw_name for item in group]
        family, pattern = detect_family_name(raw_names)
        if not family:
            family, pattern = detect_family_name(names)
        group_families.append((family, pattern))

    family_counts: Counter[str] = Counter(
        family for family, _ in group_families if family
    )

    for index, group in enumerate(duplicate_groups, start=1):
        family, pattern = group_families[index - 1]
        suggested_name = make_collision_safe_name(
            family, group, family_counts.get(family, 0)
        )

        if family:
            if suggested_name != family:
                print(
                    f"[{index}] Possible shared type: {family} (pattern: {pattern}) -> Suggested: {suggested_name}"
                )
            else:
                print(
                    f"[{index}] Possible shared type: {family} (pattern: {pattern}) -> Suggested: {suggested_name}"
                )
        else:
            print(
                "[{}] Possible shared type: (no shared numeric/letter-suffix family detected)".format(
                    index
                )
            )
        print(
            f"    Members: {group[0].member_count}, Registers: {group[0].register_count}, Instances: {len(group)}"
        )
        for item in group:
            print(f"    - {item.name}  base={item.base}  file={item.path.name}")
        print()

    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Find duplicated peripheral YAML definitions that share the same layout "
            "and register structure even when names differ."
        )
    )
    parser.add_argument(
        "yaml_dir",
        type=Path,
        help="Folder containing generated peripheral_*.yml and register_*.yml files.",
    )
    parser.add_argument(
        "--min-group-size",
        type=int,
        default=2,
        help="Minimum number of matching peripherals required to print a group (default: %(default)s).",
    )
    args = parser.parse_args(argv)

    yaml_dir = args.yaml_dir
    if not yaml_dir.exists() or not yaml_dir.is_dir():
        print(f"Path must be an existing directory: {yaml_dir}", file=sys.stderr)
        return 2

    records = collect_peripherals(yaml_dir)
    if not records:
        print(f"No peripheral_*.yml files were found in {yaml_dir}")
        return 1

    return print_report(records, max(2, args.min_group_size))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
