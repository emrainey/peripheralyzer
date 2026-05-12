"""Generate C and C++ code from peripheral YAML descriptions."""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2
import yaml

from .paths import package_templates_root


def camel_to_snake_case(name: str) -> str:
    """Convert CamelCase text into snake_case."""
    snake_string = re.sub("([A-Z])", r"_\1", name)
    return snake_string.lower().lstrip("_")


@dataclass(slots=True)
class GenerateOptions:
    banner: bool
    templates: list[str]
    yaml_files: list[str]
    verbose: bool
    output: Path
    template_root: Path
    yaml_root: Path | None
    anonymous: bool

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "GenerateOptions":
        yaml_root = None if args.yaml_root is None else Path(args.yaml_root)
        return cls(
            banner=bool(args.banner),
            templates=list(args.template or []),
            yaml_files=list(args.yaml or []),
            verbose=bool(args.verbose),
            output=Path(args.output),
            template_root=Path(args.template_root),
            yaml_root=yaml_root,
            anonymous=bool(args.anonymous),
        )


class YamlLoader:
    """Load YAML files once and cache the parsed content."""

    def __init__(self, yaml_root: Path | None, verbose: bool = False) -> None:
        self.yaml_root = yaml_root
        self.verbose = verbose
        self.loaded_files: dict[Path, dict[str, Any]] = {}

    def load(self, filename: str) -> dict[str, Any]:
        filepath = (self.yaml_root / filename) if self.yaml_root is not None else Path(filename)
        filepath = filepath.resolve()
        if filepath not in self.loaded_files:
            if self.verbose:
                print(f"Loading {filepath}")
            if not filepath.exists():
                raise FileNotFoundError(f"File {filepath} must exist")
            with filepath.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            if not isinstance(data, dict):
                raise ValueError(f"Expected YAML mapping in {filepath}")
            self.loaded_files[filepath] = data
        return self.loaded_files[filepath]


