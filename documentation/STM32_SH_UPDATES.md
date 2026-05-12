# stm32.sh - Enhanced with Safe Naming Map Workflow

## What Changed

Your `stm32.sh` script now integrates the safe naming map mechanism with helpful status messages.

## What You'll See

When you run `./stm32.sh`, after each device is processed, you'll see something like:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ New register names discovered: 247 entries
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Location: STM32F407_name_map_new_entries.yml

NEXT STEPS:
  1. Review and rename entries in: STM32F407_name_map_new_entries.yml
  2. Merge when ready: python3 -m peripheralyzer name-map merge STM32F407_name_map.yml --backup
  3. Re-run this script to regenerate code with updated names

For more info: cat SAFE_NAMING_WORKFLOW.md
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

And at the end, a summary:

```
╔════════════════════════════════════════════════════════════════╗
║                     BUILD COMPLETE                             ║
╚════════════════════════════════════════════════════════════════╝

📋 PENDING NAMING UPDATES:

  • STM32F407_name_map_new_entries.yml (review and rename)
  • STM32H753_name_map_new_entries.yml (review and rename)

📚 Workflow: cat SAFE_NAMING_WORKFLOW.md
🔗 Merge: python3 -m peripheralyzer name-map merge <device>_name_map.yml --backup
```

Or if everything is already renamed:

```
╔════════════════════════════════════════════════════════════════╗
║                     BUILD COMPLETE                             ║
╚════════════════════════════════════════════════════════════════╝

✓ No new naming entries - all registers have been renamed!
```

## New Features

✅ **`check_new_entries()` function** - Displays stats and guidance after each device
✅ **Entry count** - Shows how many new entries were discovered
✅ **Next steps** - Clear instructions on what to do
✅ **Summary report** - At the end, shows all pending naming updates
✅ **Error handling** - Uses `set -e` to exit on errors

## Typical Workflow

```bash
# 1. Run the build (includes checking for new entries)
./stm32.sh

# 2. If new entries exist, rename them
vim STM32F407_name_map_new_entries.yml
vim STM32H753_name_map_new_entries.yml

# 3. Merge when done
python3 -m peripheralyzer name-map merge STM32F407_name_map.yml --backup
python3 -m peripheralyzer name-map merge STM32H753_name_map.yml --backup

# 4. Re-run to regenerate with updated names
./stm32.sh

# 5. Done!
```

## When You See Nothing

If `check_new_entries()` doesn't display a message after an `svd.sh` call, it means:
- ✓ No new entries were discovered
- ✓ All registers in the SVD are already named in your map
- ✓ Safe to continue with code generation

## Going Deeper

For complete details on the naming workflow, see: [SAFE_NAMING_WORKFLOW.md](SAFE_NAMING_WORKFLOW.md)
