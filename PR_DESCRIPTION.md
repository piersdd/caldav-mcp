# feat: add `caldav_update_event` tool + Fastmail/iCloud E2E tests

## Summary

Two independent improvements bundled here (happy to split into separate PRs if preferred):

1. **`caldav_update_event` MCP tool** — partial update of existing events
2. **Provider E2E tests** — integration test suite for Fastmail and Apple iCloud

---

## 1. `caldav_update_event`

### Motivation

The current tool surface covers create, read, search, and delete — but has no way to mutate an existing event. This is a hard gap for real scheduling workflows (reschedule, rename, add location, etc.).

### Design

All fields are optional keyword arguments. Only fields that are explicitly provided are changed; the rest of the VEVENT is left untouched. Passing an empty string for `description` or `location` clears that field.

```python
caldav_update_event(
    event_uid="abc-123@example.com",
    title="Weekly Standup (reschedule)",
    start="2025-07-14T10:00:00Z",
    end="2025-07-14T10:30:00Z",
    location="Zoom",
)
```

### RFC 5545 compliance

The implementation correctly:
- **Increments `SEQUENCE`** on every mutating call (§3.8.7.4) so CalDAV servers and connected clients (Apple Calendar, Fastmail, Thunderbird) detect the change and re-sync
- **Updates `LAST-MODIFIED` and `DTSTAMP`** to the current UTC time on each update
- Uses `edit_icalendar_instance()` context manager (python-caldav ≥3.0 pattern) to avoid stale-reference side effects

### Files changed

| File | Change |
|---|---|
| `src/mcp_caldav/client.py` | `update_event()` method on `CalDAVClient` |
| `src/mcp_caldav/server.py` | `caldav_update_event` MCP tool registered via `@mcp.tool()` |
| `tests/test_update_event.py` | 14 unit tests covering all mutable fields, no-op path, sequence increment, DTSTAMP refresh, not-found error |
| `tests/test_server_update_event.py` | 8 unit tests verifying MCP tool correctly proxies all args to client |

---

## 2. Provider E2E tests — Fastmail + iCloud

### Motivation

The existing E2E suite runs only against Yandex Calendar. Both Fastmail and iCloud are common providers with non-trivial quirks that can only be caught against live servers.

### Structure

`tests/e2e/test_providers_e2e.py` uses a shared mixin class `CalDAVProviderTests` that is parameterised over providers. Each provider gets its own subclass:

```
CalDAVProviderTests          ← shared protocol tests
├── TestFastmailProvider     ← runs all shared tests against Fastmail
└── TestICloudProvider       ← runs all shared tests against iCloud
```

Plus provider-specific subclasses for quirks that only apply to one provider.

### Shared test coverage (both providers)

- `test_list_calendars_returns_at_least_one`
- `test_create_and_get_event` (round-trip via UID + date-range query)
- `test_update_event_title` ← new, exercises the new tool
- `test_update_event_description_and_location`
- `test_update_event_clears_description`
- `test_update_event_sequence_increments`
- `test_update_event_datetime_shift`
- `test_delete_event`
- `test_search_events_by_title`

### iCloud-specific tests

- `test_icloud_discovery_resolves_to_cluster_host` — verifies that starting from `https://caldav.icloud.com/` the library correctly follows `.well-known/caldav` to the per-account `pXX-caldav.icloud.com` host
- `test_icloud_no_vtodo_support` — living canary documenting that VTODO is not supported (will alert us if Apple ever adds it)
- `test_icloud_update_with_well_known_entry_point` — full create/update/delete cycle to confirm the update implementation survives the `.well-known` redirect

### Known iCloud quirks documented in tests

- URL must be `https://caldav.icloud.com/` (not the cluster URL); python-caldav resolves the rest
- Requires an app-specific password (not Apple ID password)
- No VTODO or VJOURNAL support
- Calendar creation via CalDAV is unreliable — tests use the first pre-existing calendar
- Deleted-then-recreated calendars with the same name may briefly show stale events — tests use unique UIDs to avoid this

### Running

Tests skip automatically if credentials are not set, so CI stays green without secrets:

```bash
# Copy and fill in credentials
cp tests/e2e/.env.e2e.providers.example tests/e2e/.env.e2e.providers

# Run (dotenv-cli or equivalent)
dotenv -f tests/e2e/.env.e2e.providers run -- make test-e2e-providers
# or manually:
export CALDAV_FASTMAIL_URL=...
export CALDAV_FASTMAIL_USERNAME=...
export CALDAV_FASTMAIL_PASSWORD=...
pytest tests/e2e/test_providers_e2e.py -v
```

### Files changed

| File | Change |
|---|---|
| `tests/e2e/test_providers_e2e.py` | Full provider E2E suite |
| `tests/e2e/.env.e2e.providers.example` | Credential template for Fastmail + iCloud |

---

## Testing

```
# Unit tests (no credentials needed)
make test

# Full E2E with Yandex (existing)
make test-e2e

# New: Fastmail + iCloud E2E
pytest tests/e2e/test_providers_e2e.py -v
```

## Checklist

- [x] `mypy` passes with no new errors
- [x] `ruff` passes
- [x] Unit tests added for all new code paths
- [x] E2E tests skip gracefully when credentials are absent
- [x] RFC 5545 §3.8.7.4 SEQUENCE increment implemented
- [x] `PROVIDER_NOTES.md` should be updated with Fastmail/iCloud notes (follow-up or included here if desired)
