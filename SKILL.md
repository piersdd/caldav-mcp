---
name: caldav-mcp
description: >
  Guide for using CalDAV MCP tools to manage calendar events — listing calendars,
  creating/searching/deleting events, checking schedules, and handling recurrence.
  Use this skill whenever the user mentions calendars, events, scheduling, meetings,
  appointments, availability, "what's on my calendar", "am I free", "book a meeting",
  "schedule something", daily/weekly agenda, or any task involving time-based planning
  that a calendar would help with. Also trigger when the user asks to create recurring
  events, check for conflicts, find a free slot, or manage attendees.
---

# CalDAV MCP — Calendar Operations Guide

This skill helps you work effectively with the CalDAV MCP tools. These tools connect
to any CalDAV-compatible calendar server (Google Calendar, iCloud, Nextcloud, Yandex,
FastMail, ownCloud, and others).

## Available tools

| Tool | Purpose |
|------|---------|
| `caldav_list_calendars` | List all calendars (returns index, name, URL) |
| `caldav_create_event` | Create an event with full iCalendar support |
| `caldav_get_events` | Query events in a date range |
| `caldav_get_today_events` | Shortcut for today's events |
| `caldav_get_week_events` | Shortcut for this week's events |
| `caldav_get_event_by_uid` | Fetch a specific event by its UID |
| `caldav_delete_event` | Delete an event by its UID |
| `caldav_search_events` | Search events by text, attendees, or location |

## Getting oriented

When a user first asks about their calendar, start by listing their calendars to
understand what's available and which `calendar_index` to use. Calendars are
zero-indexed — the first calendar is index 0.

```
caldav_list_calendars → [{"index": 0, "name": "Personal", ...}, {"index": 1, "name": "Work", ...}]
```

If the user has multiple calendars, ask which one they mean unless it's obvious
from context (e.g., "work meeting" → look for a calendar named "Work").

## Date and time formats

All date/time parameters use **ISO 8601 format**. Both `Z` suffix and `+00:00`
offset notation are accepted.

```
"2025-03-15T14:00:00"       ← local time (no timezone)
"2025-03-15T14:00:00Z"      ← UTC
"2025-03-15T14:00:00+02:00" ← explicit offset
"2025-03-15"                ← date only (for recurrence "until")
```

When creating events, always use explicit times rather than relying on defaults.
If the user says "tomorrow at 2pm", calculate the actual date and pass it as
`start_time`. The server defaults to "tomorrow at 14:00" if no start_time is
given, but being explicit avoids surprises.

### Common pitfall: end_date for queries

When querying events, `end_date` is **exclusive** — an event at exactly the end
boundary may not be returned. To get all events for a single day, use:

```
start_date: "2025-03-15T00:00:00"
end_date:   "2025-03-16T00:00:00"   ← next day, not 23:59:59
```

For `caldav_search_events`, both `start_date` and `end_date` are **required**.

## Creating events

### Basic event

Only `title` is required. Everything else has sensible defaults:

```json
{
  "title": "Team standup",
  "start_time": "2025-03-15T09:00:00",
  "end_time": "2025-03-15T09:30:00",
  "location": "Room 4B",
  "description": "Daily sync"
}
```

### Using duration instead of end time

If you have a duration but no explicit end time, use `duration_hours`:

```json
{
  "title": "Lunch with Alex",
  "start_time": "2025-03-15T12:00:00",
  "duration_hours": 1.5
}
```

### Recurring events

Use the `recurrence` object. The `frequency` field is required; everything else
is optional.

```json
{
  "title": "Weekly 1:1",
  "start_time": "2025-03-17T10:00:00",
  "duration_hours": 0.5,
  "recurrence": {
    "frequency": "WEEKLY",
    "byday": "MO",
    "count": 12
  }
}
```

**Frequency options:** `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`

**Useful combinations:**
- Every weekday: `{"frequency": "WEEKLY", "byday": "MO,TU,WE,TH,FR"}`
- First of each month: `{"frequency": "MONTHLY", "bymonthday": 1}`
- Every 2 weeks: `{"frequency": "WEEKLY", "interval": 2}`
- Until a date: `{"frequency": "DAILY", "until": "2025-06-30"}`

### Attendees

Pass as simple email strings or objects with status:

```json
{
  "attendees": [
    "alice@example.com",
    {"email": "bob@example.com", "status": "ACCEPTED"}
  ]
}
```

**Status values:** `ACCEPTED`, `DECLINED`, `TENTATIVE`, `NEEDS-ACTION`

### Reminders

```json
{
  "reminders": [
    {"minutes_before": 15, "action": "DISPLAY"},
    {"minutes_before": 60, "action": "EMAIL"}
  ]
}
```

**Action types:** `DISPLAY` (popup), `EMAIL`, `AUDIO`

### Categories and priority

```json
{
  "categories": ["work", "planning"],
  "priority": 1
}
```

Priority scale: 0 = undefined, 1 = highest, 9 = lowest.

## Workflow patterns

### Daily briefing

When a user asks "what's on today" or "what do I have today":

1. Call `caldav_get_today_events`
2. Present events chronologically
3. Highlight any overlaps or tight transitions
4. Note all-day events separately at the top

### Weekly overview

When a user asks about their week:

1. Call `caldav_get_week_events` (set `start_from_today: true` for remaining week,
   `false` for full Mon–Sun)
2. Group by day
3. Flag days with heavy scheduling vs free days

### Finding free time

The tools don't have a dedicated "free/busy" endpoint, so synthesize it:

1. Call `caldav_get_events` for the date range
2. Identify gaps between events
3. Present available slots to the user
4. Account for all-day events blocking the whole day

### Conflict detection

Before creating an event, check for overlaps:

1. Call `caldav_get_events` for the proposed time window
2. If any events overlap, tell the user and offer alternatives
3. Only create the event after the user confirms

### Bulk event creation

When creating multiple events (e.g., "set up meetings for the whole sprint"):

1. Gather all the event details first
2. Create events one at a time — there's no batch API
3. Report progress and UIDs as you go
4. If any creation fails, report the error and continue with the rest

### Modifying events

There's no update/edit tool. To modify an event:

1. Fetch it by UID with `caldav_get_event_by_uid`
2. Show the current details to the user
3. Delete the old event with `caldav_delete_event`
4. Create a new event with the updated details
5. Report the new UID

This is a destructive workflow — always confirm with the user before deleting.

## Provider-specific notes

### Yandex Calendar

Yandex has aggressive rate limiting (60 seconds per MB throttle since 2021).
Write operations frequently hit 504 timeouts. If you're working with a Yandex
calendar:

- Space out write operations (wait a few seconds between creates/deletes)
- Expect slower responses for write operations
- Reads are generally reliable

### Google Calendar

- Requires OAuth setup and app-specific passwords
- More reliable for write-heavy workloads
- Standard CalDAV support

### iCloud Calendar

- Requires app-specific password (not regular Apple ID password)
- Reliable for personal use
- Standard CalDAV support

### Nextcloud / ownCloud

- Self-hosted — no external rate limits
- Excellent CalDAV compliance
- URL format: `https://your-domain.com/remote.php/dav/calendars/username/`

## Error handling

Common errors and what they mean:

- **"CalDAV client not configured"** — missing `CALDAV_URL`, `CALDAV_USERNAME`,
  or `CALDAV_PASSWORD` environment variables
- **"Calendar index N not found"** — the index is out of range; list calendars first
- **"Event with UID ... not found"** — the UID doesn't exist or is outside the
  search window (±1 year from now)
- **504 timeout** — likely provider rate limiting (especially Yandex); wait and retry
