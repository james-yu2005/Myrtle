# Cloud MCP Integrations — Requirements & Rollout Plan

> Planning doc for connecting external MCP servers to Desk Chat via the xiaozhi backend.
> **Status:** Tavily search is **on-device** (`self.search.web`). Tapo lights cloud MCP is **working** ([setup](../scripts/mcp_tapo/README.md)).

## Goal

Extend Desk Chat beyond on-device tools (`self.focus.*`, camera, screen, speaker) by wiring cloud MCP servers so voice commands can reach Strava, Spotify, web search, Notion, and Google Calendar.

## Architecture reminder

```
You (voice) → Desk Chat (ESP32) → xiaozhi.me backend → LLM
                                              ↓
                                    Cloud MCP servers
                                    (Strava, Spotify, …)
                                              ↓
                                    External APIs / services
```

- **Device MCP** — tools registered on the ESP32 (`McpServer::AddTool`). Already implemented.
- **Cloud MCP** — external servers the backend calls. This doc covers those.

See also: [MCP usage (device-side)](./mcp-usage.md) · [WebSocket protocol](./websocket.md)

---

## Shared prerequisites (decide before starting)

| Item | Options | Decision |
|------|---------|----------|
| Backend | [xiaozhi.me](https://xiaozhi.me) hosted vs self-hosted ([xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)) | _TBD_ |
| MCP connection method | xiaozhi console endpoint · WebSocket pipe (`mcp_pipe.py`) · HTTP/SSE proxy | **WebSocket pipe** (`scripts/mcp_search/`) |
| Host machine | Mac always-on · Raspberry Pi · VPS · Docker on NAS | **Mac** (always-on while using search) |
| Secrets storage | `.env` on host · 1Password/env vault · macOS Keychain | **`scripts/mcp_search/.env`** |

### Runtime dependencies (likely needed across integrations)

- [x] Node.js 20+ (for `npx tavily-mcp`)
- [x] Python 3.10+ (for `mcp_pipe.py`); **3.11+** for Tapo (`scripts/mcp_tapo/`)
- [ ] `npx` available on PATH
- [ ] A machine that can run OAuth browser flows once during setup (later integrations)
- [ ] Outbound HTTPS from the MCP host

### xiaozhi-specific wiring

- [ ] Confirm MCP endpoint URL from xiaozhi.me console (or self-hosted config)
- [ ] Test that a single simple MCP server connects before adding more
- [ ] Document where MCP server configs live on the host

---

## Integration tracker

| # | Integration | Priority | Status | Server choice |
|---|-------------|----------|--------|---------------|
| 1 | Google Calendar | High | ⬜ Not started | _TBD_ |
| 2 | Tavily (search) | High | ✅ On-device (`self.search.web`) | Device REST API → [docs](./tavily-search.md) |
| 3 | Tapo lights | High | ✅ Working (L535E) | Thin `python-kasa` MCP → [setup](../scripts/mcp_tapo/README.md) |
| 4 | Notion | High | ⬜ Not started | [Notion MCP](https://developers.notion.com/docs/mcp) (official remote) |
| 5 | Spotify | Medium | ⬜ Not started | _TBD_ |
| 6 | Strava | Medium | ⬜ Not started | _TBD_ |

**Suggested order:** **Search (Tavily)** → **Tapo lights** → Calendar → Notion → Spotify → Strava

---

## 1. Google Calendar

### Why

Schedule-aware focus sessions: check for upcoming meetings, block focus time, get verbal reminders before events.

### Desk Chat use cases

- “Do I have anything in the next 30 minutes?”
- “Block 25 minutes for deep work.”
- “Start a focus timer — I’m free until my 3pm call.”
- “What’s on my calendar today?”

### Recommended servers (pick one)

| Server | Pros | Cons |
|--------|------|------|
| [nspady/google-calendar-mcp](https://github.com/nspady/google-calendar-mcp) | Feature-rich, multi-calendar | More setup |
| [feamster/calendar-mcp](https://github.com/feamster/calendar-mcp) | Simple, well-documented | Fewer features |
| [xiaozhi-mcp](https://github.com/tunforjob/xiaozhi-mcp) (bundled) | Native xiaozhi WebSocket pipe, includes calendar + weather + more | Monolithic; less control |

### Requirements

- [ ] Google account with Calendar access
- [ ] Google Cloud project with **Google Calendar API** enabled
- [ ] OAuth 2.0 credentials (Desktop app type)
- [ ] `credentials.json` saved to host (e.g. `~/.config/xiaozhi/credentials.json`)
- [ ] One-time browser OAuth flow → `token.json` on disk
- [ ] Timezone preference documented (e.g. `America/New_York`)

### API / auth checklist

| Credential | Where to get it |
|------------|-----------------|
| `credentials.json` | [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth 2.0 Desktop |
| `token.json` | Generated on first OAuth run |

### Integration notes

- Read-only scopes may be enough initially (`calendar.readonly`); add write scopes if blocking time on calendar.
- Pair with `self.focus.start` on device for combined “check calendar + start timer” flows.

### Status

- [ ] Server selected
- [ ] Google Cloud project created
- [ ] Calendar API enabled
- [ ] OAuth credentials downloaded
- [ ] First OAuth flow completed
- [ ] Connected to xiaozhi backend
- [ ] Voice smoke test passed

---

## 2. Tavily (web search) — **done (on-device)**

Implemented as firmware MCP tool `self.search.web` (no Mac host). Setup: [tavily-search.md](./tavily-search.md).

Optional alternative: cloud MCP pipe in [`scripts/mcp_search/`](../scripts/mcp_search/README.md).

---

## 2b. Tapo lights (L535E / Kasa) — **working**

### Why

Voice control for desk / room lighting from Desk Chat without Home Assistant.

### Desk Chat use cases

- “Turn on the desk light.”
- “Make the lamp blue / warm white.”
- “Dim the light to 20%.”
- “Is the desk light on?”

### Architecture

Host MCP on Mac uses **local LAN** `python-kasa` (direct `Device.connect`, not slow UDP discovery). Piped to xiaozhi via `mcp_pipe.py`.

```
Voice → Desk Chat → xiaozhi.me → tapo-lights MCP → python-kasa → bulb Wi‑Fi
```

### Requirements

- [x] Bulb paired in Tapo app (2.4 GHz Wi‑Fi)
- [x] Third-Party Compatibility enabled in Tapo app
- [x] `KASA_USERNAME` / `KASA_PASSWORD` (exact Tapo email casing)
- [x] Stable `TAPO_HOST` (DHCP reservation recommended)
- [x] xiaozhi MCP endpoint URL
- [x] Mac on same LAN, running `scripts/mcp_tapo/start.sh`

### Setup

See [`scripts/mcp_tapo/README.md`](../scripts/mcp_tapo/README.md).

### Status

- [x] Thin MCP server (`light_on`, `light_off`, `light_set_brightness`, `light_set_color`, `light_set_color_temp`, `light_status`, `light_discover`)
- [x] WebSocket pipe + fast KLAP connect (under cloud ~10s timeout)
- [x] Voice smoke test from Desk Chat (L535E)

---

## 3. Notion

### Why

Log focus sessions, capture tasks/notes by voice, and query project docs from the desk.

### Desk Chat use cases

- “Log that I finished a 25-minute focus block on desk_chat.”
- “Add ‘review PR’ to my task database.”
- “What did I write in my Focus Log this week?”
- “Create a note: ideas for turtle UI animations.”

### Recommended server

- **[Notion MCP](https://developers.notion.com/docs/mcp)** (official remote server) — OAuth, no manual API token juggling

Fallback: [makenotion/notion-mcp-server](https://github.com/makenotion/notion-mcp-server) (local, integration token)

### Requirements

- [ ] Notion account (free tier works)
- [ ] A Notion workspace with a **task/focus database** (create before or during setup)
- [ ] OAuth via official Notion MCP **or** internal integration token (local server)
- [ ] Database/page IDs documented for focus logging

### API / auth checklist

| Credential | Where to get it |
|------------|-----------------|
| OAuth (preferred) | Notion MCP remote — follow [Notion MCP docs](https://developers.notion.com/docs/mcp) |
| `NOTION_API_KEY` (fallback) | [Notion integrations](https://www.notion.so/my-integrations) → create integration → share pages/DBs with it |

### Pre-setup: Notion structure to create

- [ ] **Focus Log** database — fields: Date, Duration (min), Topic, Device (`desk_chat`)
- [ ] **Tasks** database (optional) — if not using Todoist separately
- [ ] Share both with the integration / OAuth app

### Integration notes

- On `self.focus.stop`, cloud MCP could append a row to Focus Log (requires backend orchestration or a custom bridge).
- Official remote MCP is easiest for OAuth; confirm xiaozhi backend supports remote/streamable HTTP MCP endpoints.

### Status

- [ ] Server approach chosen (remote OAuth vs local token)
- [ ] Notion databases created
- [ ] Auth completed
- [ ] Connected to xiaozhi backend
- [ ] Voice smoke test: read page
- [ ] Voice smoke test: write log entry

---

## 4. Spotify

### Why

Focus playlists, ambient music, and playback control hands-free at the desk.

### Desk Chat use cases

- “Play lo-fi focus music.”
- “Pause music.”
- “Start a 25-minute focus timer and play my Deep Work playlist.”
- “What’s playing?”

### Recommended servers (pick one)

| Server | Transport | Notes |
|--------|-----------|-------|
| [darrenjaworski/spotify-mcp](https://github.com/darrenjaworski/spotify-mcp) | stdio via `npx` | Mature, OAuth flow, token cache |
| [obrien-matthew/mcp-spotify](https://github.com/obrien-matthew/mcp-spotify) | stdio, Python/`uv` | Clean Python option |
| [playmcp Spotify](https://playmcp.dev/setup/) | stdio, PKCE | No client secret needed |

### Requirements

- [ ] **Spotify Premium account** (required for Web API playback control as of 2025+ dev policy)
- [ ] [Spotify Developer](https://developer.spotify.com/dashboard) application
- [ ] Redirect URI configured exactly (e.g. `http://127.0.0.1:8888/callback` — use `127.0.0.1`, not `localhost`)
- [ ] Active Spotify device on same network (desktop app, speaker, or phone)
- [ ] One-time browser OAuth on MCP host

### API / auth checklist

| Credential | Where to get it |
|------------|-----------------|
| `SPOTIFY_CLIENT_ID` | Spotify Developer Dashboard → your app |
| `SPOTIFY_CLIENT_SECRET` | Same (some PKCE servers omit this) |
| `SPOTIFY_REDIRECT_URI` | Must match dashboard exactly |
| `TOKEN_ENCRYPTION_KEY` | Generate locally (if server requires it) |

### Spotify Developer Dashboard checklist

- [ ] App created with **Web API** selected
- [ ] Redirect URI added: `http://127.0.0.1:8888/callback` (or server-specific port)
- [ ] Scopes: playback, playlists, library (per server README)

### Integration notes

- Playback targets an active Spotify device — desk speaker or Mac Spotify app must be running.
- Great combo with `self.focus.start`: “play playlist + start timer” in one utterance.
- Dev mode limits (2025+): max 5 authorized users per app, search capped at 10 results.

### Status

- [ ] Server selected
- [ ] Spotify Premium confirmed
- [ ] Developer app created
- [ ] OAuth completed, tokens cached
- [ ] Connected to xiaozhi backend
- [ ] Voice smoke test: play / pause

---

## 5. Strava

### Why

Health/fitness context at the desk — weekly activity summary, recovery awareness, motivation.

### Desk Chat use cases

- “How many kilometers did I run this week?”
- “What was my last ride?”
- “Am I on track for my monthly running goal?”
- “Take a break — you biked 40km yesterday.” (paired with focus breaks)

### Recommended servers (pick one)

| Server | Transport | Notes |
|--------|-----------|-------|
| [r-huijts/strava-mcp](https://github.com/r-huijts/strava-mcp) | stdio via `npx` | Guided OAuth in browser, 25 tools |
| [benniblau/strava-mcp](https://github.com/benniblau/strava-mcp) | HTTP or stdio | Bearer token auth, Docker-friendly |
| [pete-builds/strava-mcp-docker](https://github.com/pete-builds/strava-mcp-docker) | HTTP/SSE via Docker | Good for always-on host |

Also check: Strava official MCP connector (rolling out via Claude — may simplify setup later).

### Requirements

- [ ] Strava account
- [ ] Strava API application at [strava.com/settings/api](https://www.strava.com/settings/api)
- [ ] OAuth with scopes: `activity:read_all`, `profile:read_all` (avoid 401s on private activities)
- [ ] Callback domain configured (often `localhost` for local servers)
- [ ] Token refresh handled by server (`STRAVA_REFRESH_TOKEN`)

### API / auth checklist

| Credential | Where to get it |
|------------|-----------------|
| `STRAVA_CLIENT_ID` | Strava → Settings → My API Application |
| `STRAVA_CLIENT_SECRET` | Same |
| `STRAVA_ACCESS_TOKEN` | OAuth flow (short-lived) |
| `STRAVA_REFRESH_TOKEN` | OAuth flow (long-lived; server refreshes) |

### Integration notes

- Read-only is sufficient for desk Q&A; no write scopes needed initially.
- Less critical than calendar/search for daily desk workflow — good last integration.

### Status

- [ ] Server selected
- [ ] Strava API app created
- [ ] OAuth completed with correct scopes
- [ ] Connected to xiaozhi backend
- [ ] Voice smoke test: recent activities query

---

## Cross-integration ideas (later)

Once individual integrations work, consider combined voice flows:

| Utterance | Device MCP | Cloud MCP |
|-----------|------------|-----------|
| “Start focus — I’m free until 3.” | `self.focus.start` | Google Calendar (check) |
| “Focus for 25 minutes, play lo-fi, log it in Notion.” | `self.focus.start` | Spotify + Notion |
| “How far did I run this week? Then start a focus block.” | `self.focus.start` | Strava |
| “Search how to fix I2C on M5Stack.” | `self.search.web` | — |
| “Turn the desk light blue and start focus.” | `self.focus.start` | Tapo `light_set_color` |

---

## Open questions

- [ ] Does xiaozhi.me support multiple cloud MCP servers simultaneously?
- [ ] Remote MCP (Notion official) vs stdio + `mcp_pipe` — which transport does our backend use?
- [ ] Where will MCP servers run long-term (Mac, Pi, VPS)?
- [ ] Do we want a bundled [xiaozhi-mcp](https://github.com/tunforjob/xiaozhi-mcp) server instead of five separate ones?
- [ ] Should focus session end trigger Notion logging automatically (custom bridge)?

---

## References

- [MCP usage (device-side)](./mcp-usage.md)
- [WebSocket protocol](./websocket.md)
- [Xiaozhi MCP usage](https://xiaozhi.dev/en/docs/development/mcp/usage/)
- [MCP Registry](https://github.com/modelcontextprotocol/registry)
- [Smithery MCP directory](https://smithery.ai)
