# peripheralyzer

A Python based Jinja System for creating C++ Headers for Embedded Programming

## Step One

`transmogrify.py` allows you to convert CMSIS SVD files into the yaml format that the `peripheralyzer.py` supports. You can get SVD files from ARM. The description of what a SVD could contain is [here](https://www.keil.com/pack/doc/CMSIS/SVD/html/index.html).

```
python3 transmogrify.py -s STM32F407.svd -yr svd -ns cmsis -ns stm32 -nm STM32F407_name_map.yml
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

The project follows some policies about C++ generation as well:

* All Peripherals and Registers are `final`
* All sizes and offsets are statically asserted.
* All headers are include locked
* All bitfields are part of a union which is paired with a unit type for the register. A unit test can be generated to ensure that the union works on target as intended.
* All registers will have `operator` overloads.
  * to allow assignment to and from `const` and `volatile` instances
