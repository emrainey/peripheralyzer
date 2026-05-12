"""Verify name-map YAML files for structure and naming issues."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CPP_KEYWORDS = {
    "alignas", "alignof", "and", "and_eq", "asm", "auto", "bitand", "bitor",
    "bool", "break", "case", "catch", "char", "char8_t", "char16_t", "char32_t",
    "class", "compl", "concept", "const", "consteval", "constexpr", "constinit",
    "const_cast", "continue", "co_await", "co_return", "co_yield", "decltype",
    "default", "delete", "do", "double", "dynamic_cast", "else", "enum", "explicit",
    "export", "extern", "false", "float", "for", "friend", "goto", "if", "inline",
    "int", "long", "mutable", "namespace", "new", "noexcept", "not", "not_eq",
    "nullptr", "operator", "or", "or_eq", "private", "protected", "public",
    "register", "reinterpret_cast", "requires", "return", "short", "signed",
    "sizeof", "static", "static_assert", "static_cast", "struct", "switch",
    "template", "this", "thread_local", "throw", "true", "try", "typedef",
    "typeid", "typename", "union", "unsigned", "using", "virtual", "void",
    "volatile", "wchar_t", "while", "xor", "xor_eq",
}


@dataclass(slots=True)
class VerifyNameMapResult:
    issues: list[str]
    warnings: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.issues


@dataclass(slots=True)
class VerifyNameMapOptions:
    filepath: Path

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "VerifyNameMapOptions":
        return cls(filepath=Path(args.filepath))


class NameMapVerifier:
    def verify(self, filepath: Path) -> VerifyNameMapResult:
        issues: list[str] = []
        warnings: list[str] = []

        if not filepath.exists():
            issues.append(f"File not found: {filepath}")
            return VerifyNameMapResult(issues=issues, warnings=warnings)

        try:
            with filepath.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except yaml.YAMLError as error:
            issues.append(f"YAML Syntax Error: {error}")
            return VerifyNameMapResult(issues=issues, warnings=warnings)
        except OSError as error:
            issues.append(f"Error reading file: {error}")
            return VerifyNameMapResult(issues=issues, warnings=warnings)

        if not isinstance(data, dict):
            issues.append("Root must be a dictionary")
            return VerifyNameMapResult(issues=issues, warnings=warnings)

        for entry_name, entry_data in data.items():
            if not isinstance(entry_data, dict):
                issues.append(
                    f"Entry '{entry_name}': value must be a dictionary, got {type(entry_data).__name__}"
                )
                continue

            if "as_type" not in entry_data:
                issues.append(f"Entry '{entry_name}': missing 'as_type' field")
            if "as_variable" not in entry_data:
                issues.append(f"Entry '{entry_name}': missing 'as_variable' field")
            if "context" not in entry_data:
                issues.append(f"Entry '{entry_name}': missing 'context' field")

            as_variable = str(entry_data.get("as_variable", ""))
            if as_variable.lower() in CPP_KEYWORDS:
                issues.append(
                    f"Entry '{entry_name}': variable name '{as_variable}' is a C++ keyword"
                )

            as_type = str(entry_data.get("as_type", ""))
            if as_type.lower() in CPP_KEYWORDS:
                issues.append(f"Entry '{entry_name}': type name '{as_type}' is a C++ keyword")

            context = entry_data.get("context")
            if context is not None and not isinstance(context, list):
                issues.append(
                    f"Entry '{entry_name}': 'context' must be a list, got {type(context).__name__}"
                )

        return VerifyNameMapResult(issues=issues, warnings=warnings)


class VerifyNameMapApp:
    def __init__(self, options: VerifyNameMapOptions) -> None:
        self.options = options
        self.verifier = NameMapVerifier()

    def run(self) -> int:
        filepath = self.options.filepath
        print(f"Verifying: {filepath}")
        print("-" * 60)

        result = self.verifier.verify(filepath)
        if result.issues and result.issues[0].startswith("File not found"):
            print(f"✗ {result.issues[0]}")
            return 1
        if result.issues and result.issues[0].startswith("YAML Syntax Error"):
            print(f"✗ {result.issues[0]}")
            return 1
        if result.issues and result.issues[0].startswith("Error reading file"):
            print(f"✗ {result.issues[0]}")
            return 1

        with filepath.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        print("✓ YAML syntax is valid")
        print(f"✓ Loaded {len(data)} entries")
        print()

        if result.issues:
            print(f"✗ Found {len(result.issues)} ERROR(S):")
            for index, issue in enumerate(result.issues[:20], start=1):
                print(f"  {index}. {issue}")
            if len(result.issues) > 20:
                print(f"  ... and {len(result.issues) - 20} more errors")
            return 1

        print("✓ No structural errors found")
        if result.warnings:
            print(f"\n⚠ Found {len(result.warnings)} warning(s):")
            for warning in result.warnings[:10]:
                print(f"  • {warning}")
            if len(result.warnings) > 10:
                print(f"  ... and {len(result.warnings) - 10} more warnings")

        print()
        print("=" * 60)
        print("✓ Verification PASSED")
        return 0


class VerifyNameMapCommand:
    name = "verify-name-map"
    help = "Verify a naming map YAML file."

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.description = self.help
        parser.add_argument(
            "filepath",
            nargs="?",
            default="STM32H753_name_map.yml",
            help="Path to the naming map YAML file",
        )

    def run(self, args: argparse.Namespace) -> int:
        return VerifyNameMapApp(VerifyNameMapOptions.from_namespace(args)).run()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peripheralyzer verify-name-map")
    command = VerifyNameMapCommand()
    command.configure_parser(parser)
    args = parser.parse_args(argv)
    return command.run(args)
