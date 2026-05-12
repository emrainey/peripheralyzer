#!/usr/bin/env python3
import argparse
import copy
import fnmatch
import sys
from pathlib import Path
from typing import Any, cast

import yaml
from rich.console import Console
from rich.table import Table


MISSING = object()
TRACKED_FIELDS = ("as_type", "as_variable", "overrides")


def format_entry_value(value: Any) -> str:
    if value is MISSING:
        return ""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return yaml.safe_dump(value, sort_keys=True).strip()
    return str(value)


def get_contexts(entry: dict[str, Any]) -> list[str]:
    contexts = entry.get("context")
    if not isinstance(contexts, list):
        return []
    return [context for context in contexts if isinstance(context, str)]


def filter_overrides_for_contexts(overrides: Any, contexts: list[str]) -> Any:
    if not isinstance(overrides, dict):
        return MISSING

    filtered: dict[str, Any] = {}
    for pattern, override in overrides.items():
        if not isinstance(pattern, str) or not isinstance(override, dict):
            continue
        if any(fnmatch.fnmatchcase(context, pattern) for context in contexts):
            filtered[pattern] = copy.deepcopy(override)

    if not filtered:
        return MISSING

    return filtered


def transferable_entry(entry: dict[str, Any], target_contexts: list[str]) -> dict[str, Any]:
    comparable = dict(entry)
    comparable.pop("context", None)

    filtered_overrides = filter_overrides_for_contexts(
        entry.get("overrides", MISSING), target_contexts
    )
    if filtered_overrides is MISSING:
        comparable.pop("overrides", None)
    else:
        comparable["overrides"] = filtered_overrides

    return comparable


def entry_values_differ(left_entry: dict[str, Any], right_entry: dict[str, Any]) -> bool:
    left_comparable = transferable_entry(left_entry, get_contexts(right_entry))
    right_comparable = transferable_entry(right_entry, get_contexts(left_entry))

    for field in TRACKED_FIELDS:
        if format_entry_value(left_comparable.get(field, MISSING)) != format_entry_value(
            right_comparable.get(field, MISSING)
        ):
            return True
    return False


def capture_entry_state(entry: dict[str, Any], prefix: str) -> dict[str, Any]:
    state = {}
    for field in TRACKED_FIELDS:
        value = entry.get(field, MISSING)
        state[f"{prefix}_{field}"] = copy.deepcopy(value)
    return state


def restore_entry_state(entry: dict[str, Any], snapshot: dict[str, Any], prefix: str) -> None:
    for field in TRACKED_FIELDS:
        value = copy.deepcopy(snapshot[f"{prefix}_{field}"])
        if value is MISSING:
            entry.pop(field, None)
        else:
            entry[field] = value


