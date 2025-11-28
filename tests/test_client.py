"""Unit tests for CalDAV client."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mcp_caldav.client import CalDAVClient


def test_caldav_client_init():
    """Test CalDAV client initialization."""
    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )

    assert client.url == "https://caldav.yandex.ru/"
    assert client.username == "test@example.com"
    assert client.password == "test-password"
    assert client.client is None
    assert client.principal is None


@patch("mcp_caldav.client.caldav.DAVClient")
def test_caldav_client_connect(mock_dav_client):
    """Test CalDAV client connection."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )

    result = client.connect()

    assert result is True
    assert client.client == mock_client_instance
    assert client.principal == mock_principal
    mock_dav_client.assert_called_once_with(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )


@patch("mcp_caldav.client.caldav.DAVClient")
def test_caldav_client_connect_error(mock_dav_client):
    """Test CalDAV client connection error handling."""
    mock_dav_client.side_effect = Exception("Connection failed")

    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )

    with pytest.raises(ConnectionError) as exc_info:
        client.connect()

    assert "Connection failed" in str(exc_info.value)


@patch("mcp_caldav.client.caldav.DAVClient")
def test_caldav_client_list_calendars(mock_dav_client):
    """Test listing calendars."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar1 = MagicMock()
    mock_calendar1.name = "Calendar 1"
    mock_calendar1.url = "https://caldav.yandex.ru/calendars/1"
    mock_calendar2 = MagicMock()
    mock_calendar2.name = "Calendar 2"
    mock_calendar2.url = "https://caldav.yandex.ru/calendars/2"
    mock_principal.calendars.return_value = [mock_calendar1, mock_calendar2]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )
    client.connect()

    calendars = client.list_calendars()

    assert len(calendars) == 2
    assert calendars[0]["index"] == 0
    assert calendars[0]["name"] == "Calendar 1"
    assert calendars[1]["index"] == 1
    assert calendars[1]["name"] == "Calendar 2"


@patch("mcp_caldav.client.caldav.DAVClient")
def test_caldav_client_create_event(mock_dav_client):
    """Test creating an event."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.name = "Test Calendar"
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )
    client.connect()

    start_time = datetime(2025, 1, 20, 14, 0)
    end_time = datetime(2025, 1, 20, 15, 0)

    result = client.create_event(
        calendar_index=0,
        title="Test Event",
        description="Test description",
        location="Test location",
        start_time=start_time,
        end_time=end_time,
    )

    assert result["success"] is True
    assert result["title"] == "Test Event"
    assert "uid" in result
    assert result["calendar"] == "Test Calendar"
    mock_calendar.save_event.assert_called_once()


@patch("mcp_caldav.client.caldav.DAVClient")
def test_caldav_client_create_event_with_reminders(mock_dav_client):
    """Test creating an event with reminders."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.name = "Test Calendar"
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )
    client.connect()

    start_time = datetime(2025, 1, 20, 14, 0)

    result = client.create_event(
        calendar_index=0,
        title="Test Event",
        start_time=start_time,
        reminders=[
            {"minutes_before": 15, "action": "DISPLAY"},
            {"minutes_before": 60, "action": "EMAIL", "description": "Reminder"},
        ],
    )

    assert result["success"] is True
    mock_calendar.save_event.assert_called_once()

    # Check that VALARM is in the saved event
    saved_event = mock_calendar.save_event.call_args[0][0]
    assert "VALARM" in saved_event
    assert "TRIGGER:-PT15M" in saved_event
    assert "TRIGGER:-PT60M" in saved_event


@patch("mcp_caldav.client.caldav.DAVClient")
def test_caldav_client_create_event_with_attendees(mock_dav_client):
    """Test creating an event with attendees."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.name = "Test Calendar"
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(
        url="https://caldav.yandex.ru/",
        username="test@example.com",
        password="test-password",
    )
    client.connect()

    start_time = datetime(2025, 1, 20, 14, 0)

    result = client.create_event(
        calendar_index=0,
        title="Test Event",
        start_time=start_time,
        attendees=["attendee1@example.com", "attendee2@example.com"],
    )

    assert result["success"] is True
    mock_calendar.save_event.assert_called_once()

    # Check that ATTENDEE is in the saved event
    saved_event = mock_calendar.save_event.call_args[0][0]
    assert "ATTENDEE" in saved_event
    assert "attendee1@example.com" in saved_event
    assert "attendee2@example.com" in saved_event


