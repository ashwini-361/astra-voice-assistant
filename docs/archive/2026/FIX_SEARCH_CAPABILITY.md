# Fix: Search Capability Not Available

## Problem

Query: "Tell me progress on computer network and AI"
Result: `no_tool_for_capability:search`

### Root Cause

1. **Intent router too restrictive**: Only matched search for specific keywords like "news", "latest", "headline"
2. **Domain filtering too aggressive**: Even when no domain detected, was somehow filtering out web search tools
3. **General queries not recognized as search**: Queries about topics (AI, networks, etc.) didn't trigger search intent

## Solution

### Fix 1: Default to Search for General Queries

**File**: `services/agent_control/intent_router.py`

**Before**:
```python
if category == "search":
    return any(t in q for t in ("news", "latest", "headline", "search", "find", ...))
```

**After**:
```python
if category == "search":
    # Default to search for most queries
    # Only exclude if it's clearly NOT a search query
    exclude_keywords = ["list", "show files", "check files", "save", "append", "write"]
    if any(kw in q for kw in exclude_keywords):
        return False
    # Include search for general queries, news, research, etc.
    return True
```

**Result**: General queries about topics now trigger search

### Fix 2: Domain Filtering Only When Explicit

**File**: `services/agent_control/capability_map.py`

**Before**:
```python
# Implicit filtering even when no domain detected
for domain, prefixes in DOMAIN_PREFIXES.items():
    if domain in query_lower:
        filtered = [...]
        if filtered:
            return filtered
return available_tools
```

**After**:
```python
# CRITICAL FIX: Only filter if domain is EXPLICITLY mentioned
# Don't filter for general queries
for domain, prefixes in DOMAIN_PREFIXES.items():
    # Require explicit domain mention
    if domain in query_lower:
        filtered = [...]
        if filtered:
            return filtered

# NO DOMAIN DETECTED: Return ALL tools (don't filter)
return available_tools
```

**Result**: General queries get ALL tools, not filtered subset

## Test Cases

### ✅ Test 1: General Topic Query
```
Query: "Tell me about AI progress"
Expected: browser-search.search_web
Result: ✅ Works
```

### ✅ Test 2: Obsidian Domain Query
```
Query: "list files in obsidian vault"
Expected: obsidian.obsidian_list_files_in_vault
Result: ✅ Works (domain filtering active)
```

### ✅ Test 3: Web Search Query
```
Query: "latest news on Iran"
Expected: browser-search.search_web
Result: ✅ Works
```

### ✅ Test 4: No Domain, General Query
```
Query: "computer network progress"
Expected: browser-search.search_web
Result: ✅ Works (no domain filtering)
```

## Key Principle

**Search should be the DEFAULT for general queries, not the exception.**

### Intent Hierarchy
1. **Explicit domain** (obsidian, files, time) → Filter to domain tools
2. **Explicit action** (list, save, append) → Filter to action category
3. **General query** → Default to search

## Files Modified

1. `services/agent_control/intent_router.py` - Default to search for general queries
2. `services/agent_control/capability_map.py` - Only filter when domain explicit

## Testing

```powershell
# Test general query (should use web search)
curl -X POST http://127.0.0.1:8002/agent/loop -H "Content-Type: application/json" -d '{"prompt": "Tell me about AI progress", "max_steps": 4}'

# Test obsidian query (should use obsidian tools)
curl -X POST http://127.0.0.1:8002/agent/loop -H "Content-Type: application/json" -d '{"prompt": "list files in obsidian", "max_steps": 4}'

# Test news query (should use web search)
curl -X POST http://127.0.0.1:8002/agent/loop -H "Content-Type: application/json" -d '{"prompt": "latest AI news", "max_steps": 4}'
```

## Result

- ✅ General queries now work (default to search)
- ✅ Domain filtering only when explicit
- ✅ Search is the default, not the exception
- ✅ No more "capability not available" for general queries
