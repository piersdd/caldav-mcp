"""MCP server for CalDAV calendar integration."""

import json
import logging
import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool

from .client import CalDAVClient

# Configure logging
logger = logging.getLogger("mcp-caldav")


@dataclass
class AppContext:
    """Application context for MCP CalDAV."""

    client: CalDAVClient | None = None


def get_caldav_config() -> dict[str, str | None]:
    """Get CalDAV configuration from environment variables."""
    return {
        "url": os.getenv("CALDAV_URL"),  # No default - must be configured
        "username": os.getenv("CALDAV_USERNAME") or os.getenv("YANDEX_USERNAME"),  # Backward compatibility
        "password": os.getenv("CALDAV_PASSWORD") or os.getenv("YANDEX_PASSWORD"),  # Backward compatibility
    }


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[AppContext]:
    """Initialize and clean up application resources."""
    config = get_caldav_config()

    try:
        client = None
        if config["url"] and config["username"] and config["password"]:
            client = CalDAVClient(
                url=config["url"],
                username=config["username"],
                password=config["password"],
            )
            client.connect()
            logger.info(
                f"Connected to CalDAV server: {config['url']} "
                f"for user: {config['username']}"
            )
        else:
            missing = []
            if not config["url"]:
                missing.append("CALDAV_URL")
            if not config["username"]:
                missing.append("CALDAV_USERNAME")
            if not config["password"]:
                missing.append("CALDAV_PASSWORD")
            logger.warning(
                f"CalDAV not configured. Missing: {', '.join(missing)}. "
                "Set these environment variables to enable calendar functionality."
            )

        yield AppContext(client=client)
    finally:
        # Cleanup if needed
        pass


