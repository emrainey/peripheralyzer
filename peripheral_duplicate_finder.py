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
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, NamedTuple

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


class GroupInfo(NamedTuple):
    """All derived facts for one duplicate group, computed once and reused."""
    group: list[PeripheralRecord]
    family: str
    pattern: str
    suggested_name: str


class RepeatAtom(NamedTuple):
    """Canonical representation of one peripheral member for repeat detection."""
    member_shape: tuple[Any, ...]
    register_signature: tuple[Any, ...] | None


class RepeatPattern(NamedTuple):
    """One repeated contiguous block in a peripheral member layout."""
    start_index: int
    block_length: int
    repeats: int
    stride_bytes: int

    @property
    def end_index(self) -> int:
        return self.start_index + (self.block_length * self.repeats) - 1


def to_member_atoms(
    peripheral: dict[str, Any], register_signatures: dict[str, tuple[Any, ...]]
) -> list[RepeatAtom]:
    """Create repeat-detection atoms from members + register references."""

    def freeze_member_pattern(member: dict[str, Any]) -> tuple[Any, ...]:
        """Member shape for repeats, intentionally ignoring absolute offsets."""
        if member.get("is_union", False):
            union_members = member.get("members", [])
            union_member_shapes = []
            for inner in union_members:
                if isinstance(inner, dict):
                    union_member_shapes.append(
                        (
                            to_int(inner.get("count"), 1),
                            to_int(inner.get("sizeof"), 0),
                        )
                    )
            return (
                "union",
                to_int(member.get("sizeof"), 0),
                tuple(sorted(union_member_shapes)),
            )

        return (
            "member",
            to_int(member.get("count"), 1),
            to_int(member.get("sizeof"), 0),
        )

    members = peripheral.get("members", []) or []
    registers = peripheral.get("registers", []) or []
    atoms: list[RepeatAtom] = []
    for index, member in enumerate(members):
        if not isinstance(member, dict):
            continue
        member_shape = freeze_member_pattern(member)
        register_signature: tuple[Any, ...] | None = None
        if index < len(registers):
            register_ref = registers[index]
            if isinstance(register_ref, str):
                register_signature = register_signatures.get(register_ref)
        atoms.append(RepeatAtom(member_shape=member_shape, register_signature=register_signature))
    return atoms


def _pattern_coverage(pattern: RepeatPattern) -> int:
    return pattern.block_length * pattern.repeats


def _overlaps(existing: list[RepeatPattern], candidate: RepeatPattern) -> bool:
    for pattern in existing:
        if not (candidate.end_index < pattern.start_index or candidate.start_index > pattern.end_index):
            return True
    return False


def _infer_repeat_name(members: list[dict[str, Any]], pattern: RepeatPattern) -> str:
    """Infer a useful substructure suggestion from member names/comments."""
    words: list[str] = []
    first_block = members[pattern.start_index : pattern.start_index + pattern.block_length]
    for member in first_block:
        if not isinstance(member, dict):
            continue
        text = " ".join(
            str(part)
            for part in (member.get("name", ""), member.get("comment", ""), member.get("type", ""))
            if part
        )
        normalized = re.sub(r"\d+", "", text.lower())
        tokens = re.findall(r"[a-z]+", normalized)
        words.extend(token for token in tokens if token not in {"register", "bank", "mailbox", "fifo"})

    corpus = set(words)
    if "filter" in corpus:
        return "FilterBank"
    if {"tx", "transmit"} & corpus:
        return "TransmitMailbox"
    if {"rx", "receive"} & corpus:
        return "ReceiveMailbox"
    if {"mailbox"} & set(re.findall(r"[a-z]+", " ".join(str(m.get("comment", "")) for m in first_block).lower())):
        return "Mailbox"
    return f"Block{pattern.start_index}_{pattern.block_length}"


