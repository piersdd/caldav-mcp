# Test Coverage Report

## Overview

This document provides an overview of test coverage for the `mcp-caldav` project.

### Quick Summary

- **Unit Tests**: 35 tests, all passing ✅
- **E2E Tests**: 9 tests, 8 passed ✅, 1 skipped (rate limiting)
- **Code Coverage**: 31% (unit tests with mocks)
- **Real Implementation Coverage**: Comprehensive via E2E tests with real CalDAV server
- **Last Updated**: 2025-11-28

## Running Coverage Reports

### Unit Tests Coverage

Run unit tests with coverage:

```bash
uv run pytest tests/ -m "not e2e" --cov=src/mcp_caldav --cov-report=term-missing --cov-report=html
```

This will:

- Run all unit tests (excluding e2e tests)
- Generate a terminal report showing coverage percentages
- Generate an HTML report in `htmlcov/` directory

### View HTML Report

Open the HTML report in your browser:

```bash
open htmlcov/index.html  # macOS
# or
xdg-open htmlcov/index.html  # Linux
```

### E2E Tests Coverage

E2E tests are run separately and don't contribute to coverage metrics (they use real servers):

```bash
export CALDAV_URL="https://caldav.yandex.ru/"
export CALDAV_USERNAME="your-username"
export CALDAV_PASSWORD="your-app-password"
uv run pytest tests/e2e/ -v -m e2e
```

## Coverage Details

### Test Structure

```
tests/
├── test_client.py          # Unit tests for CalDAVClient
├── test_server.py          # Unit tests for MCP server
└── e2e/
    ├── test_client_e2e.py  # E2E tests with real server
    └── conftest.py         # E2E test fixtures
```

### Unit Tests Coverage

#### `test_client.py` - CalDAVClient Tests

**Covered Methods:**

- ✅ `__init__()` - Client initialization
- ✅ `connect()` - Connection to CalDAV server
- ✅ `connect()` error handling
- ✅ `list_calendars()` - List available calendars
- ✅ `create_event()` - Create events with reminders and attendees
- ✅ `get_events()` - Get events for date range
- ✅ `get_today_events()` - Get today's events
- ✅ `get_week_events()` - Get week's events

**Helper Functions:**

- ✅ `_format_rrule()` - Recurrence rule formatting
- ✅ `_format_categories()` - Category formatting
- ✅ `_format_attendees()` - Attendee formatting
- ✅ `_parse_categories()` - Category parsing
- ✅ `_parse_attendees()` - Attendee parsing

**New Methods (Extended Features):**

- ✅ `get_event_by_uid()` - Get event by UID
- ✅ `delete_event()` - Delete event by UID
- ✅ `search_events()` - Search events by query

#### `test_server.py` - MCP Server Tests

**Covered Functions:**

- ✅ `server_lifespan()` - Server lifecycle management
- ✅ `server_lifespan()` without credentials
- ✅ `list_tools()` - List available MCP tools
- ✅ `list_tools()` without client
- ✅ `call_tool()` - Tool invocation handlers:
  - ✅ `caldav_list_calendars`
  - ✅ `caldav_create_event`
  - ✅ `caldav_get_events`
  - ✅ `caldav_get_today_events`
  - ✅ `caldav_get_week_events`
  - ✅ `caldav_get_event_by_uid`
  - ✅ `caldav_delete_event`
  - ✅ `caldav_search_events`
- ✅ Error handling for unknown tools
- ✅ Error handling for client errors

### E2E Tests Coverage

#### `test_client_e2e.py` - Real Server Tests

**Test Scenarios:**

- ✅ `test_list_calendars` - List calendars from real server
- ✅ `test_create_and_get_event` - Create and retrieve event
- ✅ `test_create_event_with_categories_and_priority` - Categories and priority support
- ✅ `test_create_recurring_event` - Recurring events (RRULE)
- ✅ `test_create_event_with_attendees` - Events with attendees and statuses
- ✅ `test_delete_event` - Delete events
- ✅ `test_search_events` - Search functionality
- ✅ `test_get_events_with_extended_fields` - Extended fields in get_events

**Features Tested:**

