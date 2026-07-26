# Google Calendar MCP for Desk Chat

Read and create events on your Google Calendar through a Mac-side MCP bridge:

```
You → Desk Chat (M5) → xiaozhi.me → this Mac → Google Calendar API
```

Leave `./start.sh` running while you want calendar voice commands.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| [Google Cloud project](https://console.cloud.google.com/) | Enable **Google Calendar API** |
| OAuth **Desktop** client | APIs & Services → Credentials → Create OAuth client ID → Desktop app |
| [xiaozhi.me](https://xiaozhi.me) MCP endpoint | Same token as your other bridges |
| Python **3.11+** | `brew install python@3.12` if needed |

OAuth scope is `calendar.events` (read/write events, not full account admin).

## Setup

### 1. Google Cloud

1. Create or pick a project in [Google Cloud Console](https://console.cloud.google.com/).
2. **APIs & Services → Library** → enable **Google Calendar API**.
3. **APIs & Services → OAuth consent screen** → configure (External is fine for personal use; add your Google account as a test user while in Testing).
4. **Credentials → Create credentials → OAuth client ID → Desktop app**.
5. Copy the **Client ID** and **Client secret** into `.env`, or download JSON and save as `credentials.json` in this folder.

### 2. Configure `.env`

```bash
cd scripts/mcp_google_calendar
cp .env.example .env
```

Edit `.env`:

```bash
MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_TIMEZONE=America/New_York
```

If `scripts/mcp_search/.env` already has `MCP_ENDPOINT`, you can leave that line empty here and `start.sh` will reuse it.

### 3. Authorize (one time)

```bash
chmod +x start.sh
source .venv/bin/activate  # or run ./start.sh once to create it
set -a && source .env && set +a
python server.py --authorize
```

Sign in in the browser and allow calendar access. Credentials are stored in `.google-token.json` (gitignored). The token refreshes automatically afterward.

### 4. Run the bridge

```bash
./start.sh
```

Try voice prompts like:

- “What’s on my calendar tomorrow?”
- “Add a dentist appointment Friday at 2pm for one hour.”
- “Schedule focus time Monday 9 to 11.”

For timed events, the model should pass ISO-like times; all-day events use `YYYY-MM-DD`.

## Tools

| Tool | What it does |
|------|----------------|
| `calendar_list_upcoming` | Events in the next N days (default 7) |
| `calendar_create_event` | Create event with title, start, end, optional description/location |
| `calendar_list_calendars` | List writable calendars (to pick `calendar_id`) |

## Files

| File | Purpose |
|------|---------|
| `start.sh` | Virtualenv, deps, run the pipe |
| `server.py` | FastMCP tools → Calendar API v3 |
| `mcp_pipe.py` | stdio ↔ xiaozhi WebSocket |
| `mcp_config.json` | Pipe target (`google-calendar`) |
| `.env` | Endpoint + OAuth client (gitignored) |
| `.google-token.json` | User OAuth token (gitignored) |
| `credentials.json` | Optional downloaded OAuth JSON (gitignored) |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `access_denied` / consent screen | Add your Google account under OAuth consent screen → Test users |
| `invalid_client` | Check client ID/secret; use Desktop app type, not Web |
| Browser every time | Ensure `.google-token.json` persists; do not delete between runs |
| Wrong timezone on events | Set `GOOGLE_CALENDAR_TIMEZONE` to your IANA zone |
| Writes to wrong calendar | Set `GOOGLE_CALENDAR_ID` or ask the model to use `calendar_list_calendars` first |
