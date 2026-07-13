# Tavily Search MCP for Desk Chat (optional cloud pipe)

> **Preferred path:** on-device search via `self.search.web` — see
> [docs/tavily-search.md](../../docs/tavily-search.md). That needs no Mac process.

This folder is an **optional** alternative: run official `tavily-mcp` on a host and
bridge it to xiaozhi.me with `mcp_pipe.py`.

Connects [Tavily](https://tavily.com/) web search to your Desk Chat device via the
[xiaozhi.me](https://xiaozhi.me) cloud MCP endpoint.

Voice flow:

```
You → Desk Chat → xiaozhi.me → LLM calls tavily-search → spoken summary
```

Tavily exposes `tavily-search` and `tavily-extract` tools. The LLM uses search
results to answer and summarize — you do not need a separate summarization API.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| [xiaozhi.me](https://xiaozhi.me) account | Device already paired |
| MCP endpoint URL | Console → agent → MCP endpoint |
| [Tavily API key](https://app.tavily.com/) | Free tier ~1,000 credits/month |
| Node.js **v20+** | For `npx tavily-mcp` |
| Python **3.10+** | For `mcp_pipe.py` |
| Mac (or other host) | Must stay running while you want search |

## Setup

### 1. Get credentials

1. **Tavily** — sign up at [app.tavily.com](https://app.tavily.com/), copy API key (`tvly-...`).
2. **xiaozhi** — open [xiaozhi.me](https://xiaozhi.me) console, copy your agent's **MCP endpoint** WebSocket URL.

### 2. Configure

```bash
cd scripts/mcp_search
cp .env.example .env
# Edit .env — set MCP_ENDPOINT and TAVILY_API_KEY
```

### 3. Install Python deps

```bash
python3 -m pip install -r requirements.txt
```

### 4. Start the bridge

```bash
./start.sh
```

Or manually:

```bash
cd scripts/mcp_search
python3 mcp_pipe.py
```

Leave this terminal open. The pipe reconnects automatically if the WebSocket drops.

### 5. Test from Desk Chat

Say something like:

- "Search for what's new in ESP-IDF 5.5 and summarize it."
- "What are the latest news about AI voice assistants?"
- "How do I configure PSRAM on ESP32-S3?"

## Configuration

### `mcp_config.json`

Default server runs official Tavily MCP via npx:

```json
{
  "mcpServers": {
    "tavily-search": {
      "command": "npx",
      "args": ["-y", "tavily-mcp@latest"],
      "env": {
        "DEFAULT_PARAMETERS": "{\"search_depth\": \"advanced\", \"max_results\": 10}"
      }
    }
  }
}
```

`TAVILY_API_KEY` is read from `.env` (not committed). Adjust `DEFAULT_PARAMETERS` for
deeper/shallower searches — see [Tavily MCP docs](https://docs.tavily.com/documentation/mcp).

### Remote Tavily (alternative)

Tavily also hosts a remote MCP URL (no local npx). That requires HTTP/SSE support on
the xiaozhi side; the stdio + `mcp_pipe.py` approach above is the supported path for
xiaozhi.me today.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `MCP_ENDPOINT` not set | Create `.env` from `.env.example` |
| `TAVILY_API_KEY` not set | Add key from Tavily dashboard |
| `npx not found` | Install Node.js 20+ from [nodejs.org](https://nodejs.org/) |
| WebSocket disconnects | Pipe auto-reconnects; check token in MCP endpoint URL |
| Search not triggered | Confirm `mcp_pipe.py` is running; ask explicitly to "search the web" |
| Invalid API key | Key must start with `tvly-`; verify at [app.tavily.com](https://app.tavily.com/) |

## Files

| File | Purpose |
|------|---------|
| `mcp_pipe.py` | WebSocket ↔ stdio bridge to xiaozhi |
| `mcp_config.json` | Tavily MCP server definition |
| `.env` | Secrets (gitignored) |
| `start.sh` | One-command launcher |

## Next integrations

See [docs/mcp-cloud-integrations.md](../../docs/mcp-cloud-integrations.md) for
Google Calendar, Notion, Spotify, and Strava.
