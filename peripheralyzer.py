#!/usr/bin/env python3

import os
import re
import sys
import yaml
import jinja2
import typing
import argparse
import collections

# global verbose flag
verbose: bool = False
# global use named reserved fields
use_named_reserved: bool = False


def camel_to_snake_case(CamelCaseString: str) -> str:
    """
    Convert a string with camel case words to a string with snake case words.
    (ChatGPT)
    """
    # Find all instances of a capital letter and replace with a `_<letter>`
    snake_string = re.sub("([A-Z])", r"_\1", CamelCaseString)
    # Convert the string to lowercase and remove any leading '_'
    snake_string = snake_string.lower().lstrip("_")
    return snake_string


def validate_structure(structure: typing.Dict[str, str]) -> None:
    """Validates the Structure Definition

    Args:
        structure (typing.Dict[str, str]): The structure to validate
    """
    assert "name" in structure
    assert "sizeof" in structure
    assert "default_depth" in structure
    assert "default_type" in structure
    assert "members" in structure


def validate_register(register: typing.Dict[str, str]) -> None:
    assert "name" in register
    assert "default_depth" in register
    assert "default_type" in register
    assert "fields" in register
    assert "sizeof" in register


def validate_member(member: typing.Dict[str, str]) -> None:
    """Validates the member entry"""
    assert "name" in member or "is_union" in member
    assert "offset" in member
    if "type" in member:
        assert "sizeof" in member, f"Missing sizeof in {member}"


def validate_field(field: typing.Dict[str, str]) -> None:
    assert "name" in field
    # assert "count" in field # not required, defaults to 1
    assert "offset" in field


def validate_enum(enumeration: typing.Dict[str, str]) -> None:
    assert "name" in enumeration
    assert "type" in enumeration
    assert "symbols" in enumeration


def validate_symbol(symbol: typing.Dict[str, str]) -> None:
    assert "name" in symbol
    assert "value" in symbol
    # assert "comment" in symbol


class YamlLoader:
    def __init__(self, yaml_root: str) -> None:
        """A Yaml Loader which prevents loading the same file twice.

        Args:
            yaml_root (str): The root directory to look for yaml files.
        """
        self.yaml_root = yaml_root
        self.loaded_files = dict()

    def load(self, filename: str) -> typing.Optional[typing.Dict[str, str]]:
        if self.yaml_root is not None:
            filepath = os.path.join(self.yaml_root, filename)
        else:
            filepath = filename
        if filepath not in self.loaded_files:
            if verbose:
                print(f"Loading {filepath}")
            assert os.path.exists(filepath), f"File {filepath} must exist (yaml_root={self.yaml_root})"
            with open(filepath, "r") as file:
                return yaml.load(file, Loader=yaml.SafeLoader)
            return None
        else:
            raise Exception(f"Already loaded file {filepath}. There's probably a circular link.")


def pad_members(
    members: typing.List[typing.Dict[str, str]], default_type: str, member_sizeof: int, start: int, limit: int
) -> int:
    """Pads a structure with extra members for the exact number of elements."""
    count = int(start)
    while count < limit:
        if use_named_reserved:
            bytes_diff = int(limit - count)
            unit_diff = int(bytes_diff / member_sizeof)
            reserved = {
                "type": default_type,
                "name": f"_reserved_{hex(count)}",
                "count": unit_diff,
                "offset": f"{hex(count)}",
            }
            # we intentionally compute this so that if there are gaps, the compiler will catch it
            count = int(count + int(unit_diff * member_sizeof))
        else:
            reserved = {"type": default_type, "name": "", "count": 1, "offset": f"{hex(count)}"}
            count = int(count + member_sizeof)
        if verbose:
            print(f"Padding member {reserved}")
        members.append(reserved)
    return count


