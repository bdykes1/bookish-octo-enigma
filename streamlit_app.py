from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Replace with your actual calendar ID and credentials file
CALENDAR_ID = "your_calendar_id_here"
SERVICE_ACCOUNT_FILE = "credentials.json"

def get_calendar_service():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    service = build("calendar", "v3", credentials=credentials)
    return service

def upsert_calendar_event(username, lunch_text, date_str):
    service = get_calendar_service()

    # Parse date and set time window
    date = datetime.strptime(date_str, "%Y-%m-%d")
    start_time = datetime(date.year, date.month, date.day, 11, 0)
    end_time = datetime(date.year, date.month, date.day, 13, 0)

    # Search for existing lunch event with exact summary match
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat() + "Z",
        timeMax=end_time.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = [
        e for e in events_result.get("items", [])
        if e.get("summary", "").startswith(f"{username} – Lunch:")
    ]

    event_body = {
        "summary": f"{username} – Lunch: {lunch_text}",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Chicago"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Chicago"},
    }

    if events:
        # Update the first matching event
        event_id = events[0]["id"]
        service.events().update(
            calendarId=CALENDAR_ID,
            eventId=event_id,
            body=event_body
        ).execute()
    else:
        # Create new event
        service.events().insert(
            calendarId=CALENDAR_ID,
            body=event_body
        ).execute()