class PeripheralGenerator:
    """Stateful generator for rendering peripherals from YAML into templates."""

    def __init__(self, options: GenerateOptions) -> None:
        self.options = options
        self.loader = YamlLoader(options.yaml_root, verbose=options.verbose)
        self.use_named_reserved = not options.anonymous

    @property
    def verbose(self) -> bool:
        return self.options.verbose

    def validate_structure(self, structure: dict[str, Any]) -> None:
        for key in ("name", "sizeof", "default_depth", "default_type", "members"):
            assert key in structure

    def validate_register(self, register: dict[str, Any]) -> None:
        for key in ("name", "default_depth", "default_type", "fields", "sizeof"):
            assert key in register

    @staticmethod
    def validate_member(member: dict[str, Any]) -> None:
        assert "name" in member or "is_union" in member
        assert "offset" in member
        if "type" in member:
            assert "sizeof" in member, f"Missing sizeof in {member}"

    @staticmethod
    def validate_field(field: dict[str, Any]) -> None:
        assert "name" in field
        assert "offset" in field

    @staticmethod
    def validate_enum(enumeration: dict[str, Any]) -> None:
        for key in ("name", "type", "symbols"):
            assert key in enumeration

    @staticmethod
    def convert_to_int(entry: dict[str, Any], key: str) -> int:
        value = entry[key]
        if isinstance(value, str):
            entry[key] = int(value, 0)
        elif not isinstance(value, int):
            raise NotImplementedError(
                f"Unknown conversion from {value.__class__.__name__} to int for {key}"
            )
        return int(entry[key])

    def pad_members(
        self,
        members: list[dict[str, Any]],
        default_type: str,
        member_sizeof: int,
        start: int,
        limit: int,
    ) -> int:
        count = int(start)
        while count < limit:
            if self.use_named_reserved:
                bytes_diff = int(limit - count)
                unit_diff = int(bytes_diff / member_sizeof)
                reserved = {
                    "type": default_type,
                    "name": f"_reserved_{hex(count)}",
                    "count": unit_diff,
                    "offset": f"{hex(count)}",
                }
                count = int(count + int(unit_diff * member_sizeof))
            else:
                reserved = {
                    "type": default_type,
                    "name": "",
                    "count": 1,
                    "offset": f"{hex(count)}",
                }
                count = int(count + member_sizeof)
            if self.verbose:
                print(f"Padding member {reserved}")
            members.append(reserved)
        return count

    def pack_members(
        self,
        old_members: list[dict[str, Any]],
        depth: int,
        default_type: str,
        sizeof: int,
    ) -> list[dict[str, Any]]:
        sorted_members = sorted(old_members, key=lambda member: self.convert_to_int(member, "offset"))
        members: list[dict[str, Any]] = []
        count = 0
        member_sizeof = int(depth / 8)
        for member in sorted_members:
            self.validate_member(member)
            offset = self.convert_to_int(member, "offset")
            count = self.pad_members(members, default_type, member_sizeof, count, offset)
            member.setdefault("type", default_type)
            member.setdefault("count", 1)
            member.setdefault("comment", "FIXME (comment)")
            member.setdefault("sizeof", member_sizeof)
            self.convert_to_int(member, "sizeof")
            count = int(offset) + int(member["sizeof"])
            member["offset"] = hex(offset)
            if self.verbose:
                print(f"Adding member {member}")
            members.append(member)
        self.pad_members(members, default_type, member_sizeof, count, sizeof)
        return members

    def pad_fields(
        self,
        fields: list[dict[str, Any]],
        default_type: str,
        start: int,
        limit: int,
    ) -> int:
        index = int(start)
        while index < limit:
            diff = int(limit - index)
            reserved = {
                "name": "",
                "type": default_type,
                "count": diff,
                "offset": index,
                "comment": "(reserved)",
            }
            index = int(index + diff)
            if self.verbose:
                print(f"Padding field {reserved}")
            fields.append(reserved)
        return index

    def pack_fields(
        self,
        old_fields: list[dict[str, Any]],
        depth: int,
        default_type: str,
    ) -> list[dict[str, Any]]:
        sorted_fields = sorted(old_fields, key=lambda field: int(field["offset"]))
        fields: list[dict[str, Any]] = []
        index = 0
        for field in sorted_fields:
            self.validate_field(field)
            offset = int(field["offset"])
            index = self.pad_fields(fields, default_type=default_type, start=index, limit=offset)
            field.setdefault("type", default_type)
            field.setdefault("comment", "FIXME (comment)")
            field.setdefault("count", 1)
            index = int(index + int(field["count"]))
            if self.verbose:
                print(f"Adding field {field}")
            fields.append(field)
        self.pad_fields(fields, default_type=default_type, start=index, limit=depth)
        return fields

    def process_enums(self, top: dict[str, Any]) -> None:
        if "enums" not in top:
            return
        enums: list[dict[str, Any]] = []
        for yaml_file in top["enums"]:
            data = self.loader.load(yaml_file)
            if self.verbose:
                print(f"Loading {data}")
            self.validate_enum(data)
            if "type" in data:
                for symbol in data["symbols"]:
                    symbol.setdefault("comment", "FIXME (comment)")
            enums.append(data)
        top["enums"] = enums

    def process_register(self, top: dict[str, Any]) -> None:
        if "registers" not in top:
            return
        registers: list[dict[str, Any]] = []
        for yaml_file in top["registers"]:
            register = self.loader.load(yaml_file)
            if self.verbose:
                print(f"Loaded {register}")
            self.validate_register(register)
            if isinstance(register["sizeof"], str):
                register["sizeof"] = int(register["sizeof"], 0)
            register["fields"] = self.pack_fields(
                old_fields=register["fields"],
                depth=int(register["default_depth"]),
                default_type=str(register["default_type"]),
            )
            self.process_enums(register)
            registers.append(register)
        top["registers"] = registers

    def process_structure(self, top: dict[str, Any]) -> None:
        if "structures" not in top:
            return
        structures: list[dict[str, Any]] = []
        for yaml_file in top["structures"]:
            structure = self.loader.load(yaml_file)
            if self.verbose:
                print(f"Loaded {structure}")
            self.validate_structure(structure)
            sizeof = structure["sizeof"]
            if isinstance(sizeof, str):
                sizeof = int(sizeof, 0)
            structure["members"] = self.pack_members(
                old_members=structure["members"],
                depth=int(structure["default_depth"]),
                default_type=str(structure["default_type"]),
                sizeof=int(sizeof),
            )
            self.process_enums(structure)
            self.process_structure(structure)
            self.process_register(structure)
            if isinstance(structure["sizeof"], int):
                structure["sizeof"] = hex(structure["sizeof"])
            else:
                structure["sizeof"] = hex(int(structure["sizeof"], 0))
            structures.append(structure)
        top["structures"] = structures

    def _build_environment(self) -> jinja2.Environment:
        environment = jinja2.Environment(
            loader=jinja2.FileSystemLoader(os.fspath(self.options.template_root))
        )
        environment.filters["debug"] = lambda value: print(value) or value
        environment.filters["list"] = list
        environment.filters["conjoin"] = lambda namespace: f"{namespace}::"
        environment.filters["snake_case"] = camel_to_snake_case
        return environment

    def _print_banner(self) -> None:
        print(
            r"""

░▒▓███████▓▒░░▒▓████████▓▒░▒▓███████▓▒░░▒▓█▓▒░▒▓███████▓▒░░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓███████▓▒░ ░▒▓██████▓▒░░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓████████▓▒░▒▓███████▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░      ░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░   ░▒▓█▓▒░░▒▓█▓▒░    ░▒▓██▓▒░░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓███████▓▒░░▒▓██████▓▒░ ░▒▓███████▓▒░░▒▓█▓▒░▒▓███████▓▒░░▒▓████████▓▒░▒▓██████▓▒░ ░▒▓███████▓▒░░▒▓████████▓▒░▒▓█▓▒░    ░▒▓██████▓▒░   ░▒▓██▓▒░  ░▒▓██████▓▒░ ░▒▓███████▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░    ░▒▓██▓▒░    ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░   ░▒▓█▓▒░      ░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░
░▒▓█▓▒░      ░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░▒▓█▓▒░      ░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓█▓▒░░▒▓█▓▒░▒▓████████▓▒░▒▓█▓▒░   ░▒▓████████▓▒░▒▓████████▓▒░▒▓█▓▒░░▒▓█▓▒░

"""
        )

    def run(self) -> int:
        if self.options.banner:
            self._print_banner()

        environment = self._build_environment()
        self.options.output.mkdir(parents=True, exist_ok=True)

        for yaml_file in self.options.yaml_files:
            data = self.loader.load(yaml_file)
            assert "peripheral" in data
            peripheral = data["peripheral"]
            self.validate_structure(peripheral)

            default_type = str(peripheral["default_type"])
            depth = int(peripheral["default_depth"])
            sizeof = int(peripheral["sizeof"], 0) if isinstance(peripheral["sizeof"], str) else int(peripheral["sizeof"])

            self.process_enums(peripheral)
            self.process_structure(peripheral)
            self.process_register(peripheral)

            peripheral["members"] = self.pack_members(
                old_members=peripheral["members"],
                depth=depth,
                default_type=default_type,
                sizeof=sizeof,
            )
            peripheral["sizeof"] = hex(sizeof)

            for template_file in self.options.templates:
                template_path = self.options.template_root / template_file
                if not template_path.exists():
                    print(f"Template {template_path} not found.")
                    return -1
                template_data = template_path.read_text(encoding="utf-8")
                _, template_ext, _ = template_path.name.split(".")
                template = environment.from_string(template_data)
                rendered = template.render(data)
                filepath = self.options.output / f"{peripheral['name']}.{template_ext}"
                filepath.write_text(rendered, encoding="utf-8")
                if self.verbose:
                    print(rendered)
        return 0


