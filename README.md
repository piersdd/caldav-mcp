# MCP CalDAV Server

Universal MCP server for CalDAV protocol integration. Works with any CalDAV-compatible calendar server including Yandex Calendar, Google Calendar (via CalDAV), Nextcloud, ownCloud, Apple iCloud, and others.

> 📖 **Quick Start**: See [QUICKSTART.md](QUICKSTART.md) for a quick guide to get started with `uv`.  
> 🔧 **Cursor Setup**: See [CURSOR_SETUP.md](CURSOR_SETUP.md) for detailed Cursor IDE configuration instructions.

## Features

- List available calendars
- Create calendar events with reminders and attendees
- Get events for today, week, or custom date range
- Works with any CalDAV-compatible server (Yandex, Google, Nextcloud, ownCloud, iCloud, etc.)

## Installation

### Using uv (Recommended)

First, install uv if you haven't already:

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then install the project:

```bash
uv sync --dev
```

This will:

- Create a virtual environment (`.venv`)
- Install all dependencies including dev dependencies
- Generate a `uv.lock` file

### Using uvx (Run without installation)

You can also run the server directly without installing it:

```bash
uvx mcp-caldav
```

### Using pip

```bash
pip install -e .
```

## Configuration

Set the following environment variables:

```bash
export CALDAV_URL="https://caldav.example.com/"
export CALDAV_USERNAME="your-username"
export CALDAV_PASSWORD="your-password"
```

### CalDAV Server URLs

Common CalDAV server URLs:

- **Yandex Calendar**: `https://caldav.yandex.ru/`
- **Google Calendar**: `https://apidata.googleusercontent.com/caldav/v2/` (requires OAuth setup)
- **Nextcloud**: `https://your-domain.com/remote.php/dav/calendars/username/`
- **ownCloud**: `https://your-domain.com/remote.php/dav/calendars/username/`
- **Apple iCloud**: `https://caldav.icloud.com/` (requires app-specific password)
- **FastMail**: `https://caldav.fastmail.com/dav/calendars/user/`

**Note**: Some servers require app-specific passwords instead of regular passwords. Check your calendar provider's documentation for CalDAV setup instructions.

## Usage

### IDE Integration (Cursor)

To use this MCP server in Cursor:

1. Open Cursor Settings → Features → MCP Servers → + Add new global MCP server
2. Add the following configuration:

**Using uvx (Recommended - no installation needed):**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uvx",
      "args": ["mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Using local installation (after `uv sync` or `pip install`):**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "mcp-caldav",
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Using local development version:**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/caldav", "mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://caldav.example.com/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

**Example for Yandex Calendar:**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uvx",
      "args": ["mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://caldav.yandex.ru/",
        "CALDAV_USERNAME": "your-username@yandex.ru",
        "CALDAV_PASSWORD": "your-app-password"
      }
    }
  }
}
```

**Example for Nextcloud:**

```json
{
  "mcpServers": {
    "mcp-caldav": {
      "command": "uvx",
      "args": ["mcp-caldav"],
      "env": {
        "CALDAV_URL": "https://your-domain.com/remote.php/dav/calendars/username/",
        "CALDAV_USERNAME": "your-username",
        "CALDAV_PASSWORD": "your-password"
      }
    }
  }
}
```

### As MCP Server

The server can be used with MCP-compatible clients:

**Using uv (after `uv sync`):**

```bash
uv run mcp-caldav
```

**Note:** `uvx` works only with published packages from PyPI. For local development, use `uv run mcp-caldav` after `uv sync`.

**Using pip (after installation):**

```bash
mcp-caldav
```

Or with custom options:

```bash
uv run mcp-caldav --caldav-url "https://caldav.example.com/" \
                   --caldav-username "your-username" \
                   --caldav-password "your-password" \
                   --verbose
```

### Available Tools

- `caldav_list_calendars` - List all available calendars
- `caldav_create_event` - Create a new calendar event
- `caldav_get_events` - Get events for a date range
- `caldav_get_today_events` - Get events for today
- `caldav_get_week_events` - Get events for the week

## Development

### Running Tests

Using uv:

```bash
uv run pytest tests/
```

Or with coverage:

```bash
uv run pytest tests/ --cov=src/mcp_caldav --cov-report=html
```

Using pip:

```bash
pytest tests/
```

### Project Structure

```
caldav/
├── src/
│   └── mcp_caldav/
│       ├── __init__.py      # Main entry point
│       ├── server.py        # MCP server implementation
│       └── client.py         # CalDAV client wrapper
├── tests/
│   ├── test_server.py       # Server tests
│   └── test_client.py       # Client tests
├── pyproject.toml           # Project configuration
└── README.md                # This file
```

## License

See LICENSE file for details.
