"""MCP server implementation.

Registers CalDAV operations as MCP tools and wires them to the CalDAVClient.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import CalDAVClient

logger = logging.getLogger(__name__)

mcp = FastMCP("mcp-caldav")


def _get_client() -> CalDAVClient:
    url = os.environ["CALDAV_URL"]
    username = os.environ["CALDAV_USERNAME"]
    password = os.environ["CALDAV_PASSWORD"]
    return CalDAVClient(url=url, username=username, password=password)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def caldav_list_calendars() -> list[dict[str, Any]]:
    """List all available calendars on the configured CalDAV server.

    Returns a list of dicts with keys: uid, name, url.
    """
    return _get_client().list_calendars()


@mcp.tool()
def caldav_create_event(
    calendar_uid: str,
    title: str,
    start: str,
    end: str,
    description: str | None = None,
    location: str | None = None,
    recurrence_rule: str | None = None,
    categories: list[str] | None = None,
    priority: int = 0,
    attendees: list[dict[str, str]] | None = None,
    alarm_minutes: int | None = None,
) -> dict[str, Any]:
    """Create a new calendar event.

    Args:
        calendar_uid: UID or name of the target calendar.
        title: Event summary / title.
        start: Start datetime (ISO 8601, e.g. "2025-03-10T09:00:00Z").
        end: End datetime (ISO 8601).
        description: Optional event description.
        location: Optional event location.
        recurrence_rule: Optional RRULE string, e.g. "FREQ=WEEKLY;BYDAY=MO,WE".
        categories: Optional list of category strings.
        priority: Priority 0-9 (0 = undefined, 1 = highest). Default 0.
        attendees: Optional list of {"email": ..., "name": ..., "status": ...}.
        alarm_minutes: Minutes before the event to trigger a reminder.

    Returns:
        The created event as a dict.
    """
    return _get_client().create_event(
        calendar_uid=calendar_uid,
        title=title,
        start=start,
        end=end,
        description=description,
        location=location,
        recurrence_rule=recurrence_rule,
        categories=categories,
        priority=priority,
        attendees=attendees,
        alarm_minutes=alarm_minutes,
    )


@mcp.tool()
def caldav_update_event(
    event_uid: str,
    calendar_uid: str | None = None,
    title: str | None = None,
    start: str | None = None,
    end: str | None = None,
    description: str | None = None,
    location: str | None = None,
    recurrence_rule: str | None = None,
    categories: list[str] | None = None,
    priority: int | None = None,
) -> dict[str, Any]:
    """Partially update an existing calendar event.

    Only the fields you provide will be changed; all other fields remain as-is.
    Pass an empty string for description or location to clear those fields.

    The SEQUENCE counter is incremented automatically per RFC 5545 so that
    connected clients (e.g. Apple Calendar, Fastmail) detect the change.

    Args:
        event_uid: UID of the event to update (required).
        calendar_uid: Calendar name or UID to search within. When omitted,
                      all calendars are searched (slower but convenient).
        title: New event summary / title.
        start: New start datetime (ISO 8601).
        end: New end datetime (ISO 8601).
        description: New description. Pass "" to remove the existing value.
        location: New location. Pass "" to remove the existing value.
        recurrence_rule: New RRULE string. Pass "" to remove recurrence.
        categories: Replacement category list. Pass [] to clear.
        priority: New priority value (0–9).

    Returns:
        The updated event as a dict (same shape as caldav_get_event_by_uid).
    """
    return _get_client().update_event(
        event_uid=event_uid,
        calendar_uid=calendar_uid,
        title=title,
        start=start,
        end=end,
        description=description,
        location=location,
        recurrence_rule=recurrence_rule,
        categories=categories,
        priority=priority,
    )


@mcp.tool()
def caldav_get_events(
    calendar_uid: str,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """Get events within a date range from a specific calendar.

    Args:
        calendar_uid: UID or name of the calendar.
        start: Start of the range (ISO 8601).
        end: End of the range (ISO 8601).

    Returns:
        List of event dicts with extended fields including UID, categories,
        priority, attendees, and recurrence info.
    """
    return _get_client().get_events(calendar_uid=calendar_uid, start=start, end=end)


@mcp.tool()
def caldav_get_today_events(calendar_uid: str | None = None) -> list[dict[str, Any]]:
    """Get all events for today (00:00 – 23:59 local UTC).

    Args:
        calendar_uid: If given, restrict to this calendar.

    Returns:
        List of event dicts.
    """
    return _get_client().get_today_events(calendar_uid=calendar_uid)


@mcp.tool()
def caldav_get_week_events(
    calendar_uid: str | None = None,
    start_monday: bool = False,
) -> list[dict[str, Any]]:
    """Get events for the current week.

    Args:
        calendar_uid: If given, restrict to this calendar.
        start_monday: If True, the week starts on Monday; otherwise it starts today.

    Returns:
        List of event dicts.
    """
    return _get_client().get_week_events(calendar_uid=calendar_uid, start_monday=start_monday)


@mcp.tool()
def caldav_get_event_by_uid(
    event_uid: str,
    calendar_uid: str | None = None,
) -> dict[str, Any]:
    """Get a single event by its UID.

    Args:
        event_uid: The iCalendar UID of the event.
        calendar_uid: If given, only this calendar is searched.

    Returns:
        Event dict, or raises ValueError if not found.
    """
    return _get_client().get_event_by_uid(event_uid=event_uid, calendar_uid=calendar_uid)


@mcp.tool()
def caldav_delete_event(
    event_uid: str,
    calendar_uid: str | None = None,
) -> bool:
    """Delete an event by its UID.

    Args:
        event_uid: The iCalendar UID of the event to delete.
        calendar_uid: If given, only this calendar is searched.

    Returns:
        True on success, raises ValueError if not found.
    """
    return _get_client().delete_event(event_uid=event_uid, calendar_uid=calendar_uid)


@mcp.tool()
def caldav_search_events(
    query: str | None = None,
    attendee: str | None = None,
    location: str | None = None,
    calendar_uid: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    """Search events by text, attendee email, or location.

    Args:
        query: Free-text search against title and description.
        attendee: Filter by attendee email address.
        location: Filter by location (substring match).
        calendar_uid: Restrict search to one calendar (optional).
        start: Earliest event start to include (ISO 8601, optional).
        end: Latest event start to include (ISO 8601, optional).

    Returns:
        Matching event dicts.
    """
    return _get_client().search_events(
        query=query,
        attendee=attendee,
        location=location,
        calendar_uid=calendar_uid,
        start=start,
        end=end,
    )