def pack_members(
    old_members: typing.List[typing.Dict[str, str]], depth: int, default_type: str, sizeof: int
) -> typing.List[typing.Dict[str, str]]:
    """Packs the members of a Structure"""
    # first reorder the list based on the offsets
    sorted_members = sorted(old_members, key=lambda m: int(m["offset"], 0))
    members = list()
    count = int(0)
    member_sizeof = int(depth / 8)
    for member in sorted_members:
        validate_member(member)
        # get the next offset
        offset = int(member["offset"], 0)
        # while we need to add some padding
        count = pad_members(members, default_type, member_sizeof, count, offset)
        if "type" not in member:
            member["type"] = default_type
        if "count" not in member:
            member["count"] = 1
        if "comment" not in member:
            member["comment"] = "FIXME (comment)"
        if "sizeof" not in member:
            member["sizeof"] = member_sizeof
        count = int(offset + int(member["sizeof"], 0))
        member["offset"] = hex(offset)
        if verbose:
            print(f"Adding member {member}")
        members.append(member)
    count = pad_members(members, default_type, member_sizeof, count, sizeof)
    return members


def pad_fields(
    fields: typing.List[typing.Dict[str, str]], default_type: str, depth: int, start: int, limit: int
) -> int:
    """Creates a padding entry in a bit field"""
    index = int(start)
    while index < limit:
        diff = int(limit - index)
        reserved = {"name": "", "type": default_type, "count": diff, "offset": index, "comment": "(reserved)"}
        index = int(index + diff)
        if verbose:
            print(f"Padding field {reserved}")
        fields.append(reserved)
    return index


def pack_fields(
    old_fields: typing.List[typing.Dict[str, str]], depth: int, default_type: str, sizeof: int
) -> typing.List[typing.Dict[str, str]]:
    """Packs the fields of the register"""
    # sort the fields based on offset
    sorted_fields = sorted(old_fields, key=lambda f: int(f["offset"]))
    # create the list and the index
    fields = list()
    # we start at the bottom of the fields
    index = int(0)
    for field in sorted_fields:
        validate_field(field)
        # get the next bit offset in the field
        offset = field["offset"]
        # create bit padding up to this offset if needed
        index = pad_fields(fields, depth=depth, default_type=default_type, start=index, limit=offset)
        # if entries are missing assume defaults
        if "type" not in field:
            field["type"] = default_type
        if "comment" not in field:
            field["comment"] = "FIXME (comment)"
        if "count" not in field:
            field["count"] = 1
        count = int(field["count"])
        index = int(index + count)
        if verbose:
            print(f"Adding field {field}")
        fields.append(field)
    # add closing padding if needed
    count = pad_fields(fields, depth=depth, default_type=default_type, start=index, limit=depth)
    return fields


def process_enums(top: typing.Dict[str, str]) -> None:
    if "enums" in top:
        enums = list()
        for yml in top["enums"]:
            data = loader.load(yml)
            # if it's an integer type, but what if it's not?
            # data = sorted(data, key=lambda e: int(e["value"], 0))
            if verbose:
                print(f"Loading {data}")
            validate_enum(data)
            if "type" in data:
                type = data["type"]
                symbols = data["symbols"]
                for symbol in symbols:
                    if type == "char":
                        value = symbol["value"]
                        symbol["value"] = f"'{value}'"
                    if "comment" not in symbol:
                        symbol["comment"] = "FIXME (comment)"
            enums.append(data)
        top["enums"] = enums


def process_register(top: typing.Dict[str, str]) -> None:
    if "registers" in top:
        registers = list()
        for yml in top["registers"]:
            # FIXME parse enums
            reg = loader.load(yml)
            if verbose:
                print(f"Loaded {reg}")
            validate_register(reg)
            reg["fields"] = pack_fields(
                old_fields=reg["fields"],
                depth=int(reg["default_depth"]),
                default_type=reg["default_type"],
                sizeof=int(reg["sizeof"]),
            )
            # registers can not have sub structures but they can have enums
            process_enums(reg)
            registers.append(reg)
        top["registers"] = registers


def process_structure(top: typing.Dict[str, str]) -> None:
    if "structures" in top:
        structures = list()
        for yml in top["structures"]:
            sub = loader.load(yml)
            if verbose:
                print(f"Loaded {sub}")
            validate_structure(sub)
            sub["members"] = pack_members(
                old_members=sub["members"],
                depth=int(sub["default_depth"]),
                default_type=sub["default_type"],
                sizeof=int(sub["sizeof"]),
            )
            # each structure can have sub-structures, registers and enums
            process_enums(sub)
            process_structure(sub)
            process_register(sub)
            sub["sizeof"] = hex(sub["sizeof"])  # replace with hex value
            structures.append(sub)
        top["structures"] = structures


