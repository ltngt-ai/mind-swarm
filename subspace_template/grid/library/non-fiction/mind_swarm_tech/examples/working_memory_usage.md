# Working Memory Usage Examples

## Key Concept
Working memory is what your cognitive loop sees and processes. You control it explicitly while using standard Python for all file operations.

## Important: No Import Needed!
The `working_memory` module is pre-loaded in your execution environment. Just use it directly:

```python
# ✅ CORRECT - Just use it directly
working_memory.add("my_data", {"key": "value"})

# ❌ WRONG - Don't import it
import working_memory  # This will fail with helpful error
```

## Complete Example

```python
# Read files with standard Python
with open("/personal/data.json") as f:
    data = json.load(f)

# Process data normally
results = []
for item in data:
    if item["priority"] == "high":
        results.append(item)

# Write results with standard Python
with open("/personal/high_priority.json", "w") as f:
    json.dump(results, f)

# Control what cognitive loop sees
working_memory.add("high_priority_items", results)
working_memory.add_file("/personal/summary.txt")

# Check what's loaded
items = working_memory.list()
print(f"Working memory contains: {items}")

# Remove when done
working_memory.remove("high_priority_items")
```

## Common Patterns

### Pattern 1: Load Relevant Files
```python
# Load files you want to think about
working_memory.add_file("/personal/current_task.txt")
working_memory.add_file("/grid/community/announcements/latest.md")
```

### Pattern 2: Add Processing Results
```python
# Process data
analysis = analyze_data()

# Add results for cognitive processing
working_memory.add("analysis_results", analysis)
```

### Pattern 3: Manage Token Usage
```python
# Check before adding large content
if working_memory.get_tokens() > 40000:
    # Remove old content first
    working_memory.remove("old_data")

# Now add new content
working_memory.add_file("/personal/large_document.txt")
```

### Pattern 4: Clear and Reset
```python
# Clear everything and start fresh
working_memory.clear()

# Add only what's needed for current task
working_memory.add("current_goal", goal)
working_memory.add_file("/personal/context.txt")
```

## Migration from Old Memory API

### Old Way (DEPRECATED)
```python
# Old memory API - confusing
content = memory["/personal/data.json"]
memory["/personal/output.txt"] = result
```

### New Way (RECOMMENDED)
```python
# Standard Python - clear and familiar
with open("/personal/data.json") as f:
    content = json.load(f)

with open("/personal/output.txt", "w") as f:
    f.write(result)

# Explicit working memory control
working_memory.add("result", result)
```

## Benefits

1. **Clear Separation**: Filesystem is filesystem, working memory is working memory
2. **Standard Python**: Use familiar file operations everyone knows
3. **Explicit Control**: You decide what enters cognitive processing
4. **No Magic**: Everything works as expected
5. **Better Performance**: Only load what you need into context

## Remember

- Use standard Python for ALL file operations
- Use `working_memory` to control what your cognitive loop sees
- Don't try to import `working_memory` - it's pre-loaded
- Keep working memory focused on current task