def detect_internal_repeats(
    peripheral: dict[str, Any],
    register_signatures: dict[str, tuple[Any, ...]],
) -> list[RepeatPattern]:
    """Find repeated contiguous member blocks inside a single peripheral."""
    members = peripheral.get("members", []) or []
    atoms = to_member_atoms(peripheral, register_signatures)
    n = len(atoms)
    if n < 4:
        return []

    candidates: list[RepeatPattern] = []
    max_block = min(16, n // 2)

    for block_len in range(2, max_block + 1):
        for start in range(0, n - block_len):
            first = atoms[start : start + block_len]
            next_start = start + block_len
            if next_start + block_len > n:
                continue
            second = atoms[next_start : next_start + block_len]
            if first != second:
                continue

            repeats = 2
            probe = next_start + block_len
            while probe + block_len <= n and atoms[probe : probe + block_len] == first:
                repeats += 1
                probe += block_len

            first_offset = to_int((members[start] or {}).get("offset"), start * 4)
            second_offset = to_int((members[next_start] or {}).get("offset"), next_start * 4)
            stride_bytes = second_offset - first_offset

            if repeats >= 2:
                candidates.append(
                    RepeatPattern(
                        start_index=start,
                        block_length=block_len,
                        repeats=repeats,
                        stride_bytes=stride_bytes,
                    )
                )

    # Prefer the highest-coverage, most repeated blocks and avoid overlap noise.
    candidates.sort(
        key=lambda pat: (
            -_pattern_coverage(pat),
            -pat.repeats,
            pat.block_length,
            pat.start_index,
        )
    )

    selected: list[RepeatPattern] = []
    for candidate in candidates:
        if _overlaps(selected, candidate):
            continue
        selected.append(candidate)

    selected.sort(key=lambda pat: pat.start_index)
    return selected


def compute_groups(
    records: list[PeripheralRecord], min_group_size: int
) -> list[GroupInfo]:
    """Group records by structural signature and compute family/suggested names."""
    grouped: dict[tuple[Any, ...], list[PeripheralRecord]] = defaultdict(list)
    for record in records:
        grouped[record.signature].append(record)

    duplicate_groups = [
        sorted(group, key=lambda item: item.name)
        for group in grouped.values()
        if len(group) >= min_group_size
    ]
    duplicate_groups.sort(key=lambda group: (-len(group), group[0].name))

    group_families: list[tuple[str, str]] = []
    for group in duplicate_groups:
        raw_names = [item.raw_name for item in group]
        family, pattern = detect_family_name(raw_names)
        if not family:
            family, pattern = detect_family_name([item.name for item in group])
        group_families.append((family, pattern))

    family_counts: Counter[str] = Counter(
        family for family, _ in group_families if family
    )

    result: list[GroupInfo] = []
    for group, (family, pattern) in zip(duplicate_groups, group_families):
        suggested_name = make_collision_safe_name(
            family, group, family_counts.get(family, 0)
        )
        result.append(GroupInfo(group=group, family=family, pattern=pattern, suggested_name=suggested_name))

    return result


def print_report(
    records: list[PeripheralRecord],
    min_group_size: int,
    report_internal_repeats: bool,
    register_signatures: dict[str, tuple[Any, ...]],
) -> list[GroupInfo]:
    """Print the duplicate-group report and return the computed groups."""
    group_infos = compute_groups(records, min_group_size)

    if not group_infos:
        print("No duplicated peripheral shapes were found.")
        if report_internal_repeats:
            print()
            print("Internal repeats across scanned peripherals:")
            found_any = False
            for record in records:
                source_data = load_yaml(record.path)
                peripheral = source_data.get("peripheral", {}) if isinstance(source_data, dict) else {}
                if not isinstance(peripheral, dict):
                    continue

                repeats = detect_internal_repeats(peripheral, register_signatures)
                if not repeats:
                    continue

                found_any = True
                members = peripheral.get("members", []) or []
                print(f"- {record.name}  file={record.path.name}")
                for pattern in repeats:
                    suggested = _infer_repeat_name(members, pattern)
                    print(
                        "  - members={}..{} block_len={} repeats={} stride=0x{:x} suggested={}".format(
                            pattern.start_index,
                            pattern.end_index,
                            pattern.block_length,
                            pattern.repeats,
                            pattern.stride_bytes,
                            suggested,
                        )
                    )
                print()

            if not found_any:
                print("(none found)")
        return group_infos

    potential_savings = sum(len(gi.group) - 1 for gi in group_infos)
    print(f"Scanned peripherals: {len(records)}")
    print(f"Duplicate shape groups: {len(group_infos)}")
    print(f"Potential type reductions: {potential_savings}")
    print()

    for index, gi in enumerate(group_infos, start=1):
        if gi.family:
            print(
                f"[{index}] Possible shared type: {gi.family} (pattern: {gi.pattern}) -> Suggested: {gi.suggested_name}"
            )
        else:
            print(f"[{index}] Possible shared type: (no shared numeric/letter-suffix family detected)")
        print(
            f"    Members: {gi.group[0].member_count}, Registers: {gi.group[0].register_count}, Instances: {len(gi.group)}"
        )
        for item in gi.group:
            print(f"    - {item.name}  base={item.base}  file={item.path.name}")

        if report_internal_repeats:
            source_data = load_yaml(gi.group[0].path)
            peripheral = source_data.get("peripheral", {}) if isinstance(source_data, dict) else {}
            if isinstance(peripheral, dict):
                repeats = detect_internal_repeats(peripheral, register_signatures)
                if repeats:
                    members = peripheral.get("members", []) or []
                    print("    Internal repeats (source instance):")
                    for pattern in repeats:
                        suggested = _infer_repeat_name(members, pattern)
                        print(
                            "    - members={}..{} block_len={} repeats={} stride=0x{:x} suggested={}".format(
                                pattern.start_index,
                                pattern.end_index,
                                pattern.block_length,
                                pattern.repeats,
                                pattern.stride_bytes,
                                suggested,
                            )
                        )

        print()

    return group_infos


def unify_group(
    gi: GroupInfo,
    canonical_type: str,
    yaml_dir: Path,
    out_dir: Path,
) -> None:
    """Write a canonical peripheral YAML and renamed register YAMLs to out_dir.

    The source instance (first alphabetically by raw_name) is used as the
    template.  Only filenames and the peripheral name/base fields are changed;
    register content is copied verbatim.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Alphabetically first instance is the source of truth
    source = gi.group[0]
    source_raw = source.raw_name
    source_data = load_yaml(source.path)
    peripheral = dict(source_data.get("peripheral") or {})

    # Rename register file references and copy the files
    old_registers: list[str] = list(peripheral.get("registers") or [])
    new_registers: list[str] = []
    old_prefix = f"register_{source_raw}_"
    for reg_filename in old_registers:
        if reg_filename.startswith(old_prefix):
            reg_suffix = reg_filename[len(old_prefix):]
        else:
            reg_suffix = reg_filename  # unexpected shape — keep as-is
        new_reg_filename = f"register_{canonical_type}_{reg_suffix}"
        new_registers.append(new_reg_filename)

        src_reg = yaml_dir / reg_filename
        dst_reg = out_dir / new_reg_filename
        if src_reg.exists() and not dst_reg.exists():
            shutil.copy2(src_reg, dst_reg)

    # Strip instance-specific fields
    peripheral["name"] = canonical_type
    peripheral.pop("base", None)
    # Tidy the comment: remove "(PERIPHERAL1)" suffix if present
    comment = str(peripheral.get("comment", ""))
    peripheral["comment"] = re.sub(r"\s*\(.*?\)\s*$", "", comment).strip()
    peripheral["registers"] = new_registers

    # Reconstruct include_lock from namespaces + canonical type name
    namespaces: list[str] = list(source_data.get("namespaces") or [])
    ns_part = "_".join(ns.upper() for ns in namespaces)
    include_lock = f"{ns_part}_{canonical_type.upper()}_" if ns_part else f"{canonical_type.upper()}_"

    out_data: dict[str, Any] = {
        "include_lock": include_lock,
        "namespaces": namespaces,
        "peripheral": peripheral,
    }

    out_path = out_dir / f"peripheral_{canonical_type}.yml"
    with out_path.open("w", encoding="utf-8") as fh:
        yaml.dump(out_data, fh, Dumper=yaml.SafeDumper)

    print(f"  Wrote {out_path.name}")
    print(f"  Wrote {len(new_registers)} register file(s) to {out_dir}")


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
    parser.add_argument(
        "--unify-group",
        type=int,
        metavar="N",
        help="Unify the Nth group from the report (1-based) into canonical YAML files.",
    )
    parser.add_argument(
        "--suggested-type",
        type=str,
        metavar="NAME",
        help=(
            "Override the canonical C++ type name used when unifying a group. "
            "Examples: BasicTimer, AdvancedTimer, InterIntegratedCircuit. "
            "Defaults to the auto-detected suggested name."
        ),
    )
    parser.add_argument(
        "--unify-dir",
        type=Path,
        metavar="DIR",
        help="Directory to write unified YAML files into. Required when --unify-group is used.",
    )
    parser.add_argument(
        "--report-internal-repeats",
        action="store_true",
        help=(
            "Report repeated contiguous member blocks within each duplicate-group source peripheral "
            "(for identifying candidates like mailboxes/filter banks)."
        ),
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

    min_size = max(2, args.min_group_size)
    register_signatures = load_register_signatures(yaml_dir)
    group_infos = print_report(
        records,
        min_size,
        args.report_internal_repeats,
        register_signatures,
    )

    if args.unify_group is not None:
        if args.unify_dir is None:
            print("--unify-dir is required when --unify-group is specified", file=sys.stderr)
            return 2

        idx = args.unify_group
        if idx < 1 or idx > len(group_infos):
            print(
                f"--unify-group {idx} is out of range; report has {len(group_infos)} group(s).",
                file=sys.stderr,
            )
            return 2

        gi = group_infos[idx - 1]
        canonical_type = args.suggested_type or gi.suggested_name
        if not canonical_type:
            print(
                f"Group {idx} has no auto-detected family name. "
                "Provide one with --suggested-type.",
                file=sys.stderr,
            )
            return 2

        print(f"Unifying group [{idx}] as type '{canonical_type}' into {args.unify_dir}")
        unify_group(gi, canonical_type, yaml_dir, args.unify_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
