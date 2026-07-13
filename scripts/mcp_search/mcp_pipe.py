"""
MCP stdio <-> WebSocket pipe for xiaozhi.me cloud MCP endpoint.

Based on tunforjob/xiaozhi-mcp (MIT). Bridges a local stdio MCP server to the
xiaozhi backend over WebSocket.

Usage:
    export MCP_ENDPOINT="wss://api.xiaozhi.me/mcp/?token=YOUR_TOKEN"
    python3 mcp_pipe.py

Run all servers from mcp_config.json (default):
    python3 mcp_pipe.py

Run a single configured server by name:
    python3 mcp_pipe.py tavily-search
"""

import asyncio
import json
import logging
import os
import signal
import subprocess
import sys

import websockets
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("MCP_PIPE")

INITIAL_BACKOFF = 1
MAX_BACKOFF = 600

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG = os.path.join(SCRIPT_DIR, "mcp_config.json")


async def connect_with_retry(uri, target):
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


async def connect_to_server(uri, target):
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


async def pipe_websocket_to_process(websocket, process, target):
    try:
        while True:
            message = await websocket.recv()
            logger.debug("[%s] << %s...", target, str(message)[:120])
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            process.stdin.write(message + "\n")
            process.stdin.flush()
    except Exception as e:
        logger.error("[%s] WebSocket -> process error: %s", target, e)
        raise
    finally:
        if process.stdin and not process.stdin.closed:
            process.stdin.close()


async def pipe_process_to_websocket(process, websocket, target):
    try:
        while True:
            data = await asyncio.to_thread(process.stdout.readline)
            if not data:
                logger.info("[%s] MCP server stdout ended", target)
                break
            logger.debug("[%s] >> %s...", target, data[:120])
            await websocket.send(data)
    except Exception as e:
        logger.error("[%s] Process -> WebSocket error: %s", target, e)
        raise


async def pipe_process_stderr_to_terminal(process, target):
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


def signal_handler(sig, frame):
    logger.info("Shutting down...")
    sys.exit(0)


def load_config():
    path = os.environ.get("MCP_CONFIG") or DEFAULT_CONFIG
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Failed to load config %s: %s", path, e)
        return {}


def build_server_command(target=None):
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
        for k, v in (entry.get("env") or {}).items():
            child_env[str(k)] = str(v)

        if typ == "stdio":
            command = entry.get("command")
            args = entry.get("args") or []
            if not command:
                raise RuntimeError(f"Server '{target}' is missing 'command'")
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
        return [sys.executable, target], os.environ.copy()

    raise RuntimeError(
        f"'{target}' is not in mcp_config.json and is not a local script path"
    )


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    endpoint_url = os.environ.get("MCP_ENDPOINT")
    if not endpoint_url:
        logger.error(
            "Set MCP_ENDPOINT in scripts/mcp_search/.env "
            "(copy from .env.example)"
        )
        sys.exit(1)

    if not os.environ.get("TAVILY_API_KEY"):
        logger.error(
            "Set TAVILY_API_KEY in scripts/mcp_search/.env "
            "(get one at https://app.tavily.com/)"
        )
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
            tasks = [
                asyncio.create_task(connect_with_retry(endpoint_url, name))
                for name in enabled
            ]
            await asyncio.gather(*tasks)
        else:
            await connect_with_retry(endpoint_url, target_arg)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
