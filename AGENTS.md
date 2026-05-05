# AGENTS.md

Your role is that of a helpful assistant to aid in the renaming of obtuse register and peripheral names to more human readable ones. You will be given an SVD file that will be converted to many individual yaml files. Each yaml file will have a list of registers. You will be given a _renaming map_ which will have the current name, the new type, the new variable name, and the context (where this register is used). You should use this information to rename the registers and peripherals to be more human readable format. You should also avoid redundant naming and expand common shortenings. You should also follow the boundaries outlined below.

## Process

The data flow will operate as follows:

- .SVD file is converted to yaml files using `transmogrify.py`
- the individual peripherals are then generated using the `peripheralyzer.py` which will read the yaml files, and the renaming map with the templates desired, then write the new yaml files with the new names. The .SVD file is never altered, only the yaml files are altered.
- As names in the naming maps are changed, the peripheral yaml files used to run the generation through the templates again and again until the names are satisfactory. Point out which register names are still not renamed and are still obtuse to get a sense of progress. The naming map is the source of truth for the names, so if a name is not in the naming map, it will not be renamed. The naming map should be updated with the new names and types as they are changed, and then the generation should be run again to update the generated files with the new names.

## Environment

Use any local `venv` in this folder to run the scripts.

## Boundaries

- **Never** alter the .SVD files. Only the human should do this as it can have serious consequences for generation.
- **Never** alter the key names in the naming map yaml. These are used by the tool to identify which registers to rename, so altering these will break the tool. Only alter the `as_type` and `as_variable` fields to change the names and types of the registers. The `context` field is only for reference and should not be altered.
- **Never** use C/C++ keywords as the name of a variable or type.
- **Always** keep local project output separate from each other in the `out/` directory. This is to avoid collision of similar projects and to keep source files separate from generated files. Neither `out/` files or source files will be committed to this repo, only templates and scripts.
- **Prefer** to rename obtuse register names to be simple to understand. If a register is named `CR` that is _usually_ the `Control` register (ask when uncertain). So the type should be `Control` and the variable should be `control`. Namespacing/Scoping will make it clear which Peripheral this belongs to. Types should be capitalized and variables should be lowercase. If the name is already clear, then you can leave it as is.
- **Prefer** to make variables in the union lower case and used _to separate words. For example: `hsienable` => `high_speed_internal_oscillator_enable`. This is to make it clear that it's a variable and not a type, and to make it more readable. Types should be in CamelCase and variables should be in snake_case. The only exception is for existing acronyms which are commonly used in the industry like `AHB` or `APB`, which should be left as is (this is due to the expansions being too long and not adding much value, and the existing acronyms being well known in the industry).
- **Avoid** redundant naming. `CR` => `Control` not `ControlRegister`. The register part is obvious based on the size of the type. Similarly, don't name the peripheral with `Peripheral` unless it's in the normally used acronym like SPI.
- **Prefer** to expand common shortenings like the following to their longer names when naming peripherals or enumeration values, but not for variables or bits:
  - `SPI` => `SerialPeripheralInterface`
  - `I2C` => `InterIntegratedCircuit`
  - `UART` => `UniversalAsynchronousReceiverTransmitter`
  - `DMA` => `DirectMemoryAccess`
  - `GPIO` => `GeneralPurposeInputOutput`
  - `NVIC` => `NestedVectorInterruptController`
  - `EXTI` => `ExternalInterrupt`
  - `RCC` => `ResetAndClockControl`
- **Prefer** to keep short names like `i2c`, `i2s`, `ahb`, or `apb` for variable names and bits as they are frequently in other peripherals like the clock setup and the muxes.

## Glossary

- i2s = Inter-Integrated Circuit Sound
- mco = Microcontroller Clock Out

