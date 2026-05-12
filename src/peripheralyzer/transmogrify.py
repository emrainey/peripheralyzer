"""Convert CMSIS-SVD files into peripheralyzer YAML files."""

from __future__ import annotations

import argparse
import fnmatch
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml
from cmsis_svd.parser import SVDParser


class SortedSafeDumper(yaml.SafeDumper):
    def represent_sequence(self, tag: str, sequence: Any, flow_style: bool | None = None) -> Any:
        if sequence is not None and sequence and isinstance(sequence[0], str):
            sequence = sorted(sequence)
        return super().represent_sequence(tag, sequence, flow_style)


@dataclass(slots=True)
class TransmogrifyOptions:
    banner: bool
    svd: Path
    namespaces: list[str]
    name_map: Path
    yaml_root: Path
    verbose: bool
    dry_run: bool
    emit_fragment: Path | None
    fragment_cpp_root: Path | None
    fragment_templates: list[str]
    fragment_aggregate_target: str
    preserve_name_map: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "TransmogrifyOptions":
        return cls(
            banner=bool(args.banner),
            svd=Path(args.svd),
            namespaces=list(args.namespace or []),
            name_map=Path(args.name_map),
            yaml_root=Path(args.yaml_root),
            verbose=bool(args.verbose),
            dry_run=bool(args.dry_run),
            emit_fragment=None if args.emit_fragment is None else Path(args.emit_fragment),
            fragment_cpp_root=None if args.fragment_cpp_root is None else Path(args.fragment_cpp_root),
            fragment_templates=list(args.fragment_templates or []),
            fragment_aggregate_target=args.fragment_aggregate_target,
            preserve_name_map=bool(args.preserve_name_map),
        )


class NameMapper:
    def __init__(self, file_path: Path, verbose: bool = False, preserve_existing: bool = True) -> None:
        self._file_path = file_path
        self._verbose = verbose
        self._preserve_existing = preserve_existing
        self._name_map: dict[str, dict[str, Any]] = {}
        self._original_keys: set[str] = set()
        self._new_entries: dict[str, dict[str, Any]] = {}

        if self._file_path.exists():
            if self._verbose:
                print(f"Loading {self._file_path}")
            with self._file_path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            if isinstance(data, dict):
                self._name_map = data
                self._original_keys = set(self._name_map.keys())
                for name in list(self._name_map.keys()):
                    self._normalize_entry(self._name_map[name])

    @property
    def new_entries(self) -> dict[str, dict[str, Any]]:
        return self._new_entries

    def _normalize_entry(self, entry: dict[str, Any]) -> None:
        if "as_variable" in entry and isinstance(entry["as_variable"], str):
            entry["as_variable"] = entry["as_variable"].lower()
        overrides = entry.get("overrides")
        if isinstance(overrides, dict):
            for override in overrides.values():
                if isinstance(override, dict):
                    self._normalize_entry(override)

    def _best_override(self, entry: dict[str, Any], context: str | None) -> dict[str, Any] | None:
        overrides = entry.get("overrides")
        if not context or not isinstance(overrides, dict):
            return None

        exact_override = overrides.get(context)
        if isinstance(exact_override, dict):
            return exact_override

        matches: list[tuple[int, int, str, dict[str, Any]]] = []
        for pattern, override in overrides.items():
            if not isinstance(pattern, str) or not isinstance(override, dict):
                continue
            if fnmatch.fnmatchcase(context, pattern):
                wildcard_count = sum(pattern.count(token) for token in "*?[")
                matches.append((wildcard_count, -len(pattern), pattern, override))

        if not matches:
            return None

        matches.sort(key=lambda match: (match[0], match[1], match[2]))
        return matches[0][3]

    def lookup(self, name: str, context: str | None) -> dict[str, Any]:
        if name not in self._name_map:
            new_entry = {
                "as_type": name,
                "as_variable": name.lower(),
                "context": [context],
            }
            if self._preserve_existing:
                self._new_entries[name] = new_entry
                return new_entry
            self._name_map[name] = new_entry

        entry = self._name_map[name]
        if "context" in entry:
            if context and context not in entry["context"]:
                entry["context"].append(context)
        else:
            entry["context"] = [context]

        override = self._best_override(entry, context)
        if override is None:
            return entry

        merged_entry = dict(entry)
        merged_entry.update(override)
        merged_entry["context"] = entry["context"]
        return merged_entry

    def as_type(self, name: str, context: str | None = None) -> str:
        return str(self.lookup(name, context)["as_type"])

    def as_variable(self, name: str, context: str | None = None) -> str:
        return str(self.lookup(name, context)["as_variable"])

    def dump(self) -> None:
        if self._verbose:
            print(f"Dumping {self._file_path}")
        assert self._name_map

        if self._preserve_existing:
            original_map = {key: value for key, value in self._name_map.items() if key in self._original_keys}
            with self._file_path.open("w", encoding="utf-8") as handle:
                yaml.dump(data=original_map, stream=handle, sort_keys=True, Dumper=SortedSafeDumper)
            if self._new_entries:
                new_entries_file = self._file_path.with_name(
                    self._file_path.stem + "_new_entries" + self._file_path.suffix
                )
                if self._verbose:
                    print(f"Discovered {len(self._new_entries)} new entries")
                    print(f"Writing new entries to {new_entries_file}")
                with new_entries_file.open("w", encoding="utf-8") as handle:
                    yaml.dump(data=self._new_entries, stream=handle, sort_keys=True, Dumper=SortedSafeDumper)
        else:
            with self._file_path.open("w", encoding="utf-8") as handle:
                yaml.dump(data=self._name_map, stream=handle, sort_keys=True, Dumper=SortedSafeDumper)


