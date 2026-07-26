# Cloud MCP Integrations

Desk Chat uses Mac-side MCP bridges over the xiaozhi WebSocket endpoint.
On-device tools (focus, camera, screen, speaker) stay in firmware.

```
You (voice) → Desk Chat (ESP32) → xiaozhi.me → LLM
                                      ↓
                        Cloud MCP bridges on Mac
                        (search / Notion / Calendar / Tapo)
```

## Bridges

| Integration | Status | Setup |
|-------------|--------|-------|
| Tavily web search | Working | [`scripts/mcp_search/`](../scripts/mcp_search/README.md) |
| Notion notes | Working (limit OAuth to **Desk Chat Notes**) | [`scripts/mcp_notion/`](../scripts/mcp_notion/README.md) |
| Google Calendar | Working (OAuth Desktop client) | [`scripts/mcp_google_calendar/`](../scripts/mcp_google_calendar/README.md) |
| Tapo lights | Working (LAN required) | [`scripts/mcp_tapo/`](../scripts/mcp_tapo/README.md) |

## Shared requirements

- [xiaozhi.me](https://xiaozhi.me) MCP endpoint URL in each bridge `.env`
- Node.js 20+ (`npx` for Tavily + Notion)
- Python 3.11+ for the pipe scripts
- Mac on the same LAN as the Tapo bulb

## Run

```bash
./scripts/mcp_search/start.sh
./scripts/mcp_notion/start.sh
./scripts/mcp_google_calendar/start.sh
./scripts/mcp_tapo/start.sh
```

One process per bridge. Keep terminals open while using those tools.

## Device-side companion

Focus / desk-presence monitoring is firmware, not a cloud MCP:

- `self.focus.start` / `stop` / `status`
- Camera presence checks while a focus session is active

See [MCP usage](./mcp-usage.md).
