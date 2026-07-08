# Test Agent Error Handling and User Prompts

## Test Cases

### 1. Missing Arguments (Time Tool)
**Query**: "what time is it"
**Expected**: LLM should ask user for timezone information with clear description

### 2. Connection Error
**Query**: "tell me about Iran war" (when Obsidian is not running)
**Expected**: User-friendly error message explaining connection issue

### 3. Timeout Error
**Query**: Any query that triggers a tool taking >30s
**Expected**: Clear timeout error with explanation

### 4. Authentication Error
**Query**: Query requiring authenticated service with invalid credentials
**Expected**: Clear auth error asking to verify API key

## Test Commands

```powershell
# Test 1: Missing timezone argument
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "what time is it", "max_steps": 4}'

# Test 2: Search → Fetch → Summarize (should work)
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "tell me about latest AI news", "max_steps": 4}'

# Test 3: Direct URL fetch
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "https://www.bbc.com/news", "max_steps": 4}'
```

## Expected Improvements

### Before
- Silent failures with generic "tool execution failed"
- No guidance on what arguments are missing
- Cryptic error codes without explanation
- No distinction between error types

### After
- User-friendly prompts asking for missing information
- Clear error type identification (timeout, connection, auth, validation)
- Detailed explanations with actionable guidance
- Emoji indicators for visual clarity (⚠️)
- Technical details included for debugging

## Error Message Examples

### Missing Arguments
```
I need more information to use the time tool.

Missing required information:
  • timezone: The IANA timezone identifier (e.g., 'America/New_York', 'Asia/Tokyo')

Please provide this information so I can help you.
```

### Connection Error
```
I encountered an error while using the fetch tool:

⚠️ Connection Error: Unable to reach the service.
Please check if the service is running and accessible.

Technical details: HTTP 503
```

### Timeout Error
```
I encountered an error while using the search tool:

⚠️ Timeout Error: The tool took too long to respond (>30s).
This usually means the service is unavailable or overloaded.

Technical details: HTTP 504
```

### Authentication Error
```
I encountered an error while using the storage tool:

⚠️ Authentication Error: Invalid credentials or permissions.
Please verify your API key or access token.

Technical details: HTTP 401
```