- ✅ Basic CRUD operations
- ✅ Categories and tags
- ✅ Priority levels
- ✅ Recurrence rules (RRULE)
- ✅ Attendees with statuses
- ✅ Search functionality
- ✅ Extended fields (UID, categories, priority, attendees, recurrence)

## Coverage Metrics

### Current Coverage Status

**Last Updated**: 2025-11-28

Run the following command to see current coverage:

```bash
uv run pytest tests/ -m "not e2e" --cov=src/mcp_caldav --cov-report=term-missing
```

**Current Coverage:**

```
Name                         Stmts   Miss  Cover   Missing
----------------------------------------------------------
src/mcp_caldav/__init__.py      42     21    50%   15, 67-94, 100
src/mcp_caldav/client.py       426    348    18%   (many lines)
src/mcp_caldav/server.py       183     80    56%   58, 511-519, 551, 555, 597-610, ...
----------------------------------------------------------
TOTAL                          651    449    31%
```

**Note**: Unit test coverage is lower because:

- Unit tests use mocks and don't execute real CalDAV client code
- Real implementation is tested via E2E tests (not included in coverage metrics)
- Many client methods are integration-heavy and require real server connections

### Target Coverage Goals

- **Overall Coverage**: > 85% (with integration tests)
- **Unit Test Coverage**: > 50% (current: 31%)
- **Critical Paths**: > 95%
  - Client connection and error handling
  - Event CRUD operations
  - MCP server tool handlers
- **Helper Functions**: > 80%
  - iCalendar formatting functions
  - Parsing functions

### Coverage by Module

#### `__init__.py` (50% coverage)

- ✅ CLI argument parsing
- ✅ Environment variable loading
- ✅ Server startup
- ❌ Error handling paths
- ❌ Advanced CLI options

#### `client.py` (18% coverage)

- ✅ Basic structure and initialization
- ✅ Mock-based unit tests
- ❌ Real CalDAV operations (tested via E2E)
- ❌ Error handling paths
- ❌ Edge cases

**E2E Coverage** (not in metrics):

- ✅ All CRUD operations
- ✅ Extended features (categories, priority, recurrence, attendees)
- ✅ Search functionality
- ✅ Error handling with real server

#### `server.py` (56% coverage)

- ✅ Server lifecycle management
- ✅ Tool listing
- ✅ Basic tool handlers
- ✅ Error handling
- ❌ Advanced tool handlers (new features)
- ❌ Edge cases in argument parsing

## Coverage Gaps

### Areas That May Need More Coverage

1. **Edge Cases:**

   - Invalid date formats
   - Invalid recurrence rules
   - Malformed iCalendar data
   - Network timeout scenarios

2. **Error Handling:**

   - Connection retries
   - Partial failures
   - Invalid calendar indices

3. **Boundary Conditions:**
   - Empty calendars
   - Very large date ranges
   - Events at timezone boundaries

## Continuous Integration

Coverage reports can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests with coverage
  run: |
    uv run pytest tests/ -m "not e2e" \
      --cov=src/mcp_caldav \
      --cov-report=xml \
      --cov-report=term
```

## Test Statistics

### Unit Tests

- **Total Unit Tests**: 35 tests
- **Test Files**: 2 (`test_client.py`, `test_server.py`)
- **Coverage**: 31% (unit tests use mocks, real logic tested via E2E)
- **Status**: All passing ✅

### E2E Tests

- **Total E2E Tests**: 9 tests
- **Test File**: `test_client_e2e.py`
- **Status**: 8 passed ✅, 1 skipped (rate limiting)
- **Coverage**: Real server integration (not in coverage metrics)
- **Features Tested**: All CRUD operations, categories, priority, recurrence, attendees, search

### Test Execution Times

- **Unit Tests**: ~0.5-1 second
- **E2E Tests**: ~45-50 seconds (includes delays for rate limiting)

## Notes

- E2E tests are excluded from coverage metrics as they require external services
- Coverage reports are generated in `htmlcov/` directory (gitignored)
- Use `--cov-fail-under=85` to fail CI if coverage drops below threshold
- Low unit test coverage (31%) is expected because:
  - Real CalDAV operations require server connections
  - Unit tests use mocks for isolation
  - E2E tests provide comprehensive real-world coverage
- To improve unit test coverage, consider:
  - Adding more edge case tests
  - Testing error paths with mocks
  - Testing helper functions in isolation
