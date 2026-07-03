"""
MCP stdio <-> WebSocket pipe for xiaozhi.me MCP endpoint.
Based on https://github.com/78/mcp-calculator (v0.2.0)

Usage (PowerShell):
    $env:MCP_ENDPOINT = "wss://api.xiaozhi.me/mcp/?token=YOUR_TOKEN"
    python mcp_pipe.py stock_mcp.py

Or with .env file in this directory:
    python mcp_pipe.py stock_mcp.py
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
                "[%s] Connection closed (attempt %s): %s", target, reconnect_attempt, e
            )
            backoff = min(backoff * 2, MAX_BACKOFF)


async def connect_to_server(uri, target):
    process = None
    try:
        logger.info("[%s] Connecting to WebSocket server...", target)
        async with websockets.connect(uri) as websocket:
            logger.info("[%s] Successfully connected to WebSocket server", target)

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
            logger.info("[%s] Started server process: %s", target, " ".join(cmd))

            await asyncio.gather(
                pipe_websocket_to_process(websocket, process, target),
                pipe_process_to_websocket(process, websocket, target),
                pipe_process_stderr_to_terminal(process, target),
            )
    except websockets.exceptions.ConnectionClosed as e:
        logger.error("[%s] WebSocket connection closed: %s", target, e)
        raise
    except Exception as e:
        logger.error("[%s] Connection error: %s", target, e)
        raise
    finally:
        if process is not None:
            logger.info("[%s] Terminating server process", target)
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            logger.info("[%s] Server process terminated", target)


async def pipe_websocket_to_process(websocket, process, target):
    try:
        while True:
            message = await websocket.recv()
            logger.debug("[%s] << %s...", target, message[:120])
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            process.stdin.write(message + "\n")
            process.stdin.flush()
    except Exception as e:
        logger.error("[%s] Error in WebSocket to process pipe: %s", target, e)
        raise
    finally:
        if not process.stdin.closed:
            process.stdin.close()


async def pipe_process_to_websocket(process, websocket, target):
    try:
        while True:
            data = await asyncio.to_thread(process.stdout.readline)
            if not data:
                logger.info("[%s] Process has ended output", target)
                break
            logger.debug("[%s] >> %s...", target, data[:120])
            await websocket.send(data)
    except Exception as e:
        logger.error("[%s] Error in process to WebSocket pipe: %s", target, e)
        raise


async def pipe_process_stderr_to_terminal(process, target):
    try:
        while True:
            data = await asyncio.to_thread(process.stderr.readline)
            if not data:
                logger.info("[%s] Process has ended stderr output", target)
                break
            sys.stderr.write(data)
            sys.stderr.flush()
    except Exception as e:
        logger.error("[%s] Error in process stderr pipe: %s", target, e)
        raise


def signal_handler(sig, frame):
    logger.info("Received interrupt signal, shutting down...")
    sys.exit(0)


def load_config():
    path = os.environ.get("MCP_CONFIG") or os.path.join(os.getcwd(), "mcp_config.json")
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
        assert len(sys.argv) >= 2, "missing server name or script path"
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
            headers = entry.get("headers") or {}
            for hk, hv in headers.items():
                cmd += ["-H", hk, str(hv)]
            cmd.append(url)
            return cmd, child_env

        raise RuntimeError(f"Unsupported server type: {typ}")

    script_path = target
    if not os.path.exists(script_path):
        raise RuntimeError(
            f"'{target}' is neither a configured server nor an existing script"
        )
    return [sys.executable, script_path], os.environ.copy()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)

    endpoint_url = os.environ.get("MCP_ENDPOINT")
    if not endpoint_url:
        logger.error("Please set MCP_ENDPOINT (env var or .env file)")
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
                raise RuntimeError("No enabled mcpServers found in config")
            logger.info("Starting servers: %s", ", ".join(enabled))
            tasks = [
                asyncio.create_task(connect_with_retry(endpoint_url, t))
                for t in enabled
            ]
            await asyncio.gather(*tasks)
        else:
            if os.path.exists(target_arg):
                await connect_with_retry(endpoint_url, target_arg)
            else:
                logger.error(
                    "Argument must be a local Python script path. "
                    "To run configured servers, run without arguments."
                )
                sys.exit(1)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    except Exception as e:
        logger.error("Program execution error: %s", e)