class GenerateCommand:
    name = "generate"
    help = "Generate C/C++ code from peripheral YAML files."

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.help
        parser.add_argument("-b", "--banner", action="store_true", help="Prints a sick banner.")
        parser.add_argument(
            "-t",
            "--template",
            type=str,
            action="append",
            required=True,
            help="The template to use to generate the code.",
        )
        parser.add_argument(
            "-y",
            "--yaml",
            type=str,
            action="append",
            required=True,
            help="The yaml description of the peripheral set.",
        )
        parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose information.")
        parser.add_argument(
            "-o",
            "--output",
            type=str,
            default=os.getcwd(),
            help="[optional] the output path if given (default:%(default)s)",
        )
        parser.add_argument(
            "-tr",
            "--template-root",
            type=str,
            default=os.fspath(package_templates_root()),
            help="The location where the templates are kept (default=%(default)s)",
        )
        parser.add_argument(
            "-yr",
            "--yaml-root",
            type=str,
            default=None,
            help="The root to the location where the yamls are kept",
        )
        parser.add_argument(
            "-a",
            "--anonymous",
            action="store_true",
            help="Disable padding with named reserved fields",
        )

    def run(self, args: argparse.Namespace) -> int:
        return PeripheralGenerator(GenerateOptions.from_namespace(args)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peripheralyzer generate")
    command = GenerateCommand()
    command.configure_parser(parser)
    args = parser.parse_args(argv)
    return command.run(args)
