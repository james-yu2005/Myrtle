# On-device Tavily search

Desk Chat exposes live web search as a **device MCP tool** — same pattern as the focus timer.
The ESP32 calls Tavily’s REST API directly. You do **not** need `scripts/mcp_search/` or a Mac process.

```
You speak → xiaozhi.me → calls self.search.web on device → HTTPS to api.tavily.com → spoken answer
```

## Tools

| Tool | Audience | Purpose |
|------|----------|---------|
| `self.search.web` | AI | Search the web (`query`, optional `max_results` 1–8) |
| `self.search.set_api_key` | User-only | Save Tavily key to NVS |
| `self.search.status` | User-only | Whether a key is configured |

## Setup

1. Create a free key at [app.tavily.com](https://app.tavily.com/).
2. Put it on the device using **one** of:

### Option A — menuconfig (baked into firmware)

```bash
idf.py menuconfig
# Xiaozhi Assistant → Web Search (Tavily) → Tavily API key
```

Or in `sdkconfig.defaults` / `sdkconfig`:

```
CONFIG_TAVILY_API_KEY="tvly-YOUR_KEY"
```

Then rebuild and flash.

### Option B — runtime (NVS, no rebuild)

After the device is online, call the user-only tool `self.search.set_api_key` with your key
(from a companion app / MCP client with `withUserTools=true`). NVS overrides the Kconfig value.

## Try it

Say things like:

- “Search for what’s new in ESP-IDF 5.5 and summarize it.”
- “What’s the latest news about AI voice assistants?”

## Notes

- Uses `search_depth=fast`, no `include_answer` (device returns snippets; xiaozhi summarizes).
- Runs on a background thread so a slow search cannot freeze the desk UI/audio.
- HTTP timeout is 8s to stay under the cloud MCP tool timeout (~10s).
- Free Tavily tier is roughly ~1,000 credits/month.
- `scripts/mcp_search/` remains as an optional cloud-MCP pipe if you prefer hosting Tavily MCP on a Mac/Pi instead.

## Related

- [MCP usage](./mcp-usage.md)
- [Cloud MCP integrations plan](./mcp-cloud-integrations.md)
