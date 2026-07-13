"""
MCP stdio ↔ WebSocket pipe for the xiaozhi.me cloud MCP endpoint.

Bridges local stdio MCP servers (see mcp_config.json) to the xiaozhi backend.

Usage:
    ./start.sh
    # or:
    python mcp_pipe.py              # all enabled servers in mcp_config.json
    python mcp_pipe.py tapo-lights  # one server by name
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys

import websockets
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "mcp_config.json")
load_dotenv(os.path.join(SCRIPT_DIR, ".env"), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MCP_PIPE")

INITIAL_BACKOFF = 1
MAX_BACKOFF = 600


async def connect_with_retry(uri: str, target: str) -> None:
    reconnect_attempt = 0
    backoff = INITIAL_BACKOFF
    while True:
        try:
            if reconnect_attempt > 0:
                logger.info(
                    "[%s] Waiting %ss before reconnection attempt %s...",
                    target,
                    backoff,
                    reconnect_attempt,
                )
                await asyncio.sleep(backoff)
            await connect_to_server(uri, target)
        except Exception as e:
            reconnect_attempt += 1
            logger.warning(
                "[%s] Connection closed (attempt %s): %s",
                target,
                reconnect_attempt,
                e,
            )
            backoff = min(backoff * 2, MAX_BACKOFF)


async def connect_to_server(uri: str, target: str) -> None:
    process = None
    try:
        logger.info("[%s] Connecting to WebSocket server...", target)
        async with websockets.connect(uri) as websocket:
            logger.info("[%s] Connected to xiaozhi MCP endpoint", target)

            cmd, env = build_server_command(target)
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                text=True,
                env=env,
                cwd=SCRIPT_DIR,
            )
            logger.info("[%s] Started: %s", target, " ".join(cmd))

            stderr_task = asyncio.create_task(
                pipe_process_stderr_to_terminal(process, target)
            )
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process, target),
                pipe_process_to_websocket(process, websocket, target),
            )
            stderr_task.cancel()
    except websockets.exceptions.ConnectionClosed as e:
        logger.error("[%s] WebSocket closed: %s", target, e)
        raise
    except Exception as e:
        logger.error("[%s] Connection error: %s", target, e)
        raise
    finally:
        if process is not None:
            logger.info("[%s] Terminating MCP server process", target)
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _summarize_mcp_message(message: str) -> str:
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
    if "result" in payload:
        return f"result id={payload.get('id')}"
    return message[:160]


def _log_level_for_summary(summary: str) -> int:
    if summary.startswith("tools/call") or summary.startswith("error"):
        return logging.INFO
    return logging.DEBUG


async def pipe_websocket_to_process(websocket, process, target: str) -> None:
    try:
        while True:
            message = await websocket.recv()
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            summary = _summarize_mcp_message(message)
            logger.log(_log_level_for_summary(summary), "[%s] << %s", target, summary)
            process.stdin.write(message + "\n")
            process.stdin.flush()
    except Exception as e:
        logger.error("[%s] WebSocket -> process error: %s", target, e)
        raise
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()


async def pipe_process_to_websocket(process, websocket, target: str) -> None:
    try:
        while True:
            data = await asyncio.to_thread(process.stdout.readline)
            if not data:
                logger.info("[%s] MCP server stdout ended", target)
                break
            summary = _summarize_mcp_message(data)
            logger.log(_log_level_for_summary(summary), "[%s] >> %s", target, summary)
            await websocket.send(data)
    except Exception as e:
        logger.error("[%s] Process -> WebSocket error: %s", target, e)
        raise


async def pipe_process_stderr_to_terminal(process, target: str) -> None:
    try:
        while True:
            data = await asyncio.to_thread(process.stderr.readline)
            if not data:
                break
            sys.stderr.write(f"[{target}] {data}")
            sys.stderr.flush()
    except Exception as e:
        logger.error("[%s] stderr pipe error: %s", target, e)
        raise


def signal_handler(sig, frame) -> None:
    logger.info("Shutting down...")
    sys.exit(0)


def load_config() -> dict:
    path = os.environ.get("MCP_CONFIG") or DEFAULT_CONFIG
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load config %s: %s", path, e)
        return {}


def build_server_command(target: str | None = None):
    if target is None:
        assert len(sys.argv) >= 2, "missing server name"
        target = sys.argv[1]

    cfg = load_config()
    servers = cfg.get("mcpServers", {}) if isinstance(cfg, dict) else {}

    if target in servers:
        entry = servers[target] or {}
        if entry.get("disabled"):
            raise RuntimeError(f"Server '{target}' is disabled in config")

        typ = (entry.get("type") or entry.get("transportType") or "stdio").lower()
        child_env = os.environ.copy()
        child_env["PYTHONUNBUFFERED"] = "1"
        for k, v in (entry.get("env") or {}).items():
            child_env[str(k)] = str(v)

        if typ == "stdio":
            command = entry.get("command")
            args = entry.get("args") or []
            if not command:
                raise RuntimeError(f"Server '{target}' is missing 'command'")
            if command in ("python", "python3") or command.startswith("python3."):
                command = sys.executable
            return [command, *args], child_env

        if typ in ("sse", "http", "streamablehttp"):
            url = entry.get("url")
            if not url:
                raise RuntimeError(f"Server '{target}' (type {typ}) is missing 'url'")
            cmd = [sys.executable, "-m", "mcp_proxy"]
            if typ in ("http", "streamablehttp"):
                cmd += ["--transport", "streamablehttp"]
            for hk, hv in (entry.get("headers") or {}).items():
                cmd += ["-H", hk, str(hv)]
            cmd.append(url)
            return cmd, child_env

        raise RuntimeError(f"Unsupported server type: {typ}")

    if os.path.exists(target):
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        return [sys.executable, target], env

    raise RuntimeError(
        f"'{target}' is not in mcp_config.json and is not a local script path"
    )


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    endpoint_url = os.environ.get("MCP_ENDPOINT")
    if not endpoint_url:
        logger.error(
            "Set MCP_ENDPOINT in scripts/mcp_tapo/.env (copy from .env.example)"
        )
        sys.exit(1)

    if not (
        os.environ.get("KASA_USERNAME") or os.environ.get("TAPO_USERNAME")
    ) or not (
        os.environ.get("KASA_PASSWORD") or os.environ.get("TAPO_PASSWORD")
    ):
        logger.error(
            "Set KASA_USERNAME and KASA_PASSWORD in scripts/mcp_tapo/.env "
            "(exact Tapo app email/password; email is case-sensitive)"
        )
        sys.exit(1)

    if not os.environ.get("TAPO_HOST", "").strip():
        logger.error("Set TAPO_HOST (bulb IPv4) in scripts/mcp_tapo/.env")
        sys.exit(1)

    target_arg = sys.argv[1] if len(sys.argv) >= 2 else None

    async def _main():
        if not target_arg:
            cfg = load_config()
            servers_cfg = cfg.get("mcpServers") or {}
            enabled = [
                name
                for name, entry in servers_cfg.items()
                if not (entry or {}).get("disabled")
            ]
            if not enabled:
                raise RuntimeError("No enabled mcpServers in mcp_config.json")
            logger.info("Starting servers: %s", ", ".join(enabled))
            await asyncio.gather(
                *[
                    asyncio.create_task(connect_with_retry(endpoint_url, name))
                    for name in enabled
                ]
            )
        else:
            await connect_with_retry(endpoint_url, target_arg)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
