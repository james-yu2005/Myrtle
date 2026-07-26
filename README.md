# Desk Chat

Voice AI desk assistant for **M5Stack Core S3** (ESP32-S3).

Connects to [xiaozhi.me](https://xiaozhi.me) for speech, LLM, and TTS. On-device MCP controls the speaker, screen, camera, and focus timer. Cloud MCP bridges on a Mac add web search, Notion notes, Google Calendar, and Tapo lights.

## Features

- Wake word: **"Hi Myrtle"**
- Turtle ocean UI
- Focus / Pomodoro timer with desk-presence camera monitoring
- Device MCP: `self.focus.start`, `self.focus.stop`, `self.focus.status`
- Cloud MCP (Mac bridges):
  - [Tavily web search](scripts/mcp_search/README.md)
  - [Notion notes](scripts/mcp_notion/README.md) (Desk Chat Notes page)
  - [Google Calendar](scripts/mcp_google_calendar/README.md)
  - [Tapo lights](scripts/mcp_tapo/README.md)

## Build & flash (Mac)

```bash
get_idf   # . $HOME/esp/esp-idf/export.sh
cd desk_chat
python scripts/release.py m5stack-core-s3
idf.py -p /dev/cu.usbmodem101 flash monitor
```

Requires ESP-IDF **v5.5.2+**, CMake, and Ninja.

## Cloud MCP bridges

Each bridge needs its own terminal (leave running while you use it):

```bash
./scripts/mcp_search/start.sh   # web search
./scripts/mcp_notion/start.sh   # Notion notes
./scripts/mcp_google_calendar/start.sh   # Google Calendar
./scripts/mcp_tapo/start.sh     # Tapo lights
```

Copy each folder’s `.env.example` → `.env` and fill in credentials. Details are in the per-bridge READMEs.

## Config files

| File | Purpose |
|------|---------|
| `sdkconfig.defaults` | Shared settings |
| `sdkconfig.defaults.esp32s3` | S3 PSRAM, wake word |
| `main/boards/m5stack-core-s3/config.json` | Board target and camera |

## Docs

- [MCP usage (device tools)](docs/mcp-usage.md)
- [Cloud MCP overview](docs/mcp-cloud-integrations.md)
- [WebSocket protocol](docs/websocket.md)
- [Tavily search setup](scripts/mcp_search/README.md)
- [Notion notes setup](scripts/mcp_notion/README.md)
- [Google Calendar setup](scripts/mcp_google_calendar/README.md)
- [Tapo lights setup](scripts/mcp_tapo/README.md)

## License

Desk Chat is based on [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) (MIT).
See [LICENSE](LICENSE) for the license text and [NOTICE](NOTICE) for attribution.
