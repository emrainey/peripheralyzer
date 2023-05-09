# peripheralyzer

A Python based Jinja System for creating C++ Headers for Embedded Programming

Converts this:

```yaml
---
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
        - name: fourth
          offset: 0xC
```

Into this (compacted for brevity):

```cpp
#ifndef TEST_H_
#define TEST_H_
/// @file
/// Auto Generated Structure Definitions for Test from the Peripheralyzer.
/// @copyright
#include <cstdint>
namespace testing {
struct __attribute__((packed)) Test final {
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

It can also generate bitfields for registers and enumerations for types used in both bitfields and in members.
