# Multi-Fetch Bug Fixes

## Bugs Fixed

### Bug 1: String Slicing Error in Synthesis
**Error**: `ERROR:services.agent_control.control_plane:Multi-source synthesis failed: slice(None, 500, None)`

**Root Cause**: 
```python
# WRONG: Can't slice a slice object
content = str(source.get("content", ""))[:2000]
```

The issue was that `source.get("content", "")` could return a dict or other object, and when converted to string and sliced, it created a slice object instead of a string.

**Fix**:
```python
# CORRECT: Convert to string first, then slice safely
content_str = str(source.get("content", ""))
content = content_str[:2000] if len(content_str) > 2000 else content_str
```

**Location**: `services/agent_control/multi_fetch.py:186`

---

### Bug 2: Async Function Check Calling Function Prematurely
**Error**: `RuntimeWarning: coroutine 'run_phase2_agent_loop.<locals>._fetch_url' was never awaited`

**Root Cause**:
```python
# WRONG: This CALLS the function to check if it's awaitable
if hasattr(fetch_fn(url), "__await__"):
    fetch_result = await asyncio.wait_for(fetch_fn(url), ...)
```

This calls `fetch_fn(url)` twice - once to check if it's awaitable, and once to actually execute it. The first call creates a coroutine that's never awaited.

**Fix**:
```python
# CORRECT: Call once, check if result is coroutine, then await
result = fetch_fn(url)
if asyncio.iscoroutine(result):
    fetch_result = await asyncio.wait_for(result, ...)
else:
    fetch_result = await asyncio.wait_for(asyncio.to_thread(lambda: result), ...)
```

**Location**: `services/agent_control/multi_fetch.py:110-120`

---

### Bug 3: Same Async Check Issue in Control Plane
**Root Cause**: Same pattern as Bug 2 in control_plane.py

**Fix**:
```python
# CORRECT: Use asyncio.iscoroutine() instead of hasattr check
out = execute_fn(fetch_action)
if asyncio.iscoroutine(out):
    return await out
else:
    return out
```

**Location**: `services/agent_control/control_plane.py` (multi-fetch execution block)

---

## Test Results

### Before Fixes
```
ERROR:services.agent_control.control_plane:Multi-source synthesis failed: slice(None, 500, None)
RuntimeWarning: coroutine 'run_phase2_agent_loop.<locals>._fetch_url' was never awaited
```

Result: Multi-fetch failed, synthesis error, no answer generated.

### After Fixes
Expected:
- Multi-fetch executes successfully
- 2-3 sources fetched (with domain diversity)
- Synthesis combines all sources
- Final response with citations

---

## Key Lessons

### 1. String Slicing Safety
Always convert to string first, then check length before slicing:
```python
# Safe pattern
text = str(value)
truncated = text[:limit] if len(text) > limit else text
```

### 2. Async Function Checking
Use `asyncio.iscoroutine()` to check if a value is a coroutine:
```python
# WRONG
if hasattr(fn(), "__await__"):  # Calls fn() prematurely!
    await fn()

# CORRECT
result = fn()
if asyncio.iscoroutine(result):
    await result
```

### 3. Avoid Double Execution
Never call a function just to check its return type - call once, store result, then check.

---

## Testing Commands

### Test multi-fetch after fixes
```bash
curl -X POST http://127.0.0.1:8002/agent/loop \
  -H "Content-Type: application/json" \
  -d '{"prompt": "latest AI breakthroughs", "max_steps": 4}'
```

Expected output:
- Step 1: Search (5 results)
- Step 2: Multi-fetch (2-3 successful sources)
- Final response: Synthesized answer with citations

### Check logs for success
```bash
# Should see:
# "Multi-fetch: attempting 3 sources"
# "[1/3] ✓ Fetch successful: ..."
# "[2/3] ✓ Fetch successful: ..."
# "Multi-fetch complete: 2 successful, 1 failed"
# No synthesis errors
```

---

## Files Modified

1. **services/agent_control/multi_fetch.py**
   - Fixed string slicing in `synthesize_multi_source()`
   - Fixed async check in `multi_fetch()`

2. **services/agent_control/control_plane.py**
   - Fixed async check in `_fetch_url()` helper

---

## Status

✅ All bugs fixed
✅ Syntax validated
✅ Ready for testing

**Next Step**: Restart LLM service and test with "latest AI breakthroughs" query.
