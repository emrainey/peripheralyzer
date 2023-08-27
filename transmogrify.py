#!/usr/bin/env python3

import os
import re
import sys
import yaml
import jinja2
import typing
import argparse
import collections

from cmsis_svd.parser import SVDParser


class NameMapper:
    def __init__(self, file_path: str) -> None:
        self._file_path = file_path
        self._name_map = dict()
        if os.path.exists(file_path):
            print(f"Loading {file_path}")
            with open(file_path, "r") as file:
                self._name_map = yaml.load(file, Loader=yaml.SafeLoader)
                if self._name_map is None:
                    self._name_map = dict()
                else:
                    # enforce that as_variable names are lower case
                    for name in self._name_map.keys():
                        self._name_map[name]["as_variable"] = self._name_map[name]["as_variable"].lower()

    def lookup(self, name: str, context: str) -> typing.Dict[str, str]:
        if name not in self._name_map.keys():
            self._name_map[name] = {"as_type": name, "as_variable": name.lower(), "context": [context]}
        if "context" in self._name_map[name]:
            if context and context not in self._name_map[name]["context"]:
                self._name_map[name]["context"].append(context)
        else:
            self._name_map[name]["context"] = [context]
        return self._name_map[name]

    def as_type(self, name: str, context: str = None) -> str:
        return self.lookup(name, context)["as_type"]

    def as_variable(self, name: str, context: str = None) -> str:
        return self.lookup(name, context)["as_variable"]

    def dump(self) -> None:
        print(f"Dumping {self._file_path}")
        with open(self._file_path, "w+") as file:
            yaml.dump(self._name_map, file)


# Maps short names to reasonable names
name_map = dict()
# {"CTRL": "control", "TYPER": "type", "RNR": "region_number", "RBAR": "base_address", "RASR": "access"}


def fix_name(name: str, prefix: str = None) -> str:
    if prefix is not None and name.startswith(prefix):
        name.removeprefix(prefix)
    if name in name_map:
        return name_map[name]
    else:
        return name


def fix_comment(comment: str) -> str:
    """Fixes the weird "\n         " gaps"""
    if comment is None:
        return ""
    new_comment = re.sub(r"\s+", " ", comment).strip()
    return new_comment


def fix_sizeof(sizeof) -> int:
    """Corrects sizeof oddities"""
    size = "0"
    if isinstance(sizeof, int):
        pass
    elif isinstance(sizeof, str):
        sizeof = int(sizeof, 0)
    if sizeof % 4 == 1:
        size = int(sizeof - 1)
    else:
        size = sizeof
    return size


class YamlDumper:
    def __init__(self):
        self._file_map = dict()

    def dump(self, data: typing.Dict[str, str], yaml_file_path: str) -> None:
        if verbose:
            print(f"{yaml.dump(data)}")
        # what should we do if there's two of the same name? how do we disambiguate against duplicates or just plain rewrites?
        if yaml_file_path in self._file_map:
            raise Exception(f"Duplicate name found! {yaml_file_path}")
        else:
            self._file_map[yaml_file_path] = True
        with open(yaml_file_path, "w+") as file:
            yaml.dump(data, file, Dumper=yaml.SafeDumper)


