# CalDAV MCP Server — Development Guide

## Project overview

MCP server that provides CalDAV calendar operations as tools. Works with any
CalDAV-compatible server (Google Calendar, iCloud, Nextcloud, Yandex, etc.).

## Project structure

```
src/mcp_caldav/
├── __init__.py   — CLI entry point (Click), env var handling, transport selection
├── server.py     — MCP Server: tool definitions, tool dispatch, datetime parsing
└── client.py     — CalDAV client: iCalendar building/parsing, all calendar operations
```

- `server.py` defines the 8 MCP tools and routes `call_tool()` to `client.py` methods
- `client.py` does the actual CalDAV protocol work via the `caldav` library
- iCalendar text is built manually (string formatting), not via a library

## Key commands

```bash
make install-dev   # Install with dev dependencies
make test          # Run unit tests (mocked, no server needed)
make test-e2e      # Run E2E tests (requires .env.e2e with real credentials)
make check         # Run all quality checks (lint + format + type-check)
make lint          # Ruff linting
make format        # Ruff formatting
make type-check    # mypy strict mode
make coverage-html # HTML coverage report
```

## Testing

- **Unit tests** (`tests/test_client.py`, `tests/test_server.py`): Use mocks
  for the `caldav` library. No external dependencies. Run with `make test`.
- **E2E tests** (`tests/e2e/`): Require a real CalDAV server. Copy
  `.env.e2e.example` to `.env.e2e` and fill in credentials. Run with `make test-e2e`.
- Coverage target: 84% (up from 31% baseline).

## Code conventions

- **Type hints everywhere** — mypy strict mode is enforced
- **Ruff** for linting and formatting (line length 88)
- **Pre-commit hooks** are configured — run `make pre-commit-install` to set up
- Response types use `TypedDict` (in `client.py`): `CalendarInfo`, `EventRecord`,
  `EventCreationResult`, `EventDeletionResult`
- iCalendar text values must go through `_escape_ical_text()` to prevent injection
- Environment variables: `CALDAV_URL`, `CALDAV_USERNAME`, `CALDAV_PASSWORD`
  (legacy `YANDEX_*` vars still supported for backward compatibility)

## Architecture notes

- The MCP server uses `server_lifespan` to create and hold a single `CalDAVClient`
  instance for the session lifetime
- Tool names are prefixed with `caldav_` to namespace within MCP
- `get_event_by_uid` and `delete_event` search ±1 year from now (no native
  UID lookup in the CalDAV library)
- Yandex Calendar is auto-detected via URL for provider-specific behaviour
- No update/patch tool exists — modification is delete + recreate
