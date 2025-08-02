# Base Code Copy Fix

## Issue
The server was not copying the memory and perception subdirectories from base_code_template to agent directories on startup. This caused ModuleNotFoundError when agents tried to import from these modules.

## Root Cause
The `_copy_agent_base_code` method in `sandbox.py` was only copying `*.py` files using `glob("*.py")`, which doesn't include subdirectories.

## Fix Applied
Updated the method to:
1. First copy all .py files in the root directory
2. Then iterate through all subdirectories and copy them using `shutil.copytree()`
3. Skip hidden directories (starting with '.')
4. Remove existing subdirectories before copying to ensure clean updates

## Code Changes
```python
# Old: Only copied *.py files
for py_file in template_dir.glob("*.py"):
    dst_file = base_code_dir / py_file.name
    shutil.copy2(py_file, dst_file)

# New: Copies entire directory structure
# First copy all .py files in the root
for py_file in template_dir.glob("*.py"):
    dst_file = base_code_dir / py_file.name
    shutil.copy2(py_file, dst_file)

# Then copy all subdirectories
for subdir in template_dir.iterdir():
    if subdir.is_dir() and not subdir.name.startswith('.'):
        dst_subdir = base_code_dir / subdir.name
        if dst_subdir.exists():
            shutil.rmtree(dst_subdir)
        shutil.copytree(subdir, dst_subdir)
```

## Result
Now when the server starts or creates new agents, it will properly copy:
- All .py files in the root of base_code_template
- The memory/ directory with all its modules
- The perception/ directory with all its modules
- Any other subdirectories added in the future

This ensures agents have access to the complete memory system.