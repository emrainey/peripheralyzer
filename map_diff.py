#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from typing import Any, cast

import yaml
from rich.console import Console
from rich.table import Table


MISSING = object()


def load_name_map(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if data is None:
        return {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected top-level mapping in {path}, got {type(data).__name__}")

    return cast(dict[str, dict[str, Any]], data)


def write_name_map(path: Path, data: dict[str, dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)


def get_entry(map_data: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
    entry = map_data.get(key)
    if isinstance(entry, dict):
        return entry

    replacement: dict[str, Any] = {}
    map_data[key] = replacement
    return replacement


def compare_name_maps(
    left_map: dict[str, dict[str, Any]],
    right_map: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    differences: list[dict[str, str]] = []

    shared_keys = sorted(set(left_map.keys()) & set(right_map.keys()))
    for key in shared_keys:
        left_entry = left_map.get(key) or {}
        right_entry = right_map.get(key) or {}

        left_type = str(left_entry.get("as_type", ""))
        right_type = str(right_entry.get("as_type", ""))
        left_variable = str(left_entry.get("as_variable", ""))
        right_variable = str(right_entry.get("as_variable", ""))

        if left_type == right_type and left_variable == right_variable:
            continue

        differences.append(
            {
                "key": key,
                "left_type": left_type,
                "right_type": right_type,
                "left_variable": left_variable,
                "right_variable": right_variable,
            }
        )

    return differences


def shared_difference_keys(
    left_map: dict[str, dict[str, Any]],
    right_map: dict[str, dict[str, Any]],
) -> list[str]:
    keys: list[str] = []
    shared_keys = sorted(set(left_map.keys()) & set(right_map.keys()))
    for key in shared_keys:
        left_entry = left_map.get(key)
        right_entry = right_map.get(key)
        if not isinstance(left_entry, dict):
            left_entry = {}
        if not isinstance(right_entry, dict):
            right_entry = {}

        left_type = str(left_entry.get("as_type", ""))
        right_type = str(right_entry.get("as_type", ""))
        left_variable = str(left_entry.get("as_variable", ""))
        right_variable = str(right_entry.get("as_variable", ""))

        if left_type != right_type or left_variable != right_variable:
            keys.append(key)

    return keys


def print_diff_table(
    console: Console,
    differences: list[dict[str, str]],
    left_label: str,
    right_label: str,
) -> None:
    table = Table(title="Name Map Differences", show_lines=True)
    table.add_column("Key", style="bold cyan")
    table.add_column(f"{left_label} as_type", style="green")
    table.add_column(f"{right_label} as_type", style="magenta")
    table.add_column(f"{left_label} as_variable", style="green")
    table.add_column(f"{right_label} as_variable", style="magenta")

    for row in differences:
        table.add_row(
            row["key"],
            row["left_type"],
            row["right_type"],
            row["left_variable"],
            row["right_variable"],
        )

    console.print(table)


def print_choose_view(
    console: Console,
    index: int,
    key: str,
    total: int,
    left_label: str,
    right_label: str,
    left_entry: dict[str, Any],
    right_entry: dict[str, Any],
    undo_count: int,
) -> None:
    console.clear()
    console.rule("Name Map Choose Mode")
    console.print(f"Difference {index + 1}/{total}: [bold cyan]{key}[/bold cyan]")
    console.print(
        "Commands: [bold]a[/bold]=copy left to right, [bold]d[/bold]=copy right to left, "
        "[bold]w[/bold]=up, [bold]s[/bold]=down, [bold]z[/bold]=undo, "
        "[bold]f[/bold]=finalize+write, [bold]q[/bold]=quit"
    )
    console.print(f"Undo stack: [bold]{undo_count}[/bold]")

    table = Table(show_lines=True)
    table.add_column("Field", style="bold")
    table.add_column(left_label, style="green")
    table.add_column(right_label, style="magenta")
    table.add_row(
        "as_type",
        str(left_entry.get("as_type", "")),
        str(right_entry.get("as_type", "")),
    )
    table.add_row(
        "as_variable",
        str(left_entry.get("as_variable", "")),
        str(right_entry.get("as_variable", "")),
    )
    console.print(table)


def interactive_choose_mode(
    console: Console,
    left_map: dict[str, dict[str, Any]],
    right_map: dict[str, dict[str, Any]],
    left_path: Path,
    right_path: Path,
) -> int:
    left_label = left_path.stem
    right_label = right_path.stem
    index = 0
    undo_stack: list[dict[str, Any]] = []

    while True:
        keys = shared_difference_keys(left_map, right_map)

        if not keys:
            console.clear()
            console.print("[bold green]No remaining differences.[/bold green]")
            console.print("Use [bold]z[/bold] to undo, [bold]f[/bold] to write both files, [bold]q[/bold] to quit.")
            command = input("Command (z/f/q): ").strip().lower()
            if command == "z":
                if not undo_stack:
                    console.print("[yellow]Nothing to undo.[/yellow]")
                    continue
                last = undo_stack.pop()
                key = last["key"]
                left_entry = get_entry(left_map, key)
                right_entry = get_entry(right_map, key)

                for field in ("as_type", "as_variable"):
                    left_value = last[f"left_{field}"]
                    right_value = last[f"right_{field}"]
                    if left_value is MISSING:
                        left_entry.pop(field, None)
                    else:
                        left_entry[field] = left_value
                    if right_value is MISSING:
                        right_entry.pop(field, None)
                    else:
                        right_entry[field] = right_value
                continue

            if command == "f":
                write_name_map(left_path, left_map)
                write_name_map(right_path, right_map)
                console.print("[bold green]Wrote both name_map files.[/bold green]")
                return 0

            if command == "q":
                console.print("[yellow]Exited choose mode without writing changes.[/yellow]")
                return 130

            console.print("[yellow]Unknown command.[/yellow]")
            continue

        if index < 0:
            index = 0
        if index >= len(keys):
            index = len(keys) - 1

        key = keys[index]
        left_entry = get_entry(left_map, key)
        right_entry = get_entry(right_map, key)
        print_choose_view(
            console,
            index,
            key,
            len(keys),
            left_label,
            right_label,
            left_entry,
            right_entry,
            len(undo_stack),
        )

        command = input("Command (a/d/w/s/z/f/q): ").strip().lower()

        if command in ("w", "up"):
            index = max(0, index - 1)
            continue

        if command in ("s", "down"):
            index = min(len(keys) - 1, index + 1)
            continue

        if command == "z":
            if not undo_stack:
                console.print("[yellow]Nothing to undo.[/yellow]")
                continue

            last = undo_stack.pop()
            undo_key = last["key"]
            left_undo_entry = get_entry(left_map, undo_key)
            right_undo_entry = get_entry(right_map, undo_key)

            for field in ("as_type", "as_variable"):
                left_value = last[f"left_{field}"]
                right_value = last[f"right_{field}"]
                if left_value is MISSING:
                    left_undo_entry.pop(field, None)
                else:
                    left_undo_entry[field] = left_value
                if right_value is MISSING:
                    right_undo_entry.pop(field, None)
                else:
                    right_undo_entry[field] = right_value
            continue

        if command == "a":
            undo_stack.append(
                {
                    "key": key,
                    "left_as_type": left_entry.get("as_type", MISSING),
                    "left_as_variable": left_entry.get("as_variable", MISSING),
                    "right_as_type": right_entry.get("as_type", MISSING),
                    "right_as_variable": right_entry.get("as_variable", MISSING),
                }
            )
            right_entry["as_type"] = left_entry.get("as_type", "")
            right_entry["as_variable"] = left_entry.get("as_variable", "")
            continue

        if command == "d":
            undo_stack.append(
                {
                    "key": key,
                    "left_as_type": left_entry.get("as_type", MISSING),
                    "left_as_variable": left_entry.get("as_variable", MISSING),
                    "right_as_type": right_entry.get("as_type", MISSING),
                    "right_as_variable": right_entry.get("as_variable", MISSING),
                }
            )
            left_entry["as_type"] = right_entry.get("as_type", "")
            left_entry["as_variable"] = right_entry.get("as_variable", "")
            continue

        if command == "f":
            write_name_map(left_path, left_map)
            write_name_map(right_path, right_map)
            console.print("[bold green]Wrote both name_map files.[/bold green]")
            return 0

        if command == "q":
            console.print("[yellow]Exited choose mode without writing changes.[/yellow]")
            return 130

        console.print("[yellow]Unknown command.[/yellow]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two name_map YAML files and show differing as_type/as_variable values for shared keys.",
    )
    parser.add_argument("left", type=Path, help="Path to the first name_map YAML file")
    parser.add_argument("right", type=Path, help="Path to the second name_map YAML file")
    parser.add_argument(
        "--choose",
        action="store_true",
        help="Interactive mode to choose left/right values, undo decisions, and write both files.",
    )
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    console = Console()

    try:
        left_map = load_name_map(args.left)
        right_map = load_name_map(args.right)
    except FileNotFoundError as exc:
        console.print(f"[bold red]File not found:[/bold red] {exc.filename}")
        return 2
    except ValueError as exc:
        console.print(f"[bold red]Invalid map format:[/bold red] {exc}")
        return 2
    except yaml.YAMLError as exc:
        console.print(f"[bold red]YAML parse error:[/bold red] {exc}")
        return 2

    differences = compare_name_maps(left_map, right_map)

    if args.choose:
        return interactive_choose_mode(console, left_map, right_map, args.left, args.right)

    left_label = args.left.stem
    right_label = args.right.stem
    shared_key_count = len(set(left_map.keys()) & set(right_map.keys()))

    console.print(f"Shared keys: [bold]{shared_key_count}[/bold]")
    console.print(f"Differences in as_type/as_variable: [bold]{len(differences)}[/bold]")

    if not differences:
        console.print("[bold green]No differences found for shared keys.[/bold green]")
        return 0

    print_diff_table(console, differences, left_label, right_label)
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
