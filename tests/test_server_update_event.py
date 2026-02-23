"""Unit tests for the caldav_update_event MCP tool.

These tests verify that server.py correctly proxies arguments to
CalDAVClient.update_event without needing a live server.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# The server module registers tools at import time, so we import it here.
import mcp_caldav.server as server_module


SAMPLE_RETURN = {
    "uid": "abc-123",
    "title": "Updated Event",
    "start": "2025-06-01T10:00:00+00:00",
    "end": "2025-06-01T11:00:00+00:00",
    "description": None,
    "location": None,
    "recurrence_rule": None,
    "categories": [],
    "priority": 0,
    "attendees": [],
    "alarms": [],
    "sequence": 1,
}


@pytest.fixture()
def mock_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace _get_client() with a mock CalDAVClient."""
    mock = MagicMock()
    mock.update_event.return_value = SAMPLE_RETURN
    monkeypatch.setattr(server_module, "_get_client", lambda: mock)
    return mock


class TestCaldavUpdateEventTool:
    def test_title_forwarded(self, mock_client: MagicMock) -> None:
        server_module.caldav_update_event(event_uid="abc-123", title="New Title")
        mock_client.update_event.assert_called_once_with(
            event_uid="abc-123",
            calendar_uid=None,
            title="New Title",
            start=None,
            end=None,
            description=None,
            location=None,
            recurrence_rule=None,
            categories=None,
            priority=None,
        )

    def test_partial_update_only_passes_given_fields(self, mock_client: MagicMock) -> None:
        server_module.caldav_update_event(
            event_uid="abc-123",
            description="New description",
            location="Meeting Room 1",
        )
        call_kwargs = mock_client.update_event.call_args.kwargs
        assert call_kwargs["description"] == "New description"
        assert call_kwargs["location"] == "Meeting Room 1"
        assert call_kwargs["title"] is None
        assert call_kwargs["start"] is None

    def test_returns_updated_event_dict(self, mock_client: MagicMock) -> None:
        result = server_module.caldav_update_event(event_uid="abc-123", title="x")
        assert result == SAMPLE_RETURN

    def test_calendar_uid_forwarded(self, mock_client: MagicMock) -> None:
        server_module.caldav_update_event(event_uid="abc-123", calendar_uid="work", title="x")
        call_kwargs = mock_client.update_event.call_args.kwargs
        assert call_kwargs["calendar_uid"] == "work"

    def test_empty_string_description_forwarded(self, mock_client: MagicMock) -> None:
        """Empty string should be forwarded so the client can clear the field."""
        server_module.caldav_update_event(event_uid="abc-123", description="")
        call_kwargs = mock_client.update_event.call_args.kwargs
        assert call_kwargs["description"] == ""

    def test_recurrence_rule_forwarded(self, mock_client: MagicMock) -> None:
        server_module.caldav_update_event(
            event_uid="abc-123", recurrence_rule="FREQ=WEEKLY;BYDAY=MO"
        )
        call_kwargs = mock_client.update_event.call_args.kwargs
        assert call_kwargs["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=MO"

    def test_categories_list_forwarded(self, mock_client: MagicMock) -> None:
        server_module.caldav_update_event(event_uid="abc-123", categories=["work", "urgent"])
        call_kwargs = mock_client.update_event.call_args.kwargs
        assert call_kwargs["categories"] == ["work", "urgent"]

    def test_priority_forwarded(self, mock_client: MagicMock) -> None:
        server_module.caldav_update_event(event_uid="abc-123", priority=2)
        call_kwargs = mock_client.update_event.call_args.kwargs
        assert call_kwargs["priority"] == 2
