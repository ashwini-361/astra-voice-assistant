# Agent Output Format - Expected Behavior

## Test Cases with Expected Outputs

### 1. Time Query (Complete Input)

**User Input:**
```
Tell me time in Chicago
```

**Expected Output:**
```
🕒 Current time in America/Chicago:

15:30
2026-04-28
```

---

### 2. Time Query (Incomplete Input - Missing Timezone)

**User Input:**
```
what time is it
```

**Expected Output:**
```
I need more information to use the time tool.

Missing required information:
  • timezone: The IANA timezone identifier (e.g., 'America/New_York', 'Asia/Tokyo', 'Europe/London')

Please provide this information so I can help you.
```

---

### 3. Search + Fetch + Summarize (Success)

**User Input:**
```
summarize latest nuclear thorium research
```

**Expected Output:**
```
• Thorium is a more accessible and less dangerous alternative to uranium for nuclear power, as demonstrated by the first-ever thorium reactor built in the Gobi desert.
• The Chinese Academy of Sciences successfully operated this two-megawatt thorium reactor without issues and has now achieved another milestone by reloading it while still running.

• Thorium-232 can be transformed into U-233 through exposure to radiation, which then decays into protactinium. This process allows for the recycling of U-233, a key feature of thorium reactors.
• The Gobi desert-based reactor uses molten salt as a coolant instead of water, making it safer and reducing the risk of meltdown during overheating conditions.

• Molten salt reactors like this one are gaining attention again after years of development. Almost $1 billion was initially invested in developing these reactors for Cold War-era stealth bomber planes.
• The first full-power run of an Oak Ridge National Laboratory's molten salt reactor lasted over 13,000 hours from 1965 to 1969 before losing interest due to budget constraints.

Source: popularmechanics.com
```

---

### 4. Obsidian File List (Success)

**User Input:**
```
check files in obsidian vault
```

**Expected Output (if Obsidian running):**
```
📁 Files in your Obsidian vault:

• Welcome.md
• rough.md
• 2026-04-16.md
• Untitled.canvas

Let me know if you want to open or edit any file.
```

---

### 5. Obsidian Connection Error

**User Input:**
```
check files in obsidian vault
```

**Expected Output (if Obsidian not running):**
```
⚠️ Unable to connect to the service.

This usually means:
• The service is not running
• Network connectivity issues
• Firewall blocking the connection

Please check if the service is running and try again.

---
🔧 Debug Info (for development):
Error Type: connection
HTTP Status: 503
Tool: storage
Details: Connection refused to 127.0.0.1:27124
```

---

### 6. Timeout Error

**User Input:**
```
<any query that takes >30s>
```

**Expected Output:**
```
⚠️ The request took too long to complete.

This usually means:
• The service is temporarily unavailable
• The network connection is slow
• The request is too complex

Please try again in a moment.

---
🔧 Debug Info (for development):
Error Type: timeout
HTTP Status: 504
Tool: search
Details: Tool call exceeded 30s timeout
```

---

### 7. Authentication Error

**User Input:**
```
<query requiring authenticated service with invalid credentials>
```

**Expected Output:**
```
⚠️ Authentication failed.

This usually means:
• Invalid API key or credentials
• Expired authentication token
• Insufficient permissions

Please verify your credentials and try again.

---
🔧 Debug Info (for development):
Error Type: auth
HTTP Status: 401
Tool: storage
Details: Invalid API key
```

---

### 8. Validation Error (Missing Arguments)

**User Input:**
```
convert time
```

**Expected Output:**
```
I need more information to use the time tool.

Missing required information:
  • source_timezone: The source timezone (e.g., 'America/New_York')
  • time: The time to convert (e.g., '15:30')
  • target_timezone: The target timezone (e.g., 'Asia/Tokyo')

Please provide this information so I can help you.
```

---

## Key Improvements

### Before
- Raw JSON dumps
- Technical error messages
- No formatting
- No user guidance

### After
- Clean, formatted responses
- User-friendly error messages
- Emoji indicators for visual clarity
- Actionable guidance
- Debug info included (for development, will be removed in production)
- Proper structure (bullet points, line breaks)
- Source attribution for web content

## Testing Commands

```powershell
# Test 1: Time query (complete)
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "Tell me time in Chicago", "max_steps": 4}'

# Test 2: Time query (incomplete)
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "what time is it", "max_steps": 4}'

# Test 3: Search + Summarize
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "summarize latest nuclear thorium research", "max_steps": 4}'

# Test 4: Obsidian file list
curl -X POST http://127.0.0.1:8002/agent/loop `
  -H "Content-Type: application/json" `
  -d '{"prompt": "check files in obsidian vault", "max_steps": 4}'
```