def copy_entry_fields(source: dict[str, Any], destination: dict[str, Any]) -> None:
    for field in TRACKED_FIELDS:
        if field == "overrides":
            value = filter_overrides_for_contexts(
                source.get("overrides", MISSING), get_contexts(destination)
            )
        else:
            value = source.get(field, MISSING)
        if value is MISSING:
            destination.pop(field, None)
        else:
            destination[field] = copy.deepcopy(value)


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

        if not entry_values_differ(left_entry, right_entry):
            continue

        differences.append(
            {
                "key": key,
                "left_type": format_entry_value(
                    transferable_entry(left_entry, get_contexts(right_entry)).get("as_type", "")
                ),
                "right_type": format_entry_value(
                    transferable_entry(right_entry, get_contexts(left_entry)).get("as_type", "")
                ),
                "left_variable": format_entry_value(
                    transferable_entry(left_entry, get_contexts(right_entry)).get("as_variable", "")
                ),
                "right_variable": format_entry_value(
                    transferable_entry(right_entry, get_contexts(left_entry)).get("as_variable", "")
                ),
                "left_overrides": format_entry_value(
                    transferable_entry(left_entry, get_contexts(right_entry)).get("overrides", MISSING)
                ),
                "right_overrides": format_entry_value(
                    transferable_entry(right_entry, get_contexts(left_entry)).get("overrides", MISSING)
                ),
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

        if entry_values_differ(left_entry, right_entry):
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
    table.add_column(f"{left_label} overrides", style="green")
    table.add_column(f"{right_label} overrides", style="magenta")

    for row in differences:
        table.add_row(
            row["key"],
            row["left_type"],
            row["right_type"],
            row["left_variable"],
            row["right_variable"],
            row["left_overrides"],
            row["right_overrides"],
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

    left_display = transferable_entry(left_entry, get_contexts(right_entry))
    right_display = transferable_entry(right_entry, get_contexts(left_entry))

    table = Table(show_lines=True)
    table.add_column("Field", style="bold")
    table.add_column(left_label, style="green")
    table.add_column(right_label, style="magenta")
    table.add_row(
        "as_type",
        str(left_display.get("as_type", "")),
        str(right_display.get("as_type", "")),
    )
    table.add_row(
        "as_variable",
        format_entry_value(left_display.get("as_variable", "")),
        format_entry_value(right_display.get("as_variable", "")),
    )
    table.add_row(
        "overrides",
        format_entry_value(left_display.get("overrides", MISSING)),
        format_entry_value(right_display.get("overrides", MISSING)),
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

                restore_entry_state(left_entry, last, "left")
                restore_entry_state(right_entry, last, "right")
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

            restore_entry_state(left_undo_entry, last, "left")
            restore_entry_state(right_undo_entry, last, "right")
            continue

        if command == "a":
            undo_stack.append(
                {
                    "key": key,
                    **capture_entry_state(left_entry, "left"),
                    **capture_entry_state(right_entry, "right"),
                }
            )
            copy_entry_fields(left_entry, right_entry)
            continue

        if command == "d":
            undo_stack.append(
                {
                    "key": key,
                    **capture_entry_state(left_entry, "left"),
                    **capture_entry_state(right_entry, "right"),
                }
            )
            copy_entry_fields(right_entry, left_entry)
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
        description="Compare two name_map YAML files and show differing as_type/as_variable/overrides values for shared keys.",
    )
    parser.add_argument("left", type=Path, help="Path to the first name_map YAML file")
    parser.add_argument("right", type=Path, help="Path to the second name_map YAML file")
    parser.add_argument(
        "--choose",
        action="store_true",
        help="Interactive mode to choose left/right values, undo decisions, and write both files.",
    )
    return parser


class MapDiffCommand:
    name = "name-map-diff"
    help = "Compare two naming maps and show differing values for shared keys."

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        configured = build_parser()
        parser.description = configured.description
        for action in configured._actions:
            if action.dest == "help":
                continue

            action_class_name = action.__class__.__name__
            is_store_true = action_class_name == "_StoreTrueAction"
            is_store_false = action_class_name == "_StoreFalseAction"

            if action.option_strings:
                # For optional arguments
                kwargs = {
                    "dest": action.dest,
                    "help": action.help,
                }

                # Store true/false actions don't support certain kwargs
                if not (is_store_true or is_store_false):
                    kwargs["default"] = action.default
                    kwargs["required"] = action.required
                    if getattr(action, "metavar", None) is not None:
                        kwargs["metavar"] = action.metavar
                    if getattr(action, "choices", None) is not None:
                        kwargs["choices"] = action.choices
                    if getattr(action, "nargs", None) is not None:
                        kwargs["nargs"] = action.nargs
                    if getattr(action, "type", None) is not None:
                        kwargs["type"] = action.type
                    if getattr(action, "const", None) is not None:
                        kwargs["const"] = action.const

                # Set action appropriately
                if is_store_true:
                    parser.add_argument(*action.option_strings, action="store_true", **kwargs)
                elif is_store_false:
                    parser.add_argument(*action.option_strings, action="store_false", **kwargs)
                else:
                    parser.add_argument(*action.option_strings, **kwargs)
            else:
                # For positional arguments
                kwargs = {
                    "help": action.help,
                }
                if getattr(action, "default", None) is not None:
                    kwargs["default"] = action.default
                if getattr(action, "metavar", None) is not None:
                    kwargs["metavar"] = action.metavar
                if getattr(action, "choices", None) is not None:
                    kwargs["choices"] = action.choices
                if getattr(action, "nargs", None) is not None:
                    kwargs["nargs"] = action.nargs
                if getattr(action, "type", None) is not None:
                    kwargs["type"] = action.type
                parser.add_argument(action.dest, **kwargs)

    def run(self, args: argparse.Namespace) -> int:
        forwarded = [str(args.left), str(args.right)]
        if args.choose:
            forwarded.append("--choose")
        return main(forwarded)


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
    console.print(f"Differences in as_type/as_variable/overrides: [bold]{len(differences)}[/bold]")

    if not differences:
        console.print("[bold green]No differences found for shared keys.[/bold green]")
        return 0

    print_diff_table(console, differences, left_label, right_label)
    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