def main(argv: typing.List[str]) -> int:
    parser = argparse.ArgumentParser("A simple tool to convert SVD into peripheral yamls for peripheralyzer")
    parser.add_argument("-b", "--banner", action="store_true", help="Prints a sick banner.")
    parser.add_argument("-s", "--svd", type=str, action="store", help="The CMSIS SVD File")
    parser.add_argument(
        "-ns", "--namespace", type=str, action="append", help="The namespaces to use in the file (appendable)"
    )
    parser.add_argument(
        "-nm", "--name-map", type=str, action="store", default="name_map.yml", help="The dictionary of name mappings"
    )
    # parser.add_argument("-m", "--manufacturer", type=str, action="store", help="The part manufacturer")
    parser.add_argument(
        "-yr",
        "--yaml-root",
        type=str,
        action="store",
        default=os.getcwd(),
        help="The yaml output folder (default:%(default)s)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Prints verbose information")
    args = parser.parse_args(argv)

    global dumper
    dumper = YamlDumper()

    if args.banner:
        print(
            """
___________                                                       .__  _____
\__    ___/___________    ____   ______ _____   ____   ___________|__|/ ____\__.__.
  |    |  \_  __ \__  \  /    \ /  ___//     \ /  _ \ / ___\_  __ \  \   __<   |  |
  |    |   |  | \// __ \|   |  \\\\___ \|  Y Y  (  <_> ) /_/  >  | \\/  ||  |  \___  |
  |____|   |__|  (____  /___|  /____  >__|_|  /\____/\___  /|__|  |__||__|  / ____|
                      \/     \/     \/      \/      /_____/                 \/
"""
        )

    global verbose
    verbose = args.verbose or False

    if args.yaml_root:
        if not os.path.exists(args.yaml_root):
            os.mkdir(args.yaml_root)

    global mapper
    mapper = NameMapper(args.name_map)

    # create an instance of the SVDParser class from this file
    svd_parser = SVDParser.for_xml_file(args.svd)
    svd_device = svd_parser.get_device()

    default_type = f"uint{svd_device.width}_t"
    default_depth = int(svd_device.width)  # in bits
    default_sizeof = int(svd_device.width / svd_device.address_unit_bits)  # in bytes
    # change the dictionary over to the peripheralyzer format of yaml
    for svd_peripheral in svd_device.peripherals:
        # print(f"Peripheral {svd_peripheral.name}")
        data = dict()
        # parse for each register under the peripheral
        # parse for each enum anywhere

        data["peripheral"] = {
            "base": hex(svd_peripheral.base_address),
            "name": mapper.as_type(svd_peripheral.name),
            "comment": fix_comment(svd_peripheral.description) + f" ({svd_peripheral.name})",
            "default_type": default_type,
            "default_depth": default_depth,
            "sizeof": hex(int(fix_sizeof(svd_peripheral.address_block.size))),
            "registers": list(),
            "structures": list(),
            "members": list(),
        }
        offsets = {}
        for svd_register in svd_peripheral.registers:
            member = {
                "name": mapper.as_variable(svd_register.name, context=svd_peripheral.name),
                "comment": fix_comment(svd_register.description) + f" ({svd_register.name})",
                "type": mapper.as_type(svd_register.name, context=svd_peripheral.name),
                "count": 1,
                "offset": hex(svd_register.address_offset),
                "sizeof": hex(int(svd_register.size / svd_device.address_unit_bits)),  # it's in bits, convert to bytes
            }
            if member["offset"] not in offsets:
                offsets[member["offset"]] = [member]
            else:
                offsets[member["offset"]].append(member)

            register = {
                "name": mapper.as_type(svd_register.name, context=svd_peripheral.name),
                "comment": fix_comment(svd_register.description) + f" ({svd_register.name})",
                "default_depth": default_depth,
                "default_type": default_type,
                "sizeof": int(svd_register.size / svd_device.address_unit_bits),  # it's in bits, convert to bytes
                "fields": list(),
                "enums": list(),
            }
            for field in svd_register.fields:
                fld = {
                    "name": mapper.as_variable(field.name, context=f"{svd_peripheral.name}.{svd_register.name}"),
                    "offset": field.bit_offset,
                    "count": field.bit_width,
                    "comment": fix_comment(field.description) + f" ({field.name})",
                }
                if field.is_enumerated_type:
                    fld["type"] = mapper.as_type(field.name, context=f"{svd_peripheral.name}.{svd_register.name}")
                    enum = {
                        "name": mapper.as_type(
                            field.name,
                            context=f"{svd_peripheral.name}.{svd_register.name}.{field.name}",
                        ),
                        "comment": fix_comment(field.description) + f" ({field.name})",
                        "type": default_type,
                        "default_depth": default_depth,
                        "symbols": list(),
                    }
                    for enum_value in field.enumerated_values:
                        enum["symbols"].append(
                            {
                                "name": mapper.as_type(
                                    enum_value.name,
                                    context=f"{svd_peripheral.name}.{svd_register.name}.{field.name}.{enum_value.name}",
                                ),
                                "value": enum_value.value,
                                "comment": fix_comment(enum_value.description) + f" ({enum_value.name})",
                            }
                        )
                    # Add enum to Register
                    yaml_file = f"enum_{svd_peripheral.name}_{svd_register.name}_{field.name}.yml"
                    yaml_file_path = os.path.join(args.yaml_root, yaml_file)
                    register["enums"].append(yaml_file)
                    dumper.dump(enum, yaml_file_path)
                # Add field to Register
                register["fields"].append(fld)
            # Add Register to Peripheral
            yaml_file = f"register_{svd_peripheral.name}_{svd_register.name}.yml"
            yaml_file_path = os.path.join(args.yaml_root, yaml_file)
            data["peripheral"]["registers"].append(yaml_file)
            dumper.dump(register, yaml_file_path)

        for offset in offsets.keys():
            if len(offsets[offset]) > 1:
                max_sizeof = max(offsets[offset], key=lambda m: int(m["sizeof"], 0))["sizeof"]
                # print(f"Offset {offset} has multiple members {offsets[offset]}")
                data["peripheral"]["members"].append(
                    {"is_union": True, "offset": offset, "sizeof": max_sizeof, "members": offsets[offset]}
                )
            else:
                data["peripheral"]["members"].append(offsets[offset][0])

        # for block in svd_peripheral.address_block:
        #     print(f"block = {block}")
        yaml_file = f"peripheral_{svd_peripheral.name}.yml"
        yaml_file_path = os.path.join(args.yaml_root, yaml_file)
        # data["includes"] = ["<cstdint>", "<cstddef>", "<type_traits>"]
        if args.namespace:
            data["namespaces"] = args.namespace
        ns = "_".join(data["namespaces"])
        ph = data["peripheral"]["name"]
        data["include_lock"] = f"{ns}_{ph}_".upper()
        dumper.dump(data, yaml_file_path)

    # update the name map
    mapper.dump()

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
