# Obsidian MCP Docker Connection Fix

## Problem
The Obsidian MCP server running inside Docker was trying to connect to `127.0.0.1:27124`, which refers to the container itself, not the host machine. This caused connection refused errors.

## Root Cause
From inside a Docker container, `127.0.0.1` refers to the container's localhost, not the host machine's localhost. To access services running on the host from inside a container, you must use `host.docker.internal`.

## Solution Applied
Updated `mcp_config.json` to include `OBSIDIAN_API_URL` environment variable with the correct host reference:

```json
{
  "obsidian": {
    "env": {
      "OBSIDIAN_API_URL": "https://host.docker.internal:27124",
      "OBSIDIAN_HOST": "host.docker.internal",
      "OBSIDIAN_PORT": "27124",
      "OBSIDIAN_PROTOCOL": "https",
      "OBSIDIAN_API_KEY": "56787bd1a0cc0105dcaf20cdfc24d0d52b4cd865ee7f4e0ef5c109dd33955f21"
    },
    "args": [
      "run", "-i", "--rm",
      "-e", "OBSIDIAN_API_URL=https://host.docker.internal:27124",
      "-e", "OBSIDIAN_API_KEY=56787bd1a0cc0105dcaf20cdfc24d0d52b4cd865ee7f4e0ef5c109dd33955f21",
      "-e", "OBSIDIAN_PROTOCOL=https",
      "-v", "C:/Users/hp/Documents/ObsidianVault:/vault",
      "mcp/obsidian"
    ]
  }
}
```

## Verification
The curl test from the terminal proved that `host.docker.internal:27124` works correctly:

```bash
docker run --rm curlimages/curl \
  curl -k https://host.docker.internal:27124/vault/ \
  -H "Authorization: Bearer 56787bd1a0cc0105dcaf20cdfc24d0d52b4cd865ee7f4e0ef5c109dd33955f21"
```

Result: Successfully returned the file list.

## Next Steps
**Restart the LLM service** to reload the MCP configuration:

```powershell
# Stop the current LLM service (Ctrl+C or kill the process)
# Then restart it:
.\start_stack.ps1 -ServicesOnly
```

Or if using dev manager:
```powershell
.\start_stack.ps1 -UseDevManager
```

After restart, test the Obsidian tool:
```powershell
curl -X POST http://127.0.0.1:8002/mcp/docker/call `
  -H "Content-Type: application/json" `
  -d '{"server": "obsidian", "tool": "obsidian_list_files_in_vault", "arguments": {}}'
```

Expected result: List of files in the Obsidian vault.

## Key Principle
**Docker networking rule**: When a containerized service needs to access the host machine, always use `host.docker.internal` instead of `127.0.0.1` or `localhost`.
