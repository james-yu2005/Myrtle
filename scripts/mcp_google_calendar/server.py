#!/usr/bin/env python3
"""Google Calendar MCP server for Desk Chat (OAuth + Calendar API v3)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(SCRIPT_DIR / ".env", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger("google-calendar")

mcp = FastMCP("google-calendar")

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
TOKEN_PATH = SCRIPT_DIR / ".google-token.json"
DEFAULT_CREDENTIALS_FILE = SCRIPT_DIR / "credentials.json"

CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary").strip() or "primary"
TIMEZONE_NAME = (
    os.environ.get("GOOGLE_CALENDAR_TIMEZONE", "America/New_York").strip()
    or "America/New_York"
)

_service = None
_auth_lock = asyncio.Lock()


def _local_tz() -> ZoneInfo:
    try:
        return ZoneInfo(TIMEZONE_NAME)
    except Exception as e:
        raise RuntimeError(
            f"Invalid GOOGLE_CALENDAR_TIMEZONE={TIMEZONE_NAME!r}: {e}"
        ) from e


def _client_secrets_path() -> Path | None:
    explicit = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = SCRIPT_DIR / path
        return path
    if DEFAULT_CREDENTIALS_FILE.is_file():
        return DEFAULT_CREDENTIALS_FILE
    return None


def _client_config_from_env() -> dict[str, Any] | None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _oauth_setup_hint() -> str:
    return (
        "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env, or add "
        "credentials.json (Desktop OAuth client) in scripts/mcp_google_calendar/. "
        "Enable Google Calendar API in Google Cloud Console."
    )


def _load_credentials() -> Credentials:
    creds: Credentials | None = None
    if TOKEN_PATH.is_file():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        logger.info("Refreshed Google OAuth token")
        return creds

    secrets_path = _client_secrets_path()
    client_config = _client_config_from_env()
    if secrets_path:
        flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    elif client_config:
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    else:
        raise RuntimeError(_oauth_setup_hint())

    logger.info("Opening browser for Google Calendar authorization (one-time setup)...")
    creds = flow.run_local_server(port=0, open_browser=True)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    logger.info("Saved OAuth token to %s", TOKEN_PATH.name)
    return creds


def _get_service():
    global _service
    if _service is not None:
        return _service
    creds = _load_credentials()
    _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service


async def _with_service():
    async with _auth_lock:
        return await asyncio.to_thread(_get_service)


def _parse_event_time(value: str, field: str) -> dict[str, str]:
    """Return Google Calendar dateTime or date dict."""
    raw = value.strip()
    if not raw:
        raise ValueError(f"{field} is required")

    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        return {"date": raw}

    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_local_tz())
    return {"dateTime": parsed.isoformat(), "timeZone": TIMEZONE_NAME}


def _format_event(item: dict[str, Any]) -> dict[str, Any]:
    start = item.get("start") or {}
    end = item.get("end") or {}
    return {
        "id": item.get("id"),
        "summary": item.get("summary") or "(no title)",
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "location": item.get("location"),
        "htmlLink": item.get("htmlLink"),
        "status": item.get("status"),
    }


@mcp.tool()
async def calendar_list_upcoming(
    days: int = 7,
    max_results: int = 10,
    calendar_id: str | None = None,
) -> str:
    """List upcoming events on the user's Google Calendar.

    Args:
        days: How many days ahead to search from now (1–30).
        max_results: Maximum events to return (1–50).
        calendar_id: Optional calendar ID; defaults to GOOGLE_CALENDAR_ID (usually primary).
    """
    if days < 1 or days > 30:
        raise ValueError("days must be 1–30")
    if max_results < 1 or max_results > 50:
        raise ValueError("max_results must be 1–50")

    cal = (calendar_id or CALENDAR_ID).strip() or "primary"
    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=days)

    def _list():
        service = _get_service()
        result = (
            service.events()
            .list(
                calendarId=cal,
                timeMin=now.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        items = result.get("items") or []
        return {
            "calendar_id": cal,
            "count": len(items),
            "events": [_format_event(item) for item in items],
        }

    try:
        await _with_service()
        payload = await asyncio.to_thread(_list)
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}") from e

    logger.info(
        "calendar_list_upcoming cal=%s count=%s days=%s",
        cal,
        payload["count"],
        days,
    )
    return json.dumps(payload, indent=2)


@mcp.tool()
async def calendar_create_event(
    summary: str,
    start: str,
    end: str,
    description: str | None = None,
    location: str | None = None,
    calendar_id: str | None = None,
) -> str:
    """Create a calendar event.

    Args:
        summary: Event title.
        start: Start time as ISO 8601 (2026-07-26T15:00:00) or all-day date (2026-07-26).
        end: End time (same formats as start). For all-day events, end date is exclusive.
        description: Optional notes or agenda.
        location: Optional location string.
        calendar_id: Optional calendar ID; defaults to GOOGLE_CALENDAR_ID.
    """
    title = summary.strip()
    if not title:
        raise ValueError("summary is required")

    cal = (calendar_id or CALENDAR_ID).strip() or "primary"
    body: dict[str, Any] = {
        "summary": title,
        "start": _parse_event_time(start, "start"),
        "end": _parse_event_time(end, "end"),
    }
    if description and description.strip():
        body["description"] = description.strip()
    if location and location.strip():
        body["location"] = location.strip()

    def _insert():
        service = _get_service()
        created = (
            service.events().insert(calendarId=cal, body=body).execute()
        )
        return {"ok": True, "calendar_id": cal, "event": _format_event(created)}

    try:
        await _with_service()
        payload = await asyncio.to_thread(_insert)
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}") from e

    logger.info("calendar_create_event cal=%s summary=%r", cal, title)
    return json.dumps(payload, indent=2)


@mcp.tool()
async def calendar_list_calendars(max_results: int = 20) -> str:
    """List Google Calendars the user can access (helps pick calendar_id).

    Args:
        max_results: Maximum calendars to return (1–50).
    """
    if max_results < 1 or max_results > 50:
        raise ValueError("max_results must be 1–50")

    def _list_cals():
        service = _get_service()
        result = (
            service.calendarList()
            .list(maxResults=max_results, minAccessRole="writer")
            .execute()
        )
        items = result.get("items") or []
        calendars = [
            {
                "id": item.get("id"),
                "summary": item.get("summary"),
                "primary": item.get("primary", False),
                "accessRole": item.get("accessRole"),
            }
            for item in items
        ]
        return {"count": len(calendars), "calendars": calendars}

    try:
        await _with_service()
        payload = await asyncio.to_thread(_list_cals)
    except HttpError as e:
        raise RuntimeError(f"Google Calendar API error: {e}") from e

    return json.dumps(payload, indent=2)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--authorize":
        _load_credentials()
        print("Authorization complete. Token saved.", file=sys.stderr)
        sys.exit(0)

    logger.info(
        "starting calendar_id=%s timezone=%s token=%s",
        CALENDAR_ID,
        TIMEZONE_NAME,
        TOKEN_PATH.is_file(),
    )
    mcp.run(transport="stdio")
