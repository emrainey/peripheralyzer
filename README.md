# peripheralyzer

A Python based Jinja System for creating C++ Headers or C Headers for Embedded Programming of memory mapped peripherals.

```
  ┌──────┐ transmogrify.py  ┌────────┐ peripheralyzer.py   ┌──────────┐ OK? ┌──────┐
  │ .SVD ├─────────┬───────►│ __.yml ├───▲────────────────►│_.hpp/cpp ├────►│ Done │
  └──────┘         │        └────────┘   │                 └────┬─────┘     └──────┘
                   │        ┌────────┐   │                      │
                   └───────►│name_map┼───┘                      │
                            └────────┘                          ▼
                                 ▲                            Confusing
                                 └───────────────────────────  Names?

```

## Setup

```bash
python3 -v venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install jinja2 pyyaml rich cmsis-svd
```

## Step One

`transmogrify.py` allows you to convert CMSIS SVD files into the yaml format that the `peripheralyzer.py` supports. You can get SVD files from ARM or the Vendor. The description of what a SVD could contain is [here](https://www.keil.com/pack/doc/CMSIS/SVD/html/index.html).

```bash
python3 transmogrify.py -s STM32F407.svd -yr out/stm32f4xx -ns stm32 -ns f4xx -nm STM32F407_name_map.yml
#
python3 transmogrify.py -s STM32H753.svd -yr out/stm32h7xx -ns stm32 -ns h7xx -nm STM32H753_name_map.yml
```

This will arrange all peripherals into the `cmsis::stm32` namespace in C++ (after the next step). This will also emit a _renaming map_ which will maps the weird CMSIS names like `DADDR` to reasonable names like `DestinationAddress`. Merely change all the names _and types_ you'd like and re-run the transmogrify step, as it will read the file in before processing, then use it, then write it back out.

An example of the naming map file:

```yaml
ACTIVE:
  as_type: ACTIVE
  as_variable: active
  context:
  - NVIC.IABR0
  - NVIC.IABR1
  - NVIC.IABR2
```

If a short name is reused for different meanings on different peripherals, you can keep a default name and add scoped `overrides` keyed by the register or bitfield context.

```yaml
PE:
  as_type: PeripheralEnable
  as_variable: peripheral_enable
  overrides:
    UART*.SR:
      as_type: ParityError
      as_variable: parity_error
    USART*.SR:
      as_type: ParityError
      as_variable: parity_error
  context:
  - I2C1.CR1
  - I2C2.CR1
  - I2C3.CR1
  - UART4.SR
  - USART1.SR
```

`context` is still recorded as before. The top-level `as_type` and `as_variable` remain the default fallback, and any matching override takes precedence for that specific context.

### Name Map Utilities

`map_diff.py` compares two naming maps and shows keys where `as_type`, `as_variable`, or transferable `overrides` differ.

When copying from one map to another with `--choose`, `overrides` are filtered to only the patterns that match `context` values present on the destination device. This prevents carrying over override rules for peripherals, registers, or bits that do not exist on the other map.

```bash
python3 map_diff.py STM32F407_name_map.yml STM32H753_name_map.yml
```

If you want to interactively copy values from one side to the other and write both files back out, use `--choose`.

```bash
python3 map_diff.py STM32F407_name_map.yml STM32H753_name_map.yml --choose
```

`peripheral_duplicate_finder.py` scans a generated yaml folder and reports peripherals that have the same shape and may be reducible to a shared type.

```bash
python3 peripheral_duplicate_finder.py out/stm32/f4xx/ymls
python3 peripheral_duplicate_finder.py out/stm32/h7xx/ymls
```

If multiple duplicate groups would collide on the same shared name, the script suggests a disambiguated name such as `TIM_1_8` or `TIM_2_3_4_5_12_13_14`.

## Step Two

`peripheralyzer.py` allows you to convert from _something_ like this:

```yaml
include_lock: TEST_H_
includes:
- <cstdint>
namespaces:
- testing
peripheral:
    name: Test
    sizeof: 0x10
    default_type: std::uint32_t
    default_depth: 32
    members:
        - name: first
          type: std::uint8_t
          offset: 0x0
          count: 4
          sizeof: 4
        - name: second
          offset: 0x4
        - name: third
          type: float
          offset: 0x8
          sizeof: 4
        - name: fourth
          type: std::uint16_t
          offset: 0xC
          count: 2
          sizeof: 4
```

Into C++ Peripherals, Registers, and Enumerations with proper include name locks, namespaces, bitfield unions, and static_asserts for all field offsets and `sizeof`s.

The YAML is organized into a hierarchy of:

* Peripherals
  * [optional] Enumerations
  * [optional] Structures
  * Registers
    * [optional] Enumerations
    * (bit) Fields Structure

Each of these is scoped within it's container.

This is an example of a generated structure.

```cpp
#ifndef TEST_H_
#define TEST_H_
/// @file
/// Auto Generated Structure Definitions for Test from the Peripheralyzer.
/// @copyright
#include <cstdint>
namespace testing {
struct Test final {
    std::uint8_t first[4]; // offset 0x0UL
    std::uint32_t second; // offset 0x4UL
    float third; // offset 0x8UL
    std::uint16_t fourth[2]; // offset 0xcUL
};
// Ensure the structure is in standard layout format
static_assert(std::is_standard_layout<Test>::value, "Must be standard layout");
// Ensure the offsets are all correct
static_assert(offsetof(Test, first) == 0x0UL, "Must be located at this offset");
static_assert(offsetof(Test, second) == 0x4UL, "Must be located at this offset");
static_assert(offsetof(Test, third) == 0x8UL, "Must be located at this offset");
static_assert(offsetof(Test, fourth) == 0xcUL, "Must be located at this offset");
// Ensure the sizeof the entire structure is correct.
static_assert(sizeof(Test) == 0x10UL, "Must be this exact size");
}  // namespace testing
#endif // TEST_H_
```

The table below summarizes some of the differences of differences between the two generations.

| | C17 Code Generation | C++14 Code Generation |
|-|---------------------|-----------------------|
| Peripherals, Structures and Registers are `final` to prevent inheritance and `virtual` issues | -- | Yes |
| Peripherals, Structures, Enums and Registers namespace scoping | global | limited |
| Headers are `#ifndef` locked. No `pragma once` | Yes | Yes |
| Bitfields are `struct`ures contained within anonymous `union`s | Yes | Yes |
| Peripherals, Structures and Registers are `sizeof` and `offsetof` checked | Yes | Yes |
| Registers have `operator` overloads to make the load, modify, store cycle easier | -- | Yes |
| Registers have associated functions to make load, modify, store cycle easier but with null checks | Yes | No |
| `enum` can be typed | No | Yes |
| Generates Unit Tests for all fields in `union`s | Yes | Yes |