def fix_comment(comment: str | None) -> str:
    if comment is None:
        return ""
    return re.sub(r"\s+", " ", comment).strip()


def fix_sizeof(sizeof: int | str) -> int:
    if isinstance(sizeof, str):
        sizeof = int(sizeof, 0)
    if sizeof % 4 == 1:
        return int(sizeof - 1)
    return int(sizeof)


class YamlDumper:
    def __init__(self, dry_run: bool = False, verbose: bool = False) -> None:
        self._file_map: dict[Path, bool] = {}
        self._dry_run = dry_run
        self._verbose = verbose

    def output_paths(self) -> list[Path]:
        return sorted(self._file_map.keys())

    def dump(self, data: dict[str, Any], yaml_file_path: Path) -> None:
        if self._verbose:
            print(yaml.dump(data))
        if yaml_file_path in self._file_map:
            raise ValueError(f"Duplicate name found! {yaml_file_path}")
        self._file_map[yaml_file_path] = True
        if self._dry_run:
            return
        yaml_file_path.parent.mkdir(parents=True, exist_ok=True)
        with yaml_file_path.open("w", encoding="utf-8") as handle:
            yaml.dump(data, handle, Dumper=yaml.SafeDumper)


class Transmogrifier:
    def __init__(self, options: TransmogrifyOptions) -> None:
        self.options = options
        self.mapper = NameMapper(
            options.name_map,
            verbose=options.verbose,
            preserve_existing=options.preserve_name_map,
        )
        self.dumper = YamlDumper(
            dry_run=options.dry_run or bool(options.emit_fragment),
            verbose=options.verbose,
        )

    @property
    def verbose(self) -> bool:
        return self.options.verbose

    def _print_banner(self) -> None:
        print(
            """

░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░ ░▒▓███████▓▒░▒▓██████████████▓▒░ ░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓███████▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░
   ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
   ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
   ░▒▓█▓▒░   ░▒▓███████▓▒░░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒▒▓███▓▒░▒▓███████▓▒░░▒▓█▓▒░▒▓██████▓▒░  ░▒▓██████▓▒░
   ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░         ░▒▓█▓▒░
   ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░         ░▒▓█▓▒░
   ░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓███████▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓█▓▒░░▒▓██████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░         ░▒▓█▓▒░

"""
        )

    def _write_peripheral_fragment(self, peripheral_entries: list[tuple[Path, str, str]]) -> None:
        emit_fragment = self.options.emit_fragment
        cpp_root = self.options.fragment_cpp_root
        if emit_fragment is None or cpp_root is None:
            print("--emit-fragment requires --fragment-cpp-root", file=sys.stderr)
            raise SystemExit(1)

        yml_root = self.options.yaml_root
        templates = self.options.fragment_templates or ["peripheral.hpp.jinja"]
        template_flags = " ".join(f"-t {template}" for template in templates)
        transmogrify_stamp = yml_root.parent / ".transmogrify.stamp"
        peripheralyzer_stamp = yml_root.parent / ".peripheralyzer.stamp"
        aggregate = self.options.fragment_aggregate_target

        seen_types: set[str] = set()
        all_outputs: list[Path] = []
        rules: list[str] = []

        for yml_path, svd_name, type_name in peripheral_entries:
            if type_name in seen_types:
                continue
            seen_types.add(type_name)

            outputs: list[Path] = []
            for template in templates:
                ext = Path(template).name.split(".")[1]
                outputs.append(cpp_root / f"{type_name}.{ext}")

            all_outputs.extend(outputs)
            outputs_str = " \\\n    ".join(os.fspath(output) for output in outputs)

            rule_lines = [
                f"{outputs_str}: \\",
                f"    {yml_path} \\",
                f"    $(wildcard {yml_root}/register_{svd_name}_*.yml) \\",
                f"    $(wildcard {yml_root}/enum_{svd_name}_*_*.yml) \\",
                f"    {transmogrify_stamp} \\",
                "    src/peripheralyzer/generate.py \\",
                "    src/peripheralyzer/cli.py",
                f"\tmkdir -p {cpp_root}",
                (
                    f"\t$(PERIPHERALYZER) generate -tr $(TEMPLATES) -yr {yml_root}"
                    f" -o {cpp_root} -y {yml_path.name} {template_flags} -a"
                ),
                "",
            ]
            rules.append("\n".join(rule_lines))

        all_outputs_str = " \\\n    ".join(os.fspath(output) for output in all_outputs) if all_outputs else ""
        lines = [
            "# Auto-generated by peripheralyzer transmogrify --emit-fragment",
            "# Do not edit manually",
            "",
        ]
        if all_outputs_str:
            lines.append(f".PHONY: {aggregate}")
            lines.append(f"{aggregate}: \\\n    {all_outputs_str}")
            lines.append("")
            lines.append(f"{peripheralyzer_stamp}: \\\n    {all_outputs_str}")
            lines.append("")
            lines.extend(rules)

        emit_fragment.parent.mkdir(parents=True, exist_ok=True)
        emit_fragment.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _require_text(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"Missing required text field: {field_name}")
        return value

    @staticmethod
    def _require_int(value: Any, field_name: str) -> int:
        if not isinstance(value, int):
            raise ValueError(f"Missing required integer field: {field_name}")
        return value

    def run(self) -> int:
        if self.options.banner:
            self._print_banner()

        if self.options.yaml_root and not (self.options.dry_run or self.options.emit_fragment):
            self.options.yaml_root.mkdir(parents=True, exist_ok=True)

        peripheral_entries: list[tuple[Path, str, str]] = []
        svd_parser = SVDParser.for_xml_file(os.fspath(self.options.svd))
        svd_device = cast(Any, svd_parser.get_device())
        device_width = self._require_int(svd_device.width, "device.width")
        address_unit_bits = self._require_int(
            svd_device.address_unit_bits, "device.address_unit_bits"
        )
        default_type = f"uint{device_width}_t"
        default_depth = device_width

        for raw_peripheral in cast(list[Any], svd_device.peripherals or []):
            svd_peripheral = cast(Any, raw_peripheral)
            peripheral_name = self._require_text(svd_peripheral.name, "peripheral.name")
            peripheral_base_address = self._require_int(
                svd_peripheral.base_address, f"{peripheral_name}.base_address"
            )
            address_blocks = cast(list[Any], getattr(svd_peripheral, "address_blocks", []) or [])
            if not address_blocks:
                raise ValueError(f"Peripheral {peripheral_name} has no address blocks")
            peripheral_size = self._require_int(address_blocks[0].size, f"{peripheral_name}.size")
            data: dict[str, Any] = {
                "peripheral": {
                    "base": hex(peripheral_base_address),
                    "name": self.mapper.as_type(peripheral_name),
                    "comment": fix_comment(getattr(svd_peripheral, "description", None)) + f" ({peripheral_name})",
                    "default_type": default_type,
                    "default_depth": default_depth,
                    "sizeof": hex(int(fix_sizeof(peripheral_size))),
                    "registers": [],
                    "structures": [],
                    "members": [],
                }
            }
            offsets: dict[str, list[dict[str, Any]]] = {}
            for raw_register in cast(list[Any], getattr(svd_peripheral, "registers", []) or []):
                svd_register = cast(Any, raw_register)
                register_name = self._require_text(svd_register.name, f"{peripheral_name}.register.name")
                register_offset = self._require_int(
                    svd_register.address_offset, f"{peripheral_name}.{register_name}.offset"
                )
                register_size = self._require_int(
                    svd_register.size, f"{peripheral_name}.{register_name}.size"
                )
                member = {
                    "name": self.mapper.as_variable(
                        register_name,
                        context=f"{peripheral_name}.{register_name}",
                    ),
                    "comment": fix_comment(getattr(svd_register, "description", None)) + f" ({register_name})",
                    "type": self.mapper.as_type(
                        register_name,
                        context=f"{peripheral_name}.{register_name}",
                    ),
                    "count": 1,
                    "offset": hex(register_offset),
                    "sizeof": hex(int(register_size / address_unit_bits)),
                }
                member_offset = str(member["offset"])
                offsets.setdefault(member_offset, []).append(member)

                register: dict[str, Any] = {
                    "name": self.mapper.as_type(
                        register_name,
                        context=f"{peripheral_name}.{register_name}",
                    ),
                    "comment": fix_comment(getattr(svd_register, "description", None)) + f" ({register_name})",
                    "default_depth": default_depth,
                    "default_type": default_type,
                    "sizeof": int(register_size / address_unit_bits),
                    "fields": [],
                    "enums": [],
                }
                for raw_field in cast(list[Any], getattr(svd_register, "fields", []) or []):
                    field = cast(Any, raw_field)
                    field_name = self._require_text(field.name, f"{peripheral_name}.{register_name}.field.name")
                    bit_offset = self._require_int(
                        field.bit_offset, f"{peripheral_name}.{register_name}.{field_name}.bit_offset"
                    )
                    bit_width = self._require_int(
                        field.bit_width, f"{peripheral_name}.{register_name}.{field_name}.bit_width"
                    )
                    field_context = f"{peripheral_name}.{register_name}"
                    output_field: dict[str, Any] = {
                        "name": self.mapper.as_variable(field_name, context=field_context),
                        "offset": bit_offset,
                        "count": bit_width,
                        "comment": fix_comment(getattr(field, "description", None)) + f" ({field_name})",
                    }
                    if bool(getattr(field, "is_enumerated_type", False)):
                        output_field["type"] = self.mapper.as_type(field_name, context=field_context)
                        enum: dict[str, Any] = {
                            "name": self.mapper.as_type(
                                field_name,
                                context=f"{field_context}.{field_name}",
                            ),
                            "comment": fix_comment(getattr(field, "description", None)) + f" ({field_name})",
                            "type": default_type,
                            "default_depth": default_depth,
                            "symbols": [],
                        }
                        for raw_enumeration in cast(list[Any], getattr(field, "enumerated_values", []) or []):
                            enumeration = cast(Any, raw_enumeration)
                            enum_name = getattr(enumeration, "name", None) or field_name
                            if self.verbose:
                                print(f"Found enum {enum_name}")
                            for raw_enumerated_value in cast(
                                list[Any], getattr(enumeration, "enumerated_values", []) or []
                            ):
                                enumerated_value = cast(Any, raw_enumerated_value)
                                name = self._require_text(
                                    enumerated_value.name,
                                    f"{peripheral_name}.{register_name}.{field_name}.enum.name",
                                )
                                if self.verbose:
                                    print(f"\tFound enum {name}")
                                enum["symbols"].append(
                                    {
                                        "name": self.mapper.as_type(
                                            name,
                                            context=f"{field_context}.{field_name}.{name}",
                                        ),
                                        "value": enumerated_value.value,
                                        "comment": fix_comment(enumerated_value.description) + f" ({name})",
                                    }
                                )
                        yaml_file = f"enum_{peripheral_name}_{register_name}_{field_name}.yml"
                        yaml_file_path = self.options.yaml_root / yaml_file
                        register["enums"].append(yaml_file)
                        self.dumper.dump(enum, yaml_file_path)
                    register["fields"].append(output_field)

                yaml_file = f"register_{peripheral_name}_{register_name}.yml"
                yaml_file_path = self.options.yaml_root / yaml_file
                data["peripheral"]["registers"].append(yaml_file)
                self.dumper.dump(register, yaml_file_path)

            for offset, members in offsets.items():
                if len(members) > 1:
                    max_sizeof = max(members, key=lambda member: int(member["sizeof"], 0))["sizeof"]
                    data["peripheral"]["members"].append(
                        {
                            "is_union": True,
                            "offset": offset,
                            "sizeof": max_sizeof,
                            "members": members,
                        }
                    )
                else:
                    data["peripheral"]["members"].append(members[0])

            yaml_file = f"peripheral_{peripheral_name}.yml"
            yaml_file_path = self.options.yaml_root / yaml_file
            if self.options.namespaces:
                data["namespaces"] = self.options.namespaces
            namespaces = list(data.get("namespaces", []))
            ns = "_".join(namespaces)
            peripheral_name = data["peripheral"]["name"]
            data["include_lock"] = f"{ns}_{peripheral_name}_".upper() if ns else f"{peripheral_name}_".upper()
            self.dumper.dump(data, yaml_file_path)
            peripheral_entries.append((yaml_file_path, svd_peripheral.name, data["peripheral"]["name"]))

        if self.options.emit_fragment:
            self._write_peripheral_fragment(peripheral_entries)
        elif self.options.dry_run:
            for output_path in self.dumper.output_paths():
                print(output_path)
        else:
            self.mapper.dump()
            if self.options.preserve_name_map and self.mapper.new_entries:
                new_entries_file = self.options.name_map.with_name(
                    self.options.name_map.stem + "_new_entries" + self.options.name_map.suffix
                )
                print(f"\n✓ Discovered {len(self.mapper.new_entries)} new entries")
                print(f"  New entries saved to: {new_entries_file}")
                print(f"  Review and rename them, then merge into: {self.options.name_map}")

        return 0