# Create server instance
app = Server("mcp-caldav", lifespan=server_lifespan)


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available CalDAV tools."""
    ctx = app.request_context.lifespan_context

    if not ctx or not ctx.client:
        return []

    tools = [
        Tool(
            name="caldav_list_calendars",
            description="List all available calendars",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="caldav_create_event",
            description="Create a new event in the calendar",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_index": {
                        "type": "integer",
                        "description": "Index of the calendar (default: 0)",
                        "default": 0,
                    },
                    "title": {
                        "type": "string",
                        "description": "Event title",
                    },
                    "description": {
                        "type": "string",
                        "description": "Event description",
                        "default": "",
                    },
                    "location": {
                        "type": "string",
                        "description": "Event location",
                        "default": "",
                    },
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (e.g., '2025-01-20T14:00:00'). "
                        "If not provided, defaults to tomorrow at 14:00",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (e.g., '2025-01-20T15:00:00'). "
                        "If not provided, uses duration_hours from start_time",
                    },
                    "duration_hours": {
                        "type": "number",
                        "description": "Duration in hours (used if end_time not provided)",
                        "default": 1.0,
                    },
                    "reminders": {
                        "type": "array",
                        "description": "List of reminders. Each reminder is an object with: "
                        "minutes_before (integer), action ('DISPLAY', 'EMAIL', or 'AUDIO'), "
                        "and optional description (string)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "minutes_before": {"type": "integer"},
                                "action": {
                                    "type": "string",
                                    "enum": ["DISPLAY", "EMAIL", "AUDIO"],
                                },
                                "description": {"type": "string"},
                            },
                            "required": ["minutes_before", "action"],
                        },
                    },
                    "attendees": {
                        "type": "array",
                        "description": "List of attendee email addresses",
                        "items": {"type": "string"},
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="caldav_get_events",
            description="Get events from calendar for a specified period",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_index": {
                        "type": "integer",
                        "description": "Index of the calendar (default: 0)",
                        "default": 0,
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (e.g., '2025-01-20T00:00:00'). "
                        "Defaults to today 00:00",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (e.g., '2025-01-27T23:59:59'). "
                        "Defaults to 7 days from start_date",
                    },
                    "include_all_day": {
                        "type": "boolean",
                        "description": "Include all-day events",
                        "default": True,
                    },
                },
            },
        ),
        Tool(
            name="caldav_get_today_events",
            description="Get all events for today",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_index": {
                        "type": "integer",
                        "description": "Index of the calendar (default: 0)",
                        "default": 0,
                    },
                },
            },
        ),
        Tool(
            name="caldav_get_week_events",
            description="Get all events for the week",
            inputSchema={
                "type": "object",
                "properties": {
                    "calendar_index": {
                        "type": "integer",
                        "description": "Index of the calendar (default: 0)",
                        "default": 0,
                    },
                    "start_from_today": {
                        "type": "boolean",
                        "description": "Start from today (True) or from Monday (False)",
                        "default": True,
                    },
                },
            },
        ),
    ]

    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """Handle tool calls for CalDAV operations."""
    ctx = app.request_context.lifespan_context

    if not ctx or not ctx.client:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": "CalDAV client not configured. "
                        "Set CALDAV_USERNAME and CALDAV_PASSWORD environment variables."
                    },
                    indent=2,
                )
            )
        ]

    try:
        if name == "caldav_list_calendars":
            calendars = ctx.client.list_calendars()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(calendars, indent=2, ensure_ascii=False),
                )
            ]

        elif name == "caldav_create_event":
            calendar_index = arguments.get("calendar_index", 0)
            title = arguments.get("title")
            description = arguments.get("description", "")
            location = arguments.get("location", "")
            start_time_str = arguments.get("start_time")
            end_time_str = arguments.get("end_time")
            duration_hours = arguments.get("duration_hours", 1.0)
            reminders = arguments.get("reminders")
            attendees = arguments.get("attendees")

            start_time = None
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))

            end_time = None
            if end_time_str:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))

            result = ctx.client.create_event(
                calendar_index=calendar_index,
                title=title,
                description=description,
                location=location,
                start_time=start_time,
                end_time=end_time,
                duration_hours=duration_hours,
                reminders=reminders,
                attendees=attendees,
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(result, indent=2, ensure_ascii=False),
                )
            ]

        elif name == "caldav_get_events":
            calendar_index = arguments.get("calendar_index", 0)
            start_date_str = arguments.get("start_date")
            end_date_str = arguments.get("end_date")
            include_all_day = arguments.get("include_all_day", True)

            start_date = None
            if start_date_str:
                start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))

            end_date = None
            if end_date_str:
                end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))

            events = ctx.client.get_events(
                calendar_index=calendar_index,
                start_date=start_date,
                end_date=end_date,
                include_all_day=include_all_day,
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(events, indent=2, ensure_ascii=False),
                )
            ]

        elif name == "caldav_get_today_events":
            calendar_index = arguments.get("calendar_index", 0)
            events = ctx.client.get_today_events(calendar_index=calendar_index)

            return [
                TextContent(
                    type="text",
                    text=json.dumps(events, indent=2, ensure_ascii=False),
                )
            ]

        elif name == "caldav_get_week_events":
            calendar_index = arguments.get("calendar_index", 0)
            start_from_today = arguments.get("start_from_today", True)
            events = ctx.client.get_week_events(
                calendar_index=calendar_index, start_from_today=start_from_today
            )

            return [
                TextContent(
                    type="text",
                    text=json.dumps(events, indent=2, ensure_ascii=False),
                )
            ]

        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"error": f"Unknown tool: {name}"}, indent=2
                    ),
                )
            ]

    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}", exc_info=True)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, indent=2),
            )
        ]


async def run_server(transport: str = "stdio", port: int = 8000) -> None:
    """Run the MCP CalDAV server with the specified transport."""
    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request: Request) -> None:
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        import uvicorn

        config = uvicorn.Config(starlette_app, host="0.0.0.0", port=port)  # noqa: S104
        server = uvicorn.Server(config)
        await server.serve()
    else:
        from mcp.server.stdio import stdio_server

        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )

