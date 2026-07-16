#!/usr/bin/env python3
"""Bridge local stdio MCP servers to a xiaozhi.me WebSocket endpoint."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path

import websockets
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR / "mcp_config.json"
load_dotenv(SCRIPT_DIR / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MCP_PIPE")

INITIAL_BACKOFF = 1
MAX_BACKOFF = 60
ALLOWED_TOOLS = {
    "notion-search",
    "notion-fetch",
    "notion-create-pages",
    "notion-update-page",
}


def load_servers() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    return config.get("mcpServers", {})


def build_command(name: str) -> tuple[list[str], dict[str, str]]:
    entry = load_servers().get(name)
    if not entry:
        raise RuntimeError(f"Unknown MCP server: {name}")

    command = entry.get("command")
    if not command:
        raise RuntimeError(f"MCP server {name!r} has no command")

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["MCP_REMOTE_CONFIG_DIR"] = str(SCRIPT_DIR / ".mcp-auth")
    env.update({str(key): str(value) for key, value in entry.get("env", {}).items()})
    return [command, *entry.get("args", [])], env


def summarize(message: str) -> str:
    try:
        payload = json.loads(message)
    except Exception:
        return message[:160]

    method = payload.get("method")
    if method == "tools/call":
        params = payload.get("params") or {}
        return f"tools/call name={params.get('name')} args={params.get('arguments')}"
    if method:
        return f"method={method}"
    if "error" in payload:
        return f"error id={payload.get('id')} {payload.get('error')}"
    return f"result id={payload.get('id')}"


async def websocket_to_process(
    websocket, process, name: str, tool_list_request_ids: set
) -> None:
    assert process.stdin is not None
    while True:
        message = await websocket.recv()
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        try:
            payload = json.loads(message)
            if payload.get("method") == "tools/list" and "id" in payload:
                tool_list_request_ids.add(payload["id"])
        except Exception:
            pass
        summary = summarize(message)
        if summary.startswith("tools/call") or summary.startswith("error"):
            logger.info("[%s] << %s", name, summary)
        process.stdin.write(message + "\n")
        process.stdin.flush()


def filter_tool_list(message: str, request_ids: set) -> str:
    """Keep Notion's large catalog below xiaozhi's WebSocket message limit."""
    try:
        payload = json.loads(message)
    except Exception:
        return message

    message_id = payload.get("id")
    if message_id not in request_ids:
        return message
    request_ids.discard(message_id)

    tools = (payload.get("result") or {}).get("tools")
    if not isinstance(tools, list):
        return message

    filtered = [tool for tool in tools if tool.get("name") in ALLOWED_TOOLS]
    payload["result"]["tools"] = filtered
    logger.info(
        "Exposing %s of %s Notion tools: %s",
        len(filtered),
        len(tools),
        ", ".join(tool["name"] for tool in filtered),
    )
    return json.dumps(payload, separators=(",", ":")) + "\n"


async def process_to_websocket(
    process, websocket, name: str, tool_list_request_ids: set
) -> None:
    assert process.stdout is not None
    while True:
        message = await asyncio.to_thread(process.stdout.readline)
        if not message:
            raise RuntimeError(f"{name} MCP process exited")
        message = filter_tool_list(message, tool_list_request_ids)
        await websocket.send(message)


async def process_stderr(process, name: str) -> None:
    assert process.stderr is not None
    while True:
        line = await asyncio.to_thread(process.stderr.readline)
        if not line:
            return
        sys.stderr.write(f"[{name}] {line}")
        sys.stderr.flush()


async def connect(endpoint: str, name: str) -> None:
    process: subprocess.Popen[str] | None = None
    stderr_task: asyncio.Task | None = None
    tool_list_request_ids: set = set()
    try:
        logger.info("[%s] Connecting to xiaozhi...", name)
        async with websockets.connect(endpoint) as websocket:
            logger.info("[%s] Connected to xiaozhi MCP endpoint", name)
            command, env = build_command(name)
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=SCRIPT_DIR,
                env=env,
            )
            logger.info("[%s] Started: %s", name, " ".join(command))
            stderr_task = asyncio.create_task(process_stderr(process, name))
            await asyncio.gather(
                websocket_to_process(
                    websocket, process, name, tool_list_request_ids
                ),
                process_to_websocket(
                    process, websocket, name, tool_list_request_ids
                ),
            )
    finally:
        if stderr_task:
            stderr_task.cancel()
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


async def connect_with_retry(endpoint: str, name: str) -> None:
    delay = INITIAL_BACKOFF
    while True:
        try:
            await connect(endpoint, name)
            delay = INITIAL_BACKOFF
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning("[%s] Disconnected: %s; retrying in %ss", name, error, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, MAX_BACKOFF)


async def main() -> None:
    endpoint = os.environ.get("MCP_ENDPOINT", "").strip()
    if not endpoint:
        raise RuntimeError("Set MCP_ENDPOINT in scripts/mcp_notion/.env")

    servers = load_servers()
    enabled = [
        name for name, entry in servers.items() if not (entry or {}).get("disabled")
    ]
    if not enabled:
        raise RuntimeError("No enabled servers in mcp_config.json")

    logger.info("Starting servers: %s", ", ".join(enabled))
    await asyncio.gather(
        *(connect_with_retry(endpoint, name) for name in enabled)
    )


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped")