class TransmogrifyCommand:
    name = "transmogrify"
    help = "Convert CMSIS-SVD files into peripheralyzer YAML files."

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.help
        parser.add_argument("-b", "--banner", action="store_true", help="Prints a sick banner.")
        parser.add_argument("-s", "--svd", type=str, required=True, help="The CMSIS SVD file")
        parser.add_argument(
            "-ns",
            "--namespace",
            type=str,
            action="append",
            help="The namespaces to use in the file (appendable)",
        )
        parser.add_argument(
            "-nm",
            "--name-map",
            type=str,
            default="name_map.yml",
            help="The dictionary of name mappings",
        )
        parser.add_argument(
            "-yr",
            "--yaml-root",
            type=str,
            default=os.getcwd(),
            help="The yaml output folder (default:%(default)s)",
        )
        parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose information")
        parser.add_argument(
            "-n",
            "--dry-run",
            action="store_true",
            help="Emit generated yaml file paths without writing files",
        )
        parser.add_argument(
            "--emit-fragment",
            type=str,
            metavar="PATH",
            help="Write a Makefile fragment of per-peripheral targets to PATH (implies --dry-run)",
        )
        parser.add_argument(
            "--fragment-cpp-root",
            type=str,
            metavar="PATH",
            help="Output directory for cpp/hpp files referenced in the fragment",
        )
        parser.add_argument(
            "--fragment-template",
            type=str,
            action="append",
            dest="fragment_templates",
            metavar="TEMPLATE",
            help="Template filename in the fragment, e.g. peripheral.hpp.jinja (appendable)",
        )
        parser.add_argument(
            "--fragment-aggregate-target",
            type=str,
            metavar="TARGET",
            default="_peripherals",
            help="Name of the aggregate .PHONY target in the fragment (default: %(default)s)",
        )
        parser.add_argument(
            "--preserve-name-map",
            action="store_true",
            default=True,
            help="Preserve existing name map entries and write new ones to a separate file (default: True)",
        )
        parser.add_argument(
            "--expand-name-map",
            action="store_false",
            dest="preserve_name_map",
            help="Allow transmogrify to auto-expand the name map with new entries (legacy behavior)",
        )

    def run(self, args: argparse.Namespace) -> int:
        return Transmogrifier(TransmogrifyOptions.from_namespace(args)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peripheralyzer transmogrify")
    command = TransmogrifyCommand()
    command.configure_parser(parser)
    args = parser.parse_args(argv)
    return command.run(args)
