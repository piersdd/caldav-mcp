"""CalDAV client for calendar operations."""

from datetime import datetime, timedelta, date
from typing import Optional, List, Dict

try:
    import caldav
except ImportError:
    raise ImportError(
        "caldav library is not installed. Install it with: pip install caldav"
    )


class CalDAVClient:
    """Client for working with CalDAV calendars."""

    def __init__(self, url: str, username: str, password: str):
        """
        Initialize CalDAV client.

        Args:
            url: CalDAV server URL (e.g., "https://caldav.example.com/")
            username: Username for authentication
            password: Password or app password for authentication
        """
        self.url = url
        self.username = username
        self.password = password
        self.client = None
        self.principal = None

    def connect(self) -> bool:
        """Connect to CalDAV server."""
        try:
            self.client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password,
            )
            self.principal = self.client.principal()
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to CalDAV server: {e}")

    def list_calendars(self) -> List[Dict[str, str]]:
        """Get list of available calendars."""
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            return [
                {
                    "index": i,
                    "name": cal.name,
                    "url": str(cal.url),
                }
                for i, cal in enumerate(calendars)
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to list calendars: {e}")

    def create_event(
        self,
        calendar_index: int = 0,
        title: str = "Event",
        description: str = "",
        location: str = "",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        duration_hours: float = 1.0,
        reminders: Optional[List[Dict]] = None,
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Create an event in the calendar.

        Args:
            calendar_index: Calendar index (default: 0)
            title: Event title
            description: Event description
            location: Event location
            start_time: Start time (default: tomorrow at 14:00)
            end_time: End time (optional, uses duration_hours if not provided)
            duration_hours: Duration in hours (used if end_time not provided)
            reminders: List of reminder dictionaries with keys:
                - minutes_before: minutes before event
                - action: 'DISPLAY', 'EMAIL', or 'AUDIO'
                - description: reminder text (optional)
            attendees: List of email addresses for attendees

        Returns:
            Dictionary with event creation result
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Set default times
            if start_time is None:
                start_time = datetime.now() + timedelta(days=1)
                start_time = start_time.replace(
                    hour=14, minute=0, second=0, microsecond=0
                )
            if end_time is None:
                end_time = start_time + timedelta(hours=duration_hours)

            # Generate unique UID
            uid = f"{int(datetime.now().timestamp())}@caldav-mcp"

            # Format alarm components for reminders
            alarm_components = ""
            if reminders:
                for reminder in reminders:
                    minutes_before = reminder.get("minutes_before", 15)
                    action = reminder.get("action", "DISPLAY").upper()
                    description_text = reminder.get("description", title)

                    if action == "DISPLAY":
                        alarm_components += f"""BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT{minutes_before}M
DESCRIPTION:{description_text}
END:VALARM
"""
                    elif action == "EMAIL":
                        email_to = reminder.get("email_to", "")
                        alarm_components += f"""BEGIN:VALARM
ACTION:EMAIL
TRIGGER:-PT{minutes_before}M
SUMMARY:{title}
DESCRIPTION:{description_text}
"""
                        if email_to:
                            alarm_components += f"ATTENDEE:mailto:{email_to}\n"
                        alarm_components += "END:VALARM\n"
                    elif action == "AUDIO":
                        alarm_components += f"""BEGIN:VALARM
ACTION:AUDIO
TRIGGER:-PT{minutes_before}M
DESCRIPTION:{description_text}
END:VALARM
"""

            # Format attendee components
            attendee_components = ""
            if attendees:
                for attendee_email in attendees:
                    attendee_email = attendee_email.strip()
                    if "@" in attendee_email:
                        attendee_components += f"ATTENDEE;RSVP=TRUE;CN={attendee_email}:mailto:{attendee_email}\n"

            # Format iCalendar data
            vcal_data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CalDAV MCP Server//Python//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start_time.strftime("%Y%m%dT%H%M%S")}
DTEND:{end_time.strftime("%Y%m%dT%H%M%S")}
SUMMARY:{title}
DESCRIPTION:{description}
LOCATION:{location}
STATUS:CONFIRMED
SEQUENCE:0
{attendee_components}{alarm_components}END:VEVENT
END:VCALENDAR"""

            # Save event
            calendar.save_event(vcal_data)

            return {
                "success": True,
                "uid": uid,
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "calendar": calendar.name,
            }

        except Exception as e:
            raise RuntimeError(f"Failed to create event: {e}")

    def get_events(
        self,
        calendar_index: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_all_day: bool = True,
    ) -> List[Dict]:
        """
        Get events from calendar for specified period.

        Args:
            calendar_index: Calendar index (default: 0)
            start_date: Start of period (default: today 00:00)
            end_date: End of period (default: 7 days from start_date)
            include_all_day: Include all-day events

        Returns:
            List of event dictionaries
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Set default dates
            if start_date is None:
                start_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            if end_date is None:
                end_date = start_date + timedelta(days=7)

            # Search for events
            events = calendar.date_search(start=start_date, end=end_date)

            result = []
            for event in events:
                try:
                    ical_component = event.icalendar_component

                    summary = ical_component.get("SUMMARY")
                    title = str(summary) if summary else ""

                    desc = ical_component.get("DESCRIPTION")
                    description = str(desc) if desc else ""

                    loc = ical_component.get("LOCATION")
                    location = str(loc) if loc else ""

                    dtstart = ical_component.get("DTSTART")
                    dtend = ical_component.get("DTEND")

                    if dtstart:
                        start_dt = dtstart.dt
                        if isinstance(start_dt, date) and not isinstance(
                            start_dt, datetime
                        ):
                            start_dt = datetime.combine(start_dt, datetime.min.time())
                            all_day = True
                        else:
                            all_day = False
                    else:
                        continue

                    if dtend:
                        end_dt = dtend.dt
                        if isinstance(end_dt, date) and not isinstance(
                            end_dt, datetime
                        ):
                            end_dt = datetime.combine(end_dt, datetime.max.time())
                    else:
                        end_dt = start_dt + timedelta(hours=1)

                    if not include_all_day and all_day:
                        continue

                    result.append(
                        {
                            "title": title,
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat(),
                            "description": description,
                            "location": location,
                            "all_day": all_day,
                        }
                    )

                except Exception:
                    # Skip events that can't be processed
                    continue

            # Sort by start time
            result.sort(key=lambda x: x["start"])

            return result

        except Exception as e:
            raise RuntimeError(f"Failed to get events: {e}")

    def get_today_events(self, calendar_index: int = 0) -> List[Dict]:
        """Get all events for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        return self.get_events(calendar_index, today_start, today_end)

    def get_week_events(
        self, calendar_index: int = 0, start_from_today: bool = True
    ) -> List[Dict]:
        """Get all events for the week."""
        if start_from_today:
            start_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            today = datetime.now()
            days_since_monday = today.weekday()
            start_date = (today - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        end_date = start_date + timedelta(days=7)
        return self.get_events(calendar_index, start_date, end_date)
