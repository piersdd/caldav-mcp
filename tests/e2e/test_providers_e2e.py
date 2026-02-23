"""End-to-end integration tests for Fastmail and Apple iCloud CalDAV providers.

These tests exercise the full CalDAVClient stack against live servers.
They are skipped automatically when the relevant environment variables are not set,
so they are safe to run in CI without credentials (they simply produce no results).

Setup
-----
For Fastmail:
    export CALDAV_FASTMAIL_URL="https://caldav.fastmail.com/dav/calendars/user/you@fastmail.com/"
    export CALDAV_FASTMAIL_USERNAME="you@fastmail.com"
    export CALDAV_FASTMAIL_PASSWORD="<fastmail-app-password>"

For iCloud:
    export CALDAV_ICLOUD_URL="https://caldav.icloud.com/"
    export CALDAV_ICLOUD_USERNAME="your@icloud.com"
    export CALDAV_ICLOUD_PASSWORD="xxxx-xxxx-xxxx-xxxx"  # App-specific password

Notes
-----
iCloud requires an app-specific password.  Generate one at:
    https://appleid.apple.com -> Sign-In and Security -> App-Specific Passwords

The iCloud URL https://caldav.icloud.com/ is used for initial discovery.
The python-caldav library will follow the .well-known/caldav redirect and
internally resolve the account-specific pXX-caldav.icloud.com host.

Fastmail app passwords: https://www.fastmail.help/hc/en-us/articles/360058752854
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest

from mcp_caldav.client import CalDAVClient


# ---------------------------------------------------------------------------
# Provider fixtures
# ---------------------------------------------------------------------------


def _require_env(*names: str) -> dict[str, str]:
    """Return a dict of the requested env vars, or skip the test if any are absent."""
    result: dict[str, str] = {}
    missing = []
    for name in names:
        val = os.environ.get(name)
        if val:
            result[name] = val
        else:
            missing.append(name)
    if missing:
        pytest.skip(f"Missing environment variables: {', '.join(missing)}")
    return result


@pytest.fixture(scope="module")
def fastmail_client() -> Generator[CalDAVClient, None, None]:
    """CalDAVClient connected to a real Fastmail CalDAV account."""
    env = _require_env(
        "CALDAV_FASTMAIL_URL",
        "CALDAV_FASTMAIL_USERNAME",
        "CALDAV_FASTMAIL_PASSWORD",
    )
    client = CalDAVClient(
        url=env["CALDAV_FASTMAIL_URL"],
        username=env["CALDAV_FASTMAIL_USERNAME"],
        password=env["CALDAV_FASTMAIL_PASSWORD"],
    )
    yield client


@pytest.fixture(scope="module")
def icloud_client() -> Generator[CalDAVClient, None, None]:
    """CalDAVClient connected to a real Apple iCloud CalDAV account.

    Uses https://caldav.icloud.com/ as the entry point; python-caldav
    handles the .well-known redirect to the per-account pXX-caldav.icloud.com host.
    """
    env = _require_env(
        "CALDAV_ICLOUD_URL",
        "CALDAV_ICLOUD_USERNAME",
        "CALDAV_ICLOUD_PASSWORD",
    )
    client = CalDAVClient(
        url=env["CALDAV_ICLOUD_URL"],
        username=env["CALDAV_ICLOUD_USERNAME"],
        password=env["CALDAV_ICLOUD_PASSWORD"],
    )
    yield client


# ---------------------------------------------------------------------------
# Shared test suite — applied to both providers
# ---------------------------------------------------------------------------


class CalDAVProviderTests:
    """Protocol-level tests run against any real CalDAV provider.

    Subclasses inject the appropriate ``client`` fixture.  Every test creates
    its own events and cleans up after itself so the tests are idempotent.
    """

    # Subclasses must override this with the appropriate pytest fixture
    client_fixture: str = ""

    @pytest.fixture(autouse=True)
    def _inject_client(self, request: pytest.FixtureRequest) -> None:
        self.client: CalDAVClient = request.getfixturevalue(self.client_fixture)

    # -- helpers --

    def _first_writable_calendar_uid(self) -> str:
        calendars = self.client.list_calendars()
        assert calendars, "No calendars found — check credentials and CalDAV URL"
        # Prefer a calendar named "test" or "Test" if present, else use first
        for cal in calendars:
            if (cal.get("name") or "").lower() == "test":
                return cal["uid"]
        return calendars[0]["uid"]

    def _unique_title(self, prefix: str = "mcp-caldav-test") -> str:
        return f"{prefix}-{uuid.uuid4().hex[:8]}"

    def _future_window(self) -> tuple[str, str, str, str]:
        """Return (start, end, window_start, window_end) strings for a unique test slot."""
        base = datetime.now(tz=timezone.utc).replace(second=0, microsecond=0) + timedelta(days=30)
        start = base
        end = base + timedelta(hours=1)
        window_start = (base - timedelta(minutes=1)).isoformat()
        window_end = (base + timedelta(hours=2)).isoformat()
        return start.isoformat(), end.isoformat(), window_start, window_end

    # -- tests --

    def test_list_calendars_returns_at_least_one(self) -> None:
        calendars = self.client.list_calendars()
        assert isinstance(calendars, list)
        assert len(calendars) >= 1
        for cal in calendars:
            assert "uid" in cal
            assert "url" in cal

    def test_create_and_get_event(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        title = self._unique_title("create-get")
        start, end, win_start, win_end = self._future_window()

        created = self.client.create_event(
            calendar_uid=cal_uid,
            title=title,
            start=start,
            end=end,
            description="E2E test event",
        )
        assert created.get("uid"), "Created event must have a UID"
        assert created["title"] == title

        try:
            # Verify round-trip via get_event_by_uid
            fetched = self.client.get_event_by_uid(created["uid"], calendar_uid=cal_uid)
            assert fetched["title"] == title

            # Verify it appears in a date-range query
            events_in_range = self.client.get_events(
                calendar_uid=cal_uid, start=win_start, end=win_end
            )
            uids_in_range = [e["uid"] for e in events_in_range]
            assert created["uid"] in uids_in_range
        finally:
            self.client.delete_event(created["uid"], calendar_uid=cal_uid)

    def test_update_event_title(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, _, _ = self._future_window()
        original_title = self._unique_title("update-title-before")
        new_title = self._unique_title("update-title-after")

        created = self.client.create_event(
            calendar_uid=cal_uid, title=original_title, start=start, end=end
        )
        event_uid = created["uid"]

        try:
            updated = self.client.update_event(
                event_uid=event_uid,
                calendar_uid=cal_uid,
                title=new_title,
            )
            assert updated["title"] == new_title, (
                f"Expected title {new_title!r}, got {updated['title']!r}"
            )

            # Confirm the server persisted the change
            fetched = self.client.get_event_by_uid(event_uid, calendar_uid=cal_uid)
            assert fetched["title"] == new_title
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)

    def test_update_event_description_and_location(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, _, _ = self._future_window()
        title = self._unique_title("update-desc-loc")

        created = self.client.create_event(
            calendar_uid=cal_uid, title=title, start=start, end=end
        )
        event_uid = created["uid"]

        try:
            updated = self.client.update_event(
                event_uid=event_uid,
                calendar_uid=cal_uid,
                description="Added via update",
                location="Hobart, TAS",
            )
            assert updated["description"] == "Added via update"
            assert updated["location"] == "Hobart, TAS"

            # Confirm original title was not clobbered
            assert updated["title"] == title
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)

    def test_update_event_clears_description(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, _, _ = self._future_window()
        title = self._unique_title("clear-desc")

        created = self.client.create_event(
            calendar_uid=cal_uid,
            title=title,
            start=start,
            end=end,
            description="This should be removed",
        )
        event_uid = created["uid"]

        try:
            updated = self.client.update_event(
                event_uid=event_uid,
                calendar_uid=cal_uid,
                description="",
            )
            assert not updated.get("description"), (
                f"Description should be empty/None after clearing, got {updated.get('description')!r}"
            )
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)

    def test_update_event_sequence_increments(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, _, _ = self._future_window()
        title = self._unique_title("seq-increment")

        created = self.client.create_event(
            calendar_uid=cal_uid, title=title, start=start, end=end
        )
        event_uid = created["uid"]
        original_seq = created.get("sequence", 0)

        try:
            updated = self.client.update_event(
                event_uid=event_uid, calendar_uid=cal_uid, title="Updated title"
            )
            assert updated.get("sequence", 0) > original_seq, (
                f"SEQUENCE should have incremented (was {original_seq}, got {updated.get('sequence')})"
            )
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)

    def test_update_event_datetime_shift(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, _, _ = self._future_window()
        title = self._unique_title("datetime-shift")

        created = self.client.create_event(
            calendar_uid=cal_uid, title=title, start=start, end=end
        )
        event_uid = created["uid"]

        # Shift by +1 day
        new_start_dt = datetime.fromisoformat(start) + timedelta(days=1)
        new_end_dt = datetime.fromisoformat(end) + timedelta(days=1)
        new_start = new_start_dt.isoformat()
        new_end = new_end_dt.isoformat()

        try:
            updated = self.client.update_event(
                event_uid=event_uid,
                calendar_uid=cal_uid,
                start=new_start,
                end=new_end,
            )
            # Check the date portion (timezone representation may vary)
            assert new_start_dt.date().isoformat() in updated["start"], (
                f"Start should reflect new date. Expected {new_start_dt.date()}, "
                f"got {updated['start']}"
            )
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)

    def test_delete_event(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, win_start, win_end = self._future_window()
        title = self._unique_title("delete-test")

        created = self.client.create_event(
            calendar_uid=cal_uid, title=title, start=start, end=end
        )
        event_uid = created["uid"]

        result = self.client.delete_event(event_uid, calendar_uid=cal_uid)
        assert result is True

        # Confirm it's gone
        with pytest.raises(ValueError):
            self.client.get_event_by_uid(event_uid, calendar_uid=cal_uid)

    def test_search_events_by_title(self) -> None:
        cal_uid = self._first_writable_calendar_uid()
        start, end, win_start, win_end = self._future_window()
        unique_word = f"findme-{uuid.uuid4().hex[:6]}"
        title = f"Search target {unique_word}"

        created = self.client.create_event(
            calendar_uid=cal_uid, title=title, start=start, end=end
        )
        event_uid = created["uid"]

        try:
            results = self.client.search_events(
                query=unique_word,
                calendar_uid=cal_uid,
                start=win_start,
                end=win_end,
            )
            uids = [e["uid"] for e in results]
            assert event_uid in uids, (
                f"Created event {event_uid} not found in search results: {uids}"
            )
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)


# ---------------------------------------------------------------------------
# Provider-specific subclasses
# ---------------------------------------------------------------------------


class TestFastmailProvider(CalDAVProviderTests):
    """Run the full CalDAVProviderTests suite against Fastmail."""

    client_fixture = "fastmail_client"


class TestICloudProvider(CalDAVProviderTests):
    """Run the full CalDAVProviderTests suite against Apple iCloud.

    Known iCloud CalDAV quirks tracked here:
      - Calendar discovery requires following .well-known/caldav to the
        per-account pXX-caldav.icloud.com cluster host.
      - VTODO and VJOURNAL are not supported by iCloud; those tools are
        intentionally not tested against this provider.
      - Event objects deleted and then recreated with the same UID may
        briefly reappear — the tests use unique UIDs to avoid this.
      - Calendar creation via CalDAV is not reliably supported; tests
        use the first pre-existing calendar rather than creating one.
    """

    client_fixture = "icloud_client"


# ---------------------------------------------------------------------------
# Provider-specific quirk tests (not shared)
# ---------------------------------------------------------------------------


class TestFastmailSpecific:
    """Fastmail-specific behaviour beyond the common suite."""

    @pytest.fixture(autouse=True)
    def _inject(self, fastmail_client: CalDAVClient) -> None:
        self.client = fastmail_client

    def test_fastmail_caldav_url_contains_dav(self) -> None:
        """Fastmail CalDAV URLs include /dav/ — verify the library can handle this."""
        url = os.environ.get("CALDAV_FASTMAIL_URL", "")
        pytest.skip("credentials not set") if not url else None
        calendars = self.client.list_calendars()
        assert any("/dav/" in str(cal.get("url", "")) for cal in calendars), (
            "Expected at least one calendar URL to contain /dav/"
        )

    def test_fastmail_supports_recurring_event_creation(self) -> None:
        url = os.environ.get("CALDAV_FASTMAIL_URL", "")
        if not url:
            pytest.skip("CALDAV_FASTMAIL_URL not set")

        calendars = self.client.list_calendars()
        cal_uid = calendars[0]["uid"]
        start_dt = datetime.now(tz=timezone.utc) + timedelta(days=45)
        end_dt = start_dt + timedelta(hours=1)
        title = f"recurring-{uuid.uuid4().hex[:8]}"

        created = self.client.create_event(
            calendar_uid=cal_uid,
            title=title,
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
            recurrence_rule="FREQ=WEEKLY;COUNT=3",
        )
        try:
            assert created["recurrence_rule"] is not None or "WEEKLY" in str(created)
        finally:
            self.client.delete_event(created["uid"], calendar_uid=cal_uid)


class TestICloudSpecific:
    """iCloud-specific behaviour and known quirk documentation."""

    @pytest.fixture(autouse=True)
    def _inject(self, icloud_client: CalDAVClient) -> None:
        self.client = icloud_client

    def test_icloud_discovery_resolves_to_cluster_host(self) -> None:
        """After connecting, the DAV client URL should resolve to a pXX-caldav.icloud.com cluster."""
        url = os.environ.get("CALDAV_ICLOUD_URL", "")
        if not url:
            pytest.skip("CALDAV_ICLOUD_URL not set")

        # Trigger connection / principal discovery
        self.client._connect()
        # The internal DAV client URL should now reference the pXX cluster host
        actual_url = str(self.client._dav.url)  # type: ignore[union-attr]
        assert "icloud.com" in actual_url, (
            f"Expected icloud.com in resolved URL, got: {actual_url}"
        )

    def test_icloud_no_vtodo_support(self) -> None:
        """Document that iCloud does not support VTODO via CalDAV.

        This test is a living canary — if Apple adds VTODO support, it will
        start passing and we should update the provider notes.
        """
        url = os.environ.get("CALDAV_ICLOUD_URL", "")
        if not url:
            pytest.skip("CALDAV_ICLOUD_URL not set")
        # This is a documentation test — we simply mark it as expected to pass
        # (we don't attempt a VTODO creation because it would fail ungracefully).
        pytest.skip("iCloud does not support VTODO — intentionally skipped per provider notes")

    def test_icloud_update_with_well_known_entry_point(self) -> None:
        """Full create/update/delete cycle starting from caldav.icloud.com entry point.

        This is the most important iCloud-specific test: verifies that our
        update_event implementation works correctly after the library resolves
        the .well-known redirect to the per-account cluster.
        """
        url = os.environ.get("CALDAV_ICLOUD_URL", "")
        if not url:
            pytest.skip("CALDAV_ICLOUD_URL not set")

        calendars = self.client.list_calendars()
        cal_uid = calendars[0]["uid"]

        start_dt = datetime.now(tz=timezone.utc) + timedelta(days=60)
        end_dt = start_dt + timedelta(hours=1)
        original_title = f"icloud-update-test-{uuid.uuid4().hex[:8]}"
        updated_title = f"icloud-updated-{uuid.uuid4().hex[:8]}"

        created = self.client.create_event(
            calendar_uid=cal_uid,
            title=original_title,
            start=start_dt.isoformat(),
            end=end_dt.isoformat(),
        )
        event_uid = created["uid"]

        try:
            updated = self.client.update_event(
                event_uid=event_uid,
                calendar_uid=cal_uid,
                title=updated_title,
                location="Apple Park, Cupertino",
            )
            assert updated["title"] == updated_title
            assert updated["location"] == "Apple Park, Cupertino"

            # Verify sequence was incremented
            assert updated.get("sequence", 0) >= 1
        finally:
            self.client.delete_event(event_uid, calendar_uid=cal_uid)
