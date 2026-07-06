# Test Obsidian Local REST API reachability from host and Docker

$OBSIDIAN_HOST = "127.0.0.1"
$OBSIDIAN_PORT = "27124"
$OBSIDIAN_PROTOCOL = "https"
$API_KEY = "56787bd1a0cc0105dcaf20cdfc24d0d52b4cd865ee7f4e0ef5c109dd33955f21"

Write-Host ""
Write-Host "=== Test 1: Host -> Obsidian API ===" -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "${OBSIDIAN_PROTOCOL}://${OBSIDIAN_HOST}:${OBSIDIAN_PORT}/vault/" -Headers @{"Authorization" = "Bearer $API_KEY"} -TimeoutSec 5 -SkipCertificateCheck -ErrorAction Stop
    Write-Host "OK Host can reach Obsidian API (status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "FAIL Host CANNOT reach Obsidian API: $_" -ForegroundColor Red
    Write-Host "  -> Check if Obsidian is running and Local REST API plugin is enabled" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Test 2: Docker -> host.docker.internal ===" -ForegroundColor Cyan
try {
    $dockerTest = docker run --rm curlimages/curl:latest curl -k -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $API_KEY" --connect-timeout 5 "${OBSIDIAN_PROTOCOL}://host.docker.internal:${OBSIDIAN_PORT}/vault/" 2>&1
    
    if ($dockerTest -match "^\d{3}$") {
        Write-Host "OK Docker can reach host.docker.internal:${OBSIDIAN_PORT} (status: $dockerTest)" -ForegroundColor Green
    } else {
        Write-Host "FAIL Docker CANNOT reach host.docker.internal: $dockerTest" -ForegroundColor Red
        Write-Host "  -> Try binding Obsidian to 0.0.0.0 instead of 127.0.0.1" -ForegroundColor Yellow
    }
} catch {
    Write-Host "FAIL Docker test failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Test 3: MCP Obsidian Container (one-shot) ===" -ForegroundColor Cyan
$testPayload = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}}}'

try {
    $mcpTest = echo $testPayload | docker run -i --rm -e OBSIDIAN_HOST=host.docker.internal -e OBSIDIAN_PORT=$OBSIDIAN_PORT -e OBSIDIAN_PROTOCOL=$OBSIDIAN_PROTOCOL -e OBSIDIAN_API_KEY=$API_KEY mcp/obsidian:latest 2>&1 | Select-Object -First 1
    
    if ($mcpTest -match "result") {
        Write-Host "OK MCP Obsidian container can initialize" -ForegroundColor Green
    } else {
        Write-Host "FAIL MCP Obsidian container failed: $mcpTest" -ForegroundColor Red
    }
} catch {
    Write-Host "FAIL MCP test failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Recommendations ===" -ForegroundColor Cyan
Write-Host "1. Ensure Obsidian is running with Local REST API plugin enabled"
Write-Host "2. Check plugin settings: should bind to 0.0.0.0 (not 127.0.0.1)"
Write-Host "3. Verify API key matches: $API_KEY"
Write-Host "4. Verify protocol: $OBSIDIAN_PROTOCOL and port: $OBSIDIAN_PORT"
Write-Host "5. If Docker tests fail, check Windows Firewall rules"
Write-Host ""
