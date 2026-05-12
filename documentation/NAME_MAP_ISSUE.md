# Why Your Naming Map Gets Wiped Out

## Root Cause

The naming map is being modified and rewritten by **transmogrify.py** during SVD processing. Here's the exact sequence:

### The Problem Flow

1. **transmogrify.py starts** (line 361)
   - Loads your naming map into the `NameMapper` class
   - Example: 1,000 entries you've carefully renamed

2. **During SVD processing**
   - As the script iterates through registers, fields, and enums from the SVD file
   - It calls `mapper.lookup(name, context)` to look up each register/field name
   - **If a name isn't in the map, `lookup()` creates it** (lines 75-81 in transmogrify.py):
     ```python
     if name not in self._name_map.keys():
         self._name_map[name] = {
             "as_type": name,
             "as_variable": name.lower(),
             "context": [context],
         }
     ```
   - This adds NEW entries with default names (no renaming applied)

3. **transmogrify.py finishes** (line 529)
   - Calls `mapper.dump()` which **overwrites the entire naming map file**
   - All the auto-generated default entries are now saved to disk
   - **Your custom renames are preserved, but now you have hundreds of new entries you haven't renamed yet**

### Why It Feels Like Erasure

The issue is **not that your edits are deleted** — they're still there. But:
- You may see the file expand with tons of new un-renamed entries
- If the YAML format changes slightly during the dump, you might lose formatting
- You have to keep re-running the renaming process as new registers appear

## Solutions

### Option 1: Track Changes (Recommended)

Use the new `name-map track` command to see exactly what transmogrify.py is adding:

```bash
# Before running transmogrify
python3 -m peripheralyzer name-map track STM32H753_name_map.yml --before --backup

# Run transmogrify
python3 -m peripheralyzer transmogrify ...

# Check what changed
python3 -m peripheralyzer name-map track STM32H753_name_map.yml --after
```

This will show you:
- How many entries were added
- What entries were removed
- What entries were modified
- A backup file you can restore from

### Option 2: Prevent Auto-Population (Code Change)

**Edit transmogrify.py** to add a flag that prevents `lookup()` from auto-creating entries:

```python
# In NameMapper class, modify lookup() to:
def lookup(self, name: str, context: typing.Optional[str],
           create_if_missing: bool = True) -> typing.Dict[str, typing.Any]:
    if name not in self._name_map.keys():
        if create_if_missing:  # Only create if allowed
            self._name_map[name] = {
                "as_type": name,
                "as_variable": name.lower(),
                "context": [context],
            }
        else:
            # Return a default without adding to the map
            return {
                "as_type": name,
                "as_variable": name.lower(),
                "context": [context],
            }
    # ... rest of method
```

Then add `--no-expand-map` flag to prevent the map from growing.

### Option 3: Use Map Snapshots

Create immutable snapshots:

```bash
cp STM32H753_name_map.yml STM32H753_name_map.locked.yml
chmod 444 STM32H753_name_map.locked.yml  # Read-only
```

Then modify transmogrify.py to load from both files (locked + working).

### Option 4: Split Naming Maps

Separate your custom renames from auto-generated defaults:

- `STM32H753_name_map_custom.yml` - Only your edits (you manage)
- `STM32H753_name_map_auto.yml` - Auto-generated defaults (transmogrify manages)

Modify the code to load both and merge them (custom takes priority).

## Recommended Action

I recommend **Option 1 + Option 2** together:

1. Use `name-map track` to see what's happening
2. Add a flag to `transmogrify.py` to prevent auto-population of the map
3. Generate a separate file with missing entries that need naming

Would you like me to implement the code change to prevent auto-population?
