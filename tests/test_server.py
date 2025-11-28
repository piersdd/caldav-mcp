"""Unit tests for MCP CalDAV server."""

import json
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import Tool

from mcp_caldav.server import (
    AppContext,
    call_tool,
    get_caldav_config,
    list_tools,
    server_lifespan,
)


@pytest.mark.anyio
async def test_server_lifespan():
    """Test the server_lifespan context manager."""
    with (
        patch("mcp_caldav.server.get_caldav_config") as mock_config,
        patch("mcp_caldav.server.CalDAVClient") as mock_client_cls,
        patch("mcp_caldav.server.logger") as mock_logger,
    ):
        mock_config.return_value = {
            "url": "https://caldav.yandex.ru/",
            "username": "test@example.com",
            "password": "test-password",
        }
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_server = MagicMock()

        async with server_lifespan(mock_server) as ctx:
            assert isinstance(ctx, AppContext)
            assert ctx.client is not None
            mock_client.connect.assert_called_once()


@pytest.mark.anyio
async def test_server_lifespan_no_credentials():
    """Test the server_lifespan when credentials are not provided."""
    with (
        patch("mcp_caldav.server.get_caldav_config") as mock_config,
        patch("mcp_caldav.server.logger") as mock_logger,
    ):
        mock_config.return_value = {
            "url": "https://caldav.yandex.ru/",
            "username": None,
            "password": None,
        }

        mock_server = MagicMock()

        async with server_lifespan(mock_server) as ctx:
            assert isinstance(ctx, AppContext)
            assert ctx.client is None
            mock_logger.warning.assert_called()


def test_get_caldav_config():
    """Test getting CalDAV configuration from environment."""
    with patch.dict(
        "os.environ",
        {
            "CALDAV_URL": "https://test.example.com/",
            "CALDAV_USERNAME": "test@example.com",
            "CALDAV_PASSWORD": "test-password",
        },
    ):
        config = get_caldav_config()
        assert config["url"] == "https://test.example.com/"
        assert config["username"] == "test@example.com"
        assert config["password"] == "test-password"


def test_get_caldav_config_yandex_env():
    """Test getting CalDAV configuration using YANDEX_* environment variables."""
    with patch.dict(
        "os.environ",
        {
            "YANDEX_USERNAME": "test@yandex.ru",
            "YANDEX_PASSWORD": "test-password",
        },
        clear=False,
    ):
        config = get_caldav_config()
        assert config["username"] == "test@yandex.ru"
        assert config["password"] == "test-password"


@pytest.mark.anyio
async def test_list_tools_with_client(app_context):
    """Test listing tools when client is available."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        tools = await list_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

        for tool in tools:
            assert isinstance(tool, Tool)
            assert tool.name.startswith("caldav_")
            assert hasattr(tool, "description")
            assert hasattr(tool, "inputSchema")

        # Check that we have expected tools
        tool_names = [tool.name for tool in tools]
        assert "caldav_list_calendars" in tool_names
        assert "caldav_create_event" in tool_names
        assert "caldav_get_events" in tool_names
        assert "caldav_get_today_events" in tool_names
        assert "caldav_get_week_events" in tool_names


@pytest.mark.anyio
async def test_list_tools_no_client():
    """Test listing tools when client is not available."""
    from .conftest import mock_request_context

    app_context = AppContext(client=None)
    with mock_request_context(app_context):
        tools = await list_tools()
        assert isinstance(tools, list)
        assert len(tools) == 0


@pytest.mark.anyio
async def test_call_tool_list_calendars(app_context):
    """Test calling caldav_list_calendars tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.list_calendars.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_create_event(app_context):
    """Test calling caldav_create_event tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "description": "Test description",
                "location": "Test location",
            },
        )

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert data["success"] is True
        assert data["title"] == "Test Event"
        app_context.client.create_event.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_create_event_with_datetime(app_context):
    """Test calling caldav_create_event tool with datetime strings."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_create_event",
            {
                "title": "Test Event",
                "start_time": "2025-01-20T14:00:00",
                "end_time": "2025-01-20T15:00:00",
            },
        )

        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True

        # Check that create_event was called with datetime objects
        call_kwargs = app_context.client.create_event.call_args[1]
        assert call_kwargs["title"] == "Test Event"
        assert call_kwargs["start_time"] is not None
        assert call_kwargs["end_time"] is not None


@pytest.mark.anyio
async def test_call_tool_get_events(app_context):
    """Test calling caldav_get_events tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("caldav_get_events", {"calendar_index": 0})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.get_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_get_today_events(app_context):
    """Test calling caldav_get_today_events tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("caldav_get_today_events", {"calendar_index": 0})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.get_today_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_get_week_events(app_context):
    """Test calling caldav_get_week_events tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool(
            "caldav_get_week_events",
            {"calendar_index": 0, "start_from_today": True},
        )

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert isinstance(data, list)
        app_context.client.get_week_events.assert_called_once()


@pytest.mark.anyio
async def test_call_tool_no_client():
    """Test calling tool when client is not configured."""
    from .conftest import mock_request_context

    app_context = AppContext(client=None)
    with mock_request_context(app_context):
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "error" in data
        assert "not configured" in data["error"].lower()


@pytest.mark.anyio
async def test_call_tool_unknown_tool(app_context):
    """Test calling unknown tool."""
    from .conftest import mock_request_context

    with mock_request_context(app_context):
        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "error" in data
        assert "Unknown tool" in data["error"]


@pytest.mark.anyio
async def test_call_tool_error_handling(app_context):
    """Test error handling in tool calls."""
    from .conftest import mock_request_context

    app_context.client.list_calendars.side_effect = Exception("Test error")

    with mock_request_context(app_context):
        result = await call_tool("caldav_list_calendars", {})

        assert len(result) == 1
        assert result[0].type == "text"

        data = json.loads(result[0].text)
        assert "error" in data
        assert "Test error" in data["error"]
