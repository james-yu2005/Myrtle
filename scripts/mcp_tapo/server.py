#!/usr/bin/env python3
"""Thin MCP server for Tapo / Kasa lights via python-kasa (local LAN)."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from kasa import Credentials, Device, DeviceConfig, Discover, Module
from kasa.deviceconfig import DeviceConnectionParameters
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger("tapo-lights")

mcp = FastMCP("tapo-lights")

USERNAME = os.environ.get("KASA_USERNAME") or os.environ.get("TAPO_USERNAME") or ""
PASSWORD = os.environ.get("KASA_PASSWORD") or os.environ.get("TAPO_PASSWORD") or ""
DEFAULT_HOST = os.environ.get("TAPO_HOST", "").strip()

# L535E uses SMART.TAPOBULB + KLAP login_version=2. Direct Device.connect avoids
# UDP discovery (~5–10s), which blows the xiaozhi cloud MCP tool timeout (~10s).
_BULB_CONNECTION = DeviceConnectionParameters.from_values(
    "SMART.TAPOBULB",
    "KLAP",
    login_version=2,
    https=False,
    http_port=80,
)
_CONNECT_TIMEOUT_S = 6.0


def _credentials() -> Credentials:
    if not USERNAME or not PASSWORD:
        raise RuntimeError(
            "Set KASA_USERNAME and KASA_PASSWORD (Tapo/TP-Link account) in .env"
        )
    return Credentials(USERNAME, PASSWORD)


def _resolve_host(host: str | None) -> str:
    """Use a literal IPv4 only. Ignore LLM junk (aliases) that would DNS-hang."""
    candidate = (host or "").strip()
    if candidate:
        try:
            ipaddress.IPv4Address(candidate)
            return candidate
        except ValueError:
            logger.warning("Ignoring non-IP host=%r; using TAPO_HOST", candidate)

    if not DEFAULT_HOST:
        raise RuntimeError(
            "No bulb host. Set TAPO_HOST in .env or pass host= as an IPv4 address."
        )
    try:
        ipaddress.IPv4Address(DEFAULT_HOST)
    except ValueError as e:
        raise RuntimeError(
            f"TAPO_HOST must be an IPv4 address, got {DEFAULT_HOST!r}"
        ) from e
    return DEFAULT_HOST


@asynccontextmanager
async def _device(host: str | None = None):
    target = _resolve_host(host)
    creds = _credentials()
    logger.info("Connecting to %s", target)

    async def _connect():
        config = DeviceConfig(
            host=target,
            credentials=creds,
            connection_type=_BULB_CONNECTION,
            timeout=5,
        )
        dev = await Device.connect(config=config)
        await dev.update()
        return dev

    try:
        dev = await asyncio.wait_for(_connect(), timeout=_CONNECT_TIMEOUT_S)
    except Exception as e:
        logger.exception("Failed to reach bulb at %s", target)
        raise RuntimeError(
            f"Could not reach bulb at {target}: {e}. "
            "Check TAPO_HOST, same Wi‑Fi, email casing, and Third-Party Compatibility."
        ) from e
    try:
        yield dev
    finally:
        try:
            await dev.disconnect()
        except Exception:
            pass


def _light(dev):
    if Module.Light not in dev.modules:
        raise RuntimeError(f"{dev.alias or dev.host} has no Light module")
    return dev.modules[Module.Light]


def _status_dict(dev) -> dict[str, Any]:
    light = _light(dev)
    out: dict[str, Any] = {
        "alias": dev.alias,
        "host": getattr(dev, "host", None),
        "model": getattr(dev, "model", None),
        "is_on": dev.is_on,
    }
    if light.has_feature("brightness"):
        out["brightness"] = light.brightness
    if light.has_feature("hsv"):
        hsv = light.hsv
        out["hsv"] = {"hue": hsv[0], "saturation": hsv[1], "value": hsv[2]}
    if light.has_feature("color_temp"):
        out["color_temp"] = light.color_temp
    return out


@mcp.tool()
async def light_discover() -> str:
    """Discover Tapo/Kasa bulbs on the LAN. Prefer light_on/off with TAPO_HOST set."""
    creds = _credentials()
    found = await asyncio.wait_for(
        Discover.discover(credentials=creds, discovery_timeout=3, timeout=3),
        timeout=8,
    )
    devices = []
    try:
        for ip, dev in found.items():
            devices.append(
                {
                    "host": ip,
                    "alias": getattr(dev, "alias", None),
                    "model": getattr(dev, "model", None),
                    "is_on": getattr(dev, "is_on", None),
                }
            )
    finally:
        for dev in found.values():
            try:
                await dev.disconnect()
            except Exception:
                pass
    logger.info("light_discover found %s device(s)", len(devices))
    return json.dumps({"count": len(devices), "devices": devices}, indent=2)


@mcp.tool()
async def light_status(host: str | None = None) -> str:
    """Get on/off, brightness, color, and color temperature for a bulb.

    Args:
        host: Optional bulb IPv4. Defaults to TAPO_HOST.
    """
    async with _device(host) as dev:
        return json.dumps(_status_dict(dev), indent=2)


@mcp.tool()
async def light_on(host: str | None = None) -> str:
    """Turn the Tapo light on.

    Args:
        host: Optional bulb IPv4. Defaults to TAPO_HOST.
    """
    async with _device(host) as dev:
        await dev.turn_on()
        await dev.update()
        logger.info("light_on ok (%s)", dev.alias)
        return json.dumps({"ok": True, "action": "on", **_status_dict(dev)})


@mcp.tool()
async def light_off(host: str | None = None) -> str:
    """Turn the Tapo light off.

    Args:
        host: Optional bulb IPv4. Defaults to TAPO_HOST.
    """
    async with _device(host) as dev:
        await dev.turn_off()
        await dev.update()
        logger.info("light_off ok (%s)", dev.alias)
        return json.dumps({"ok": True, "action": "off", **_status_dict(dev)})


@mcp.tool()
async def light_set_brightness(brightness: int, host: str | None = None) -> str:
    """Set bulb brightness (1–100). Turns the light on if needed.

    Args:
        brightness: Brightness percent from 1 to 100.
        host: Optional bulb IPv4. Defaults to TAPO_HOST.
    """
    if brightness < 1 or brightness > 100:
        raise ValueError("brightness must be 1–100")
    async with _device(host) as dev:
        light = _light(dev)
        if not light.has_feature("brightness"):
            raise RuntimeError("This device does not support brightness")
        if not dev.is_on:
            await dev.turn_on()
        await light.set_brightness(brightness)
        await dev.update()
        return json.dumps(
            {"ok": True, "action": "set_brightness", **_status_dict(dev)}
        )


@mcp.tool()
async def light_set_color(
    hue: int,
    saturation: int = 100,
    value: int | None = None,
    host: str | None = None,
) -> str:
    """Set bulb color via HSV. Turns the light on if needed.

    Args:
        hue: Hue in degrees 0–360 (0=red, 120=green, 240=blue).
        saturation: Saturation percent 0–100 (default 100).
        value: Brightness/value percent 1–100. Keeps current if omitted.
        host: Optional bulb IPv4. Defaults to TAPO_HOST.
    """
    if hue < 0 or hue > 360:
        raise ValueError("hue must be 0–360")
    if saturation < 0 or saturation > 100:
        raise ValueError("saturation must be 0–100")
    if value is not None and (value < 1 or value > 100):
        raise ValueError("value must be 1–100")

    async with _device(host) as dev:
        light = _light(dev)
        if not light.has_feature("hsv"):
            raise RuntimeError("This device does not support color (HSV)")
        if not dev.is_on:
            await dev.turn_on()
        await light.set_hsv(hue, saturation, value)
        await dev.update()
        return json.dumps({"ok": True, "action": "set_color", **_status_dict(dev)})


@mcp.tool()
async def light_set_color_temp(kelvin: int, host: str | None = None) -> str:
    """Set white color temperature in Kelvin. Turns the light on if needed.

    Args:
        kelvin: Color temperature (typically ~2500–6500 for L535E).
        host: Optional bulb IPv4. Defaults to TAPO_HOST.
    """
    if kelvin < 1000 or kelvin > 10000:
        raise ValueError("kelvin must be 1000–10000")
    async with _device(host) as dev:
        light = _light(dev)
        if not light.has_feature("color_temp"):
            raise RuntimeError("This device does not support color temperature")
        if not dev.is_on:
            await dev.turn_on()
        await light.set_color_temp(kelvin)
        await dev.update()
        return json.dumps(
            {"ok": True, "action": "set_color_temp", **_status_dict(dev)}
        )


if __name__ == "__main__":
    logger.info(
        "starting user=%s host=%s pass_set=%s",
        USERNAME,
        DEFAULT_HOST,
        bool(PASSWORD),
    )
    mcp.run(transport="stdio")
