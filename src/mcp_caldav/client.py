"""CalDAV client wrapper.

Wraps the python-caldav library with a clean interface for the MCP server.
This module is intentionally kept free of MCP concerns.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

import caldav
from caldav import DAVClient
from icalendar import Calendar, vDatetime, vText
from icalendar import Event as iCalEvent

logger = logging.getLogger(__name__)


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO 8601 datetime string, returning a timezone-aware datetime."""
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime string: {value!r}")


def _serialize_dt(dt: date | datetime | None) -> str | None:
    """Serialize a date or datetime to ISO 8601 string."""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return dt.isoformat()


def _extract_event(vevent: Any) -> dict[str, Any]:
    """Extract a VEVENT component into a plain dict."""
    attendees = []
    raw_attendees = vevent.get("ATTENDEE", [])
    if not isinstance(raw_attendees, list):
        raw_attendees = [raw_attendees]
    for att in raw_attendees:
        partstat = att.params.get("PARTSTAT", "NEEDS-ACTION") if hasattr(att, "params") else "NEEDS-ACTION"
        cn = att.params.get("CN", str(att)) if hasattr(att, "params") else str(att)
        attendees.append({"email": str(att).replace("mailto:", ""), "name": cn, "status": partstat})

    categories: list[str] = []
    raw_cats = vevent.get("CATEGORIES", [])
    if raw_cats:
        if not isinstance(raw_cats, list):
            raw_cats = [raw_cats]
        for cat in raw_cats:
            if hasattr(cat, "cats"):
                categories.extend(str(c) for c in cat.cats)
            else:
                categories.append(str(cat))

    rrule = None
    if "RRULE" in vevent:
        rrule = vevent["RRULE"].to_ical().decode()

    alarms: list[dict[str, Any]] = []
    for component in vevent.subcomponents:
        if component.name == "VALARM":
            trigger = component.get("TRIGGER")
            alarms.append({"trigger": str(trigger) if trigger else None})

    return {
        "uid": str(vevent.get("UID", "")),
        "title": str(vevent.get("SUMMARY", "")),
        "description": str(vevent.get("DESCRIPTION", "")) if vevent.get("DESCRIPTION") else None,
        "location": str(vevent.get("LOCATION", "")) if vevent.get("LOCATION") else None,
        "start": _serialize_dt(vevent.get("DTSTART", {}).dt if vevent.get("DTSTART") else None),
        "end": _serialize_dt(vevent.get("DTEND", {}).dt if vevent.get("DTEND") else None),
        "recurrence_rule": rrule,
        "categories": categories,
        "priority": int(str(vevent.get("PRIORITY", 0))) if vevent.get("PRIORITY") else 0,
        "attendees": attendees,
        "alarms": alarms,
        "sequence": int(str(vevent.get("SEQUENCE", 0))) if vevent.get("SEQUENCE") else 0,
    }


