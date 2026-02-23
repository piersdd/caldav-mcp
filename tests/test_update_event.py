"""Unit tests for CalDAVClient.update_event.

These tests use unittest.mock so no live CalDAV server is required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call
from contextlib import contextmanager

import pytest
from icalendar import Calendar, Event as iCalEvent, vText

from mcp_caldav.client import CalDAVClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_UID = "test-event-uid-001@example.com"

def _make_ical_event(
    uid: str = SAMPLE_UID,
    summary: str = "Original Title",
    dtstart: datetime | None = None,
    dtend: datetime | None = None,
    description: str | None = None,
    location: str | None = None,
    sequence: int = 0,
) -> Calendar:
    """Build a minimal VCALENDAR wrapping a VEVENT."""
    if dtstart is None:
        dtstart = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)
    if dtend is None:
        dtend = datetime(2025, 6, 1, 11, 0, 0, tzinfo=timezone.utc)

    cal = Calendar()
    cal.add("prodid", "-//test//test//EN")
    cal.add("version", "2.0")

    vevent = iCalEvent()
    vevent.add("uid", uid)
    vevent.add("summary", summary)
    vevent.add("dtstart", dtstart)
    vevent.add("dtend", dtend)
    vevent.add("dtstamp", datetime(2025, 1, 1, tzinfo=timezone.utc))
    vevent.add("sequence", sequence)
    if description:
        vevent.add("description", description)
    if location:
        vevent.add("location", location)

    cal.add_component(vevent)
    return cal


def _mock_caldav_event(cal_obj: Calendar) -> MagicMock:
    """Build a mock caldav Event whose icalendar_instance returns cal_obj."""
    mock_event = MagicMock()
    mock_event.icalendar_instance = cal_obj

    # edit_icalendar_instance() should be a context manager that yields cal_obj
    # and saves on exit (simulated by no-op).
    @contextmanager
    def _edit_ctx():
        yield cal_obj

    mock_event.edit_icalendar_instance = _edit_ctx
    mock_event.save = MagicMock()
    return mock_event


def _make_client_with_event(cal_obj: Calendar) -> tuple[CalDAVClient, MagicMock]:
    """Return a CalDAVClient wired to a mock principal containing one event."""
    client = CalDAVClient(url="http://localhost/", username="u", password="p")

    mock_event = _mock_caldav_event(cal_obj)

    mock_calendar = MagicMock()
    mock_calendar.id = "personal"
    mock_calendar.name = "Personal"
    mock_calendar.object_by_uid = MagicMock(return_value=mock_event)

    mock_principal = MagicMock()
    mock_principal.calendars = MagicMock(return_value=[mock_calendar])

    mock_dav_client = MagicMock()
    mock_dav_client.principal = MagicMock(return_value=mock_principal)

    # Patch DAVClient so _connect() uses our mock
    with patch("mcp_caldav.client.DAVClient", return_value=mock_dav_client):
        client._connect()

    return client, mock_calendar


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateEventTitle:
    def test_title_is_updated(self) -> None:
        cal_obj = _make_ical_event(summary="Old Title")
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID, title="New Title")

        assert result["title"] == "New Title"

    def test_original_title_preserved_when_not_given(self) -> None:
        cal_obj = _make_ical_event(summary="Keep This")
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID, description="Only description changed")

        assert result["title"] == "Keep This"


class TestUpdateEventDatetime:
    def test_start_is_updated(self) -> None:
        cal_obj = _make_ical_event()
        client, _ = _make_client_with_event(cal_obj)

        new_start = "2025-07-15T09:00:00Z"
        result = client.update_event(event_uid=SAMPLE_UID, start=new_start)

        # The stored datetime should match the requested one
        assert "2025-07-15" in result["start"]

    def test_end_is_updated(self) -> None:
        cal_obj = _make_ical_event()
        client, _ = _make_client_with_event(cal_obj)

        new_end = "2025-07-15T10:30:00Z"
        result = client.update_event(event_uid=SAMPLE_UID, end=new_end)

        assert "2025-07-15" in result["end"]


class TestUpdateEventTextFields:
    def test_description_is_set(self) -> None:
        cal_obj = _make_ical_event()
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID, description="A new description")

        assert result["description"] == "A new description"

    def test_description_is_cleared_by_empty_string(self) -> None:
        cal_obj = _make_ical_event(description="Remove me")
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID, description="")

        assert not result.get("description")

    def test_location_is_set(self) -> None:
        cal_obj = _make_ical_event()
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID, location="Sydney, NSW")

        assert result["location"] == "Sydney, NSW"

    def test_location_is_cleared_by_empty_string(self) -> None:
        cal_obj = _make_ical_event(location="Old Location")
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID, location="")

        assert not result.get("location")


class TestUpdateEventSequence:
    def test_sequence_is_incremented_from_zero(self) -> None:
        cal_obj = _make_ical_event(sequence=0)
        client, _ = _make_client_with_event(cal_obj)

        client.update_event(event_uid=SAMPLE_UID, title="Updated")

        # Inspect the modified ical object directly
        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                assert int(str(comp.get("SEQUENCE"))) == 1

    def test_sequence_is_incremented_from_existing_value(self) -> None:
        cal_obj = _make_ical_event(sequence=5)
        client, _ = _make_client_with_event(cal_obj)

        client.update_event(event_uid=SAMPLE_UID, title="Updated again")

        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                assert int(str(comp.get("SEQUENCE"))) == 6

    def test_dtstamp_is_refreshed(self) -> None:
        original_dtstamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
        cal_obj = _make_ical_event()
        # Manually set an old dtstamp
        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                if "DTSTAMP" in comp:
                    del comp["DTSTAMP"]
                comp.add("DTSTAMP", original_dtstamp)

        client, _ = _make_client_with_event(cal_obj)
        client.update_event(event_uid=SAMPLE_UID, title="Bump dtstamp")

        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                new_dtstamp = comp.get("DTSTAMP").dt
                assert new_dtstamp > original_dtstamp


class TestUpdateEventNoOp:
    def test_returns_current_event_when_no_fields_given(self) -> None:
        cal_obj = _make_ical_event(summary="Unchanged")
        client, _ = _make_client_with_event(cal_obj)

        result = client.update_event(event_uid=SAMPLE_UID)

        assert result["title"] == "Unchanged"

    def test_sequence_not_incremented_when_no_fields_given(self) -> None:
        cal_obj = _make_ical_event(sequence=3)
        client, _ = _make_client_with_event(cal_obj)

        client.update_event(event_uid=SAMPLE_UID)

        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                assert int(str(comp.get("SEQUENCE"))) == 3


class TestUpdateEventRecurrence:
    def test_recurrence_rule_is_set(self) -> None:
        cal_obj = _make_ical_event()
        client, _ = _make_client_with_event(cal_obj)

        client.update_event(event_uid=SAMPLE_UID, recurrence_rule="FREQ=WEEKLY;BYDAY=MO")

        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                assert "RRULE" in comp

    def test_recurrence_rule_is_removed_by_empty_string(self) -> None:
        cal_obj = _make_ical_event()
        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                from icalendar import vRecur
                comp["RRULE"] = vRecur.from_ical("FREQ=DAILY")

        client, _ = _make_client_with_event(cal_obj)
        client.update_event(event_uid=SAMPLE_UID, recurrence_rule="")

        for comp in cal_obj.subcomponents:
            if comp.name == "VEVENT":
                assert "RRULE" not in comp


class TestUpdateEventNotFound:
    def test_raises_value_error_for_unknown_uid(self) -> None:
        cal_obj = _make_ical_event()
        client, mock_calendar = _make_client_with_event(cal_obj)

        from caldav import error as caldav_error
        mock_calendar.object_by_uid.side_effect = caldav_error.NotFoundError("not found")

        with pytest.raises(ValueError, match="not found"):
            client.update_event(event_uid="nonexistent-uid", title="x")