def main(argv: typing.List[str]) -> int:
    parser = argparse.ArgumentParser("A simple tool to emit peripheral definitions using Jinja.")
    parser.add_argument("-b", "--banner", action="store_true", help="Prints a sick banner.")
    parser.add_argument("-t", "--template", type=str, action="append", help="The template to use to generate the code.")
    parser.add_argument("-y", "--yaml", type=str, action="append", help="The yaml description of the peripheral set.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Prints verbose information")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        action="store",
        default=os.getcwd(),
        help="[optional] the output path if given (default:%(default)s)",
    )
    parser.add_argument(
        "-tr",
        "--template-root",
        type=str,
        action="store",
        default=os.path.join(os.getcwd(), "templates"),
        help="The location where the templates are kept (default=%(default)s)",
    )
    parser.add_argument(
        "-yr",
        "--yaml-root",
        type=str,
        action="store",
        default=None,
        help="The root to the location where the yamls are kept",
    )
    parser.add_argument("-a", "--anonymous", action="store_true", help="Disables padding with named reserved fields")
    args = parser.parse_args()

    if args.banner:
        print(
            """
__________             .__       .__                 .__       .__
\______   \ ___________|__|_____ |  |__   ___________|__|____  |  | ___.__.________ ___________
 |     ___// __ \_  __ \  \____ \|  |  \_/ __ \_  __ \  \__  \ |  |<   |  |\___   // __ \_  __ \\
 |    |   \  ___/|  | \/  |  |_> >   Y  \  ___/|  | \/  |/ __ \|  |_\___  | /    /\  ___/|  | \/
 |____|    \___  >__|  |__|   __/|___|  /\___  >__|  |__(____  /____/ ____|/_____ \\___  >__|
               \/         |__|        \/     \/              \/     \/           \/    \/
"""
        )

    verbose = args.verbose or False  # in case it comes back None
    if args.anonymous is not None:
        use_named_reserved = not args.anonymous
    global loader  # declare globally
    loader = YamlLoader(args.yaml_root)

    # Takes the dictionary and emit through the templates
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(args.template_root))
    env.filters["debug"] = lambda x: print(x) or x
    env.filters["list"] = list
    env.filters["conjoin"] = lambda ns: f"{ns}::"
    env.filters["snake_case"] = camel_to_snake_case

    count = 0
    for yml in args.yaml:
        data = loader.load(yml)
        # validate keys
        assert "peripheral" in data
        peripheral = data["peripheral"]
        validate_structure(peripheral)

        # convenience variables
        default_type = peripheral["default_type"]
        depth = int(peripheral["default_depth"])
        sizeof = int(peripheral["sizeof"], 0)
        bytes_per_unit = int(depth / 8)

        # process the peripheral's enums, structures and registers
        process_enums(peripheral)
        process_structure(peripheral)
        process_register(peripheral)

        # replace the members in the top level peripheral
        peripheral["members"] = pack_members(
            old_members=peripheral["members"], depth=depth, default_type=default_type, sizeof=sizeof
        )
        peripheral["sizeof"] = hex(sizeof)

        for template_file in args.template:
            template_path = os.path.join(args.template_root, template_file)
            if not os.path.exists(template_path):
                print(f"Template {template_path} not found.")
                return -1
            with open(template_path, "r") as file:
                template_data = file.read()
                template_name, template_ext, _ = os.path.basename(template_path).split(".")
                file.close()
                template = env.from_string(template_data)
                peripheral_name = peripheral["name"]
                filename = f"{peripheral_name}.{template_ext}"
                if not os.path.exists(args.output):
                    os.mkdir(args.output)
                filepath = os.path.join(args.output, filename)
                with open(filepath, "w+") as file:
                    file.write(template.render(data))
                if verbose:
                    print(template.render(data))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
