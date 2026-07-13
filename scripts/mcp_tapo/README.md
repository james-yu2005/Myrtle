# Tapo Lights MCP for Desk Chat

Voice control for a Tapo bulb (tested on **L535E**) via a Mac-side MCP bridge:

```
You → Desk Chat (M5) → xiaozhi.me → this Mac → python-kasa → bulb on Wi‑Fi
```

The Mac must stay on the **same LAN** as the bulb while you want voice control.
Leave `./start.sh` running.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Bulb in **Tapo app** | Pair on phone first (2.4 GHz Wi‑Fi) |
| **Third-Party Compatibility** | Tapo → Me → Third-Party Services → Third-Party Compatibility → **On** |
| TP-Link account email/password | Exact same as Tapo app login — **email is case-sensitive** |
| Bulb LAN IP (`TAPO_HOST`) | Prefer a DHCP reservation |
| [xiaozhi.me](https://xiaozhi.me) MCP endpoint | Console → your agent → MCP endpoint |
| Python **3.11+** | `brew install python@3.12` if macOS only has 3.9 |

## Setup

### 1. Configure `.env`

```bash
cd scripts/mcp_tapo
cp .env.example .env
```

Edit `.env`:

```bash
MCP_ENDPOINT=wss://api.xiaozhi.me/mcp/?token=...
KASA_USERNAME=Exact.Casing@email.com   # must match Tapo login exactly
KASA_PASSWORD=your-tapo-password
TAPO_HOST=192.168.x.x                  # bulb IPv4
```

### 2. Sanity-check the bulb (optional)

```bash
./start.sh   # creates .venv + installs deps on first run; Ctrl+C after connect if testing only

source .venv/bin/activate
set -a && source .env && set +a
kasa --host "$TAPO_HOST" --username "$KASA_USERNAME" --password "$KASA_PASSWORD" on
```

If auth fails with “challenge” / wrong password: fix **email casing** first (e.g. `James...` ≠ `james...`), then confirm Third-Party Compatibility is on.

### 3. Run the bridge

```bash
./start.sh
```

You should see:

```text
Connected to xiaozhi MCP endpoint
starting user=... host=192.168.... pass_set=True
Processing request of type ListToolsRequest
```

Then ask Desk Chat things like “turn on the desk light”, “make it blue”, “dim to 20%”.

Restart `./start.sh` after any `.env` or code change.

## Tools

| Tool | What it does |
|------|----------------|
| `light_on` / `light_off` | Power |
| `light_set_brightness` | 1–100% |
| `light_set_color` | HSV (`hue` 0–360, `saturation`, optional `value`) |
| `light_set_color_temp` | White Kelvin (e.g. 2700–6500) |
| `light_status` | On/off, brightness, HSV, color temp |
| `light_discover` | LAN scan (slow; only for finding a new IP) |

Optional `host` (IPv4 only) overrides `TAPO_HOST`. Non-IP values are ignored.

## Files

| File | Purpose |
|------|---------|
| `start.sh` | Create `.venv`, install deps, run the pipe |
| `server.py` | FastMCP tools → `python-kasa` |
| `mcp_pipe.py` | stdio ↔ xiaozhi WebSocket |
| `mcp_config.json` | Pipe target (`tapo-lights`) |
| `.env` | Secrets (gitignored) |
| `.venv/` | Local virtualenv (gitignored) |

## How it works (important)

- Xiaozhi cloud MCP tools time out in about **10 seconds**.
- This server uses **direct `Device.connect`** (SMART.TAPOBULB + KLAP v2), not UDP discovery, so on/off/color usually finish in under **1 second**.
- `.env` is loaded with `override=True` from this folder so shell leftovers cannot wipe credentials.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Device response did not match our challenge` | Email **case** must match Tapo exactly; password must match app login; enable Third-Party Compatibility (toggle off/on if needed) |
| `$KASA_USERNAME` empty in shell | `.env` is not auto-exported — use `set -a && source .env && set +a` before `kasa`, or pass flags explicitly |
| CLI works, voice fails | Restart `./start.sh` so it picks up `.env` / code; confirm log shows `tools/call name=light_on` then `Connecting to ...` |
| Voice times out | Bridge must be running on the same Wi‑Fi as the bulb; avoid relying on `light_discover` for routine control |
| Bulb IP changed after router reboot | Update `TAPO_HOST` or reserve DHCP; optional: `kasa discover` / `light_discover` |
