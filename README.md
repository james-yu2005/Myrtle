# Desk Chat

Voice AI desk assistant for **M5Stack Core S3** (ESP32-S3).

Connects to [xiaozhi.me](https://xiaozhi.me) for speech, LLM, and TTS. On-device MCP controls the speaker, screen, camera, and focus timer.

## Features

- Wake word: **"hi nova"**
- Turtle ocean UI
- Focus / Pomodoro timer with desk-presence camera monitoring
- MCP: `self.focus.start`, `self.focus.stop`, `self.focus.status`

## Build & flash (Mac)

```bash
get_idf   # . $HOME/esp/esp-idf/export.sh
cd desk_chat
python scripts/release.py m5stack-core-s3
idf.py -p /dev/cu.usbmodem101 flash monitor
```

Requires ESP-IDF **v5.5.2+**, CMake, and Ninja.

## Config files

| File | Purpose |
|------|---------|
| `sdkconfig.defaults` | Shared settings |
| `sdkconfig.defaults.esp32s3` | S3 PSRAM, wake word |
| `main/boards/m5stack-core-s3/config.json` | Board target and camera |

## Docs

- [MCP usage](docs/mcp-usage.md)
- [WebSocket protocol](docs/websocket.md)

## License

Desk Chat is based on [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) (MIT).
See [LICENSE](LICENSE) for the license text and [NOTICE](NOTICE) for attribution.
