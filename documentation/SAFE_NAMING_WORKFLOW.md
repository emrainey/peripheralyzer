# Safe Naming Map Workflow

## The Problem (FIXED)

Previously, when `transmogrify.py` ran, it would:
1. Load your naming map with custom renames
2. Discover new registers/fields in the SVD file that weren't in the map
3. Auto-create default entries for them in memory
4. Overwrite your entire naming map file with everything (custom + auto-generated)

This made it feel like your progress was being erased—it wasn't, but it was mixed with hundreds of newly auto-generated defaults.

## The Solution (NEW BEHAVIOR)

Now `transmogrify.py` **preserves your existing renames** and **writes new entries separately**:

### Step 1: Run transmogrify (Default Behavior)

```bash
./svd.sh
# OR
transmogrify.py -s STM32H753.svd -nm STM32H753_name_map.yml ...
```

**What happens:**
- ✓ Your existing naming map entries are **never touched**
- ✓ New registers discovered in the SVD are written to `STM32H753_name_map_new_entries.yml`
- ✓ You see a message like:
  ```
  ✓ Discovered 247 new entries
    New entries saved to: STM32H753_name_map_new_entries.yml
    Review and rename them, then merge into: STM32H753_name_map.yml
  ```

### Step 2: Review and Rename New Entries

Open the `_new_entries.yml` file and rename the entries according to your conventions:

```yaml
# STM32H753_name_map_new_entries.yml
CTRL:
  as_type: CTRL              # ← Change to more descriptive name
  as_variable: ctrl
  context:
  - SPI1.CR1

# becomes:

CTRL:
  as_type: Control           # ← Clear, meaningful name
  as_variable: control
  context:
  - SPI1.CR1
```

### Step 3: Merge When Ready

```bash
python3 -m peripheralyzer name-map merge STM32H753_name_map.yml
```

**Options:**
- `--backup` - Create a backup before merging
- `--dry-run` - Preview what would be merged
- `--new-entries FILE` - Specify a custom new entries file

### Step 4: Verify and Regenerate

```bash
# Verify the merged map is healthy
python3 -m peripheralyzer name-map verify STM32H753_name_map.yml

# Regenerate peripherals with the updated names
./svd.sh
```

## Why This Approach is Better

✓ **Your progress is never lost** - Renamed entries stay renamed
✓ **Clear separation** - New entries are in a separate file
✓ **You control the pace** - Rename at your convenience
✓ **Merge on your terms** - Only merge when entries are satisfactory
✓ **Trackable progress** - Each `_new_entries.yml` file shows what's still to be renamed

## Use Cases

### Case 1: New SVD Version Available
```bash
# Get latest SVD with new peripheral
transmogrify.py -s STM32H753_latest.svd ...
# OR
python3 -m peripheralyzer transmogrify -s STM32H753_latest.svd ...
# → STM32H753_name_map_new_entries.yml appears

# Rename 50 new entries
# Merge when done
python3 -m peripheralyzer name-map merge STM32H753_name_map.yml

# All old names preserved, only new ones added
```

### Case 2: Incremental Renaming
```bash
# Day 1: Just need the code, skip renaming
python3 -m peripheralyzer transmogrify ...  # Creates _new_entries.yml

# Day 2: Rename 100 entries in the new file
# Batch rename using your editor's find-replace

# Day 3: Merge and regenerate
python3 -m peripheralyzer name-map merge STM32H753_name_map.yml
python3 -m peripheralyzer transmogrify ...
```

### Case 3: Revert a Merge
```bash
# If you merged something you didn't like:
cp STM32H753_name_map.backup.yml STM32H753_name_map.yml

# The new entries file is deleted after merge,
# so re-run transmogrify to regenerate it:
python3 -m peripheralyzer transmogrify ...
```

## Command-Line Flags

### Preserve Mode (Default - RECOMMENDED)
```bash
python3 -m peripheralyzer transmogrify ... --preserve-name-map
# (enabled by default)
```
- Existing entries: NOT modified
- New entries: Saved to separate file
- Name map file size: Stays the same (only adds new_entries file)

### Legacy Mode (Old Behavior)
```bash
python3 -m peripheralyzer transmogrify ... --expand-name-map
```
- Existing entries: May be modified if context changes
- New entries: Added directly to main map
- Name map file size: Grows with each run
- ⚠️ Not recommended, but available for backward compatibility

## Tools Reference

### `name-map merge`
Merge `_new_entries.yml` into main map
```bash
python3 -m peripheralyzer name-map merge STM32H753_name_map.yml [--backup] [--dry-run]
```

### `name-map verify`
Check for syntax errors and C++ keyword issues
```bash
python3 -m peripheralyzer name-map verify STM32H753_name_map.yml
```

### `name-map track`
See exactly what changed between runs
```bash
python3 -m peripheralyzer name-map track STM32H753_name_map.yml --before --backup
# ... run transmogrify ...
python3 -m peripheralyzer name-map track STM32H753_name_map.yml --after
```

## Quick Reference Workflow

```bash
# 1. Run transmogrify (will create _new_entries.yml if needed)
./svd.sh

# 2. If new entries exist, rename them
# (Open STM32H753_name_map_new_entries.yml in your editor)

# 3. Merge when ready
python3 -m peripheralyzer name-map merge STM32H753_name_map.yml --backup

# 4. Verify and regenerate
python3 -m peripheralyzer name-map verify STM32H753_name_map.yml
./svd.sh

# 5. Done! Your peripheral code is generated with proper names
```

## FAQ

**Q: Can I undo a merge?**
A: Yes, if you used `--backup`, run:
```bash
cp STM32H753_name_map.backup.yml STM32H753_name_map.yml
```

**Q: What if I want to start fresh?**
A: Back up your custom names, then delete the main map to regenerate from scratch:
```bash
cp STM32H753_name_map.yml STM32H753_name_map.old.yml
rm STM32H753_name_map.yml
python3 -m peripheralyzer transmogrify ...  # Creates new default map
```

**Q: Can I rename entries after merging?**
A: Yes, just edit the main map directly and re-run transmogrify.

**Q: How big can a naming map get?**
A: With preserve mode, only as large as your custom renames + one merge of new entries. No artificial bloat.

**Q: What if I'm happy with default names?**
A: Just run merge without editing the `_new_entries.yml` file—the defaults are already reasonable.