class CalDAVClient:
    """Thread-safe wrapper around python-caldav for use by the MCP server."""

    def __init__(self, url: str, username: str, password: str) -> None:
        self._url = url
        self._username = username
        self._password = password
        self._dav: DAVClient | None = None
        self._principal: Any = None

    def _connect(self) -> None:
        if self._dav is None:
            self._dav = DAVClient(url=self._url, username=self._username, password=self._password)
            self._principal = self._dav.principal()

    def _get_calendar_by_uid(self, calendar_uid: str) -> Any:
        self._connect()
        for cal in self._principal.calendars():
            if str(cal.id) == calendar_uid or (cal.name and str(cal.name) == calendar_uid):
                return cal
        raise ValueError(f"Calendar not found: {calendar_uid!r}")

    def _find_event_by_uid(self, event_uid: str, calendar_uid: str | None = None) -> tuple[Any, Any]:
        """Return (calendar, event) for the given event UID.

        If calendar_uid is given, only that calendar is searched; otherwise all
        calendars are searched in order.
        """
        self._connect()
        calendars = (
            [self._get_calendar_by_uid(calendar_uid)]
            if calendar_uid
            else self._principal.calendars()
        )
        for cal in calendars:
            try:
                event = cal.object_by_uid(event_uid)
                return cal, event
            except caldav.error.NotFoundError:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.debug("Error searching calendar %s for UID %s: %s", cal.name, event_uid, exc)
                continue
        raise ValueError(f"Event with UID {event_uid!r} not found")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_calendars(self) -> list[dict[str, Any]]:
        """Return a list of all accessible calendars."""
        self._connect()
        result = []
        for cal in self._principal.calendars():
            result.append({
                "uid": str(cal.id),
                "name": str(cal.name) if cal.name else None,
                "url": str(cal.url),
            })
        return result

    def create_event(
        self,
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
        """Create a new event and return its serialized form."""
        cal = self._get_calendar_by_uid(calendar_uid)

        dtstart = _parse_datetime(start)
        dtend = _parse_datetime(end)

        kwargs: dict[str, Any] = {
            "dtstart": dtstart,
            "dtend": dtend,
            "summary": title,
        }
        if description:
            kwargs["description"] = description
        if location:
            kwargs["location"] = location

        event = cal.save_event(**kwargs)

        # Apply fields not supported by save_event kwargs directly
        with event.edit_icalendar_instance() as ical:
            for comp in ical.subcomponents:
                if comp.name != "VEVENT":
                    continue
                if recurrence_rule:
                    from icalendar import vRecur
                    comp["RRULE"] = vRecur.from_ical(recurrence_rule)
                if categories:
                    from icalendar import vCategory
                    comp["CATEGORIES"] = categories
                if priority:
                    comp["PRIORITY"] = priority
                if attendees:
                    for att in attendees:
                        from icalendar import vCalAddress
                        a = vCalAddress(f"mailto:{att['email']}")
                        a.params["CN"] = att.get("name", att["email"])
                        a.params["PARTSTAT"] = att.get("status", "NEEDS-ACTION")
                        comp.add("ATTENDEE", a)
                if alarm_minutes is not None:
                    from datetime import timedelta
                    from icalendar import Alarm
                    alarm = Alarm()
                    alarm.add("action", "DISPLAY")
                    alarm.add("trigger", timedelta(minutes=-alarm_minutes))
                    comp.add_component(alarm)

        # Re-fetch to return fully populated data
        _, refreshed = self._find_event_by_uid(
            str(event.icalendar_instance.subcomponents[0].get("UID", "")),
            calendar_uid,
        )
        ical_instance = refreshed.icalendar_instance
        for comp in ical_instance.subcomponents:
            if comp.name == "VEVENT":
                return _extract_event(comp)
        return {}

    def get_events(
        self,
        calendar_uid: str,
        start: str,
        end: str,
    ) -> list[dict[str, Any]]:
        """Return events in the given date range from the specified calendar."""
        cal = self._get_calendar_by_uid(calendar_uid)
        dtstart = _parse_datetime(start)
        dtend = _parse_datetime(end)

        results = cal.search(start=dtstart, end=dtend, event=True, expand=True)
        events = []
        for obj in results:
            for comp in obj.icalendar_instance.subcomponents:
                if comp.name == "VEVENT":
                    events.append(_extract_event(comp))
        return events

    def get_today_events(self, calendar_uid: str | None = None) -> list[dict[str, Any]]:
        """Return all events for today across all calendars (or one calendar)."""
        now = datetime.now(tz=timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        self._connect()
        calendars = (
            [self._get_calendar_by_uid(calendar_uid)]
            if calendar_uid
            else self._principal.calendars()
        )
        events: list[dict[str, Any]] = []
        for cal in calendars:
            try:
                results = cal.search(start=today_start, end=today_end, event=True, expand=True)
                for obj in results:
                    for comp in obj.icalendar_instance.subcomponents:
                        if comp.name == "VEVENT":
                            events.append(_extract_event(comp))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to get today events for calendar %s: %s", cal.name, exc)
        return events

    def get_week_events(self, calendar_uid: str | None = None, start_monday: bool = False) -> list[dict[str, Any]]:
        """Return events for the current week."""
        from datetime import timedelta
        now = datetime.now(tz=timezone.utc)
        if start_monday:
            days_since_monday = now.weekday()
            week_start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        self._connect()
        calendars = (
            [self._get_calendar_by_uid(calendar_uid)]
            if calendar_uid
            else self._principal.calendars()
        )
        events: list[dict[str, Any]] = []
        for cal in calendars:
            try:
                results = cal.search(start=week_start, end=week_end, event=True, expand=True)
                for obj in results:
                    for comp in obj.icalendar_instance.subcomponents:
                        if comp.name == "VEVENT":
                            events.append(_extract_event(comp))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to get week events for calendar %s: %s", cal.name, exc)
        return events

    def get_event_by_uid(self, event_uid: str, calendar_uid: str | None = None) -> dict[str, Any]:
        """Return a single event by UID."""
        _, event = self._find_event_by_uid(event_uid, calendar_uid)
        for comp in event.icalendar_instance.subcomponents:
            if comp.name == "VEVENT":
                return _extract_event(comp)
        raise ValueError(f"VEVENT component not found in object {event_uid!r}")

    def delete_event(self, event_uid: str, calendar_uid: str | None = None) -> bool:
        """Delete an event by UID. Returns True if deleted."""
        _, event = self._find_event_by_uid(event_uid, calendar_uid)
        event.delete()
        return True

    def search_events(
        self,
        query: str | None = None,
        attendee: str | None = None,
        location: str | None = None,
        calendar_uid: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search events by text, attendee email, or location."""
        self._connect()
        calendars = (
            [self._get_calendar_by_uid(calendar_uid)]
            if calendar_uid
            else self._principal.calendars()
        )
        dtstart = _parse_datetime(start) if start else None
        dtend = _parse_datetime(end) if end else None
        results: list[dict[str, Any]] = []

        for cal in calendars:
            try:
                objs = cal.search(
                    start=dtstart,
                    end=dtend,
                    event=True,
                    expand=True,
                )
                for obj in objs:
                    for comp in obj.icalendar_instance.subcomponents:
                        if comp.name != "VEVENT":
                            continue
                        ev = _extract_event(comp)
                        # Client-side filtering (server search support varies)
                        if query:
                            q = query.lower()
                            text = " ".join(filter(None, [ev.get("title"), ev.get("description")])).lower()
                            if q not in text:
                                continue
                        if attendee:
                            emails = [a["email"].lower() for a in ev.get("attendees", [])]
                            if attendee.lower() not in emails:
                                continue
                        if location:
                            if location.lower() not in (ev.get("location") or "").lower():
                                continue
                        results.append(ev)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to search calendar %s: %s", cal.name, exc)
        return results

    def update_event(
        self,
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
        """Partially update an existing event.

        Only the fields provided (non-None) will be changed.  The SEQUENCE
        counter is incremented automatically as required by RFC 5545 §3.8.7.4
        so that CalDAV servers and connected clients can detect the change.

        Args:
            event_uid: UID of the event to update.
            calendar_uid: Calendar name or UID to search within (optional;
                          searches all calendars when omitted).
            title: New summary/title.
            start: New start datetime (ISO 8601 string).
            end: New end datetime (ISO 8601 string).
            description: New description (pass empty string to clear).
            location: New location (pass empty string to clear).
            recurrence_rule: New RRULE string, e.g. "FREQ=WEEKLY;BYDAY=MO".
            categories: Replacement category list.
            priority: New priority value (0–9, 0 = undefined / highest).

        Returns:
            The updated event as a dict (same shape as get_event_by_uid).

        Raises:
            ValueError: If the event cannot be found.
        """
        if all(v is None for v in (title, start, end, description, location, recurrence_rule, categories, priority)):
            # Nothing to do - return current state
            return self.get_event_by_uid(event_uid, calendar_uid)

        _, event = self._find_event_by_uid(event_uid, calendar_uid)

        with event.edit_icalendar_instance() as ical:
            for comp in ical.subcomponents:
                if comp.name != "VEVENT":
                    continue

                if title is not None:
                    comp["SUMMARY"] = vText(title)

                if start is not None:
                    dtstart = _parse_datetime(start)
                    if "DTSTART" in comp:
                        del comp["DTSTART"]
                    comp.add("DTSTART", dtstart)

                if end is not None:
                    dtend = _parse_datetime(end)
                    if "DTEND" in comp:
                        del comp["DTEND"]
                    comp.add("DTEND", dtend)

                if description is not None:
                    if "DESCRIPTION" in comp:
                        del comp["DESCRIPTION"]
                    if description:  # empty string = clear field
                        comp["DESCRIPTION"] = vText(description)

                if location is not None:
                    if "LOCATION" in comp:
                        del comp["LOCATION"]
                    if location:
                        comp["LOCATION"] = vText(location)

                if recurrence_rule is not None:
                    if "RRULE" in comp:
                        del comp["RRULE"]
                    if recurrence_rule:
                        from icalendar import vRecur
                        comp["RRULE"] = vRecur.from_ical(recurrence_rule)

                if categories is not None:
                    if "CATEGORIES" in comp:
                        del comp["CATEGORIES"]
                    if categories:
                        comp.add("CATEGORIES", categories)

                if priority is not None:
                    comp["PRIORITY"] = priority

                # RFC 5545 §3.8.7.4: increment SEQUENCE on every update
                current_seq = int(str(comp.get("SEQUENCE", 0)))
                if "SEQUENCE" in comp:
                    del comp["SEQUENCE"]
                comp.add("SEQUENCE", current_seq + 1)

                # Update modification timestamps
                now = datetime.now(tz=timezone.utc)
                for field in ("LAST-MODIFIED", "DTSTAMP"):
                    if field in comp:
                        del comp[field]
                comp.add("LAST-MODIFIED", now)
                comp.add("DTSTAMP", now)

        # Re-fetch to return the server's canonical representation
        _, refreshed = self._find_event_by_uid(event_uid, calendar_uid)
        for comp in refreshed.icalendar_instance.subcomponents:
            if comp.name == "VEVENT":
                return _extract_event(comp)
        raise ValueError(f"VEVENT component missing after update for UID {event_uid!r}")
