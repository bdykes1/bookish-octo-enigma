# lunch_picker.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Google Calendar imports
from google.oauth2 import service_account
from googleapiclient.discovery import build

# -------------------------
# CONFIG
# -------------------------
DISTRICT = "linnmark12ia"
SCHOOL = "echo-hill"
MENU_TYPE = "lunch"
CALENDAR_ID = "449a3e735292d623fa0eec60e35d5f4b90c9dc5627c936cc94b4600056219d65@group.calendar.google.com"

# -------------------------
# GOOGLE CALENDAR SETUP
# -------------------------
@st.cache_resource
def load_gcal_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds)

def upsert_calendar_event(service, date_str, entree, username):
    """Update existing event for a user/day or create a new one. Remove duplicates."""
    if username == "Boston":
        start_time = datetime.fromisoformat(date_str).replace(hour=11, minute=0)
        end_time = start_time.replace(hour=12, minute=0)
    elif username == "Cannon":
        start_time = datetime.fromisoformat(date_str).replace(hour=12, minute=0)
        end_time = start_time.replace(hour=13, minute=0)
    else:
        start_time = datetime.fromisoformat(date_str).replace(hour=11, minute=0)
        end_time = start_time.replace(hour=12, minute=0)

    description = f"{username} – {entree}" if entree != "Cold Lunch" else f"{username} is bringing a Cold Lunch"

    # Search for existing events
    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=start_time.isoformat() + "Z",
        timeMax=end_time.isoformat() + "Z",
        q=username,
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    if events:
        # Update the first event
        event = events[0]
        event["summary"] = f"{username} – Lunch: {entree}"
        event["description"] = description
        event["start"]["dateTime"] = start_time.isoformat()
        event["end"]["dateTime"] = end_time.isoformat()
        service.events().update(calendarId=CALENDAR_ID, eventId=event["id"], body=event).execute()

        # Delete duplicates
        for extra in events[1:]:
            service.events().delete(calendarId=CALENDAR_ID, eventId=extra["id"]).execute()
    else:
        # Create new event
        event = {
            "summary": f"{username} – Lunch: {entree}",
            "description": description,
            "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Chicago"},
            "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Chicago"},
        }
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

# -------------------------
# NUTRISLICE HELPERS
# -------------------------
def build_api_url(year, month, day):
    return (
        f"https://{DISTRICT}.api.nutrislice.com/menu/api/weeks/school/"
        f"{SCHOOL}/menu-type/{MENU_TYPE}/{year}/{month:02d}/{day:02d}/"
    )

def fetch_week_menu(year, month, day):
    url = build_api_url(year, month, day)
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def parse_menu(json_data):
    """
    Parses the Nutrislice API JSON.
    - Treats all items as entrées unless their category is explicitly 'side'
    """
    meals_by_day = {}

    for day in json_data.get("days", []):
        date_str = day.get("date")
        entrees, sides = [], []

        for item in day.get("menu_items", []):
            food = item.get("food")
            if not food or not food.get("name"):
                continue

            name = food.get("display_name", food["name"]).strip()
            category = (item.get("category") or "").lower()

            if category == "side":
                sides.append(name)
            else:
                entrees.append(name)

        # Always add Cold Lunch as an option
        entrees.append("Cold Lunch")
        meals_by_day[date_str] = {"entrees": entrees, "sides": sides}

    return meals_by_day

def get_monday_of_week(date):
    return date - timedelta(days=date.weekday())

# -------------------------
# STREAMLIT UI
# -------------------------
st.title("🍽 Echo Hill Lunch Picker")

# Dynamic week selection
today = datetime.now()
weekday = today.weekday()
if weekday <= 2:  # Mon-Wed
    target_date = today
else:  # Thu-Sun
    target_date = today + timedelta(days=(7 - weekday))
monday = get_monday_of_week(target_date)
week_str = monday.strftime("%b %d")
st.subheader(f"Lunch selections for the week of {week_str}")

# Fetch menu
try:
    menu_json = fetch_week_menu(monday.year, monday.month, monday.day)
    meals_by_day = parse_menu(menu_json)
except Exception as e:
    st.error(f"Could not fetch menu: {e}")
    st.stop()

# Kid selection buttons
if "username" not in st.session_state:
    st.session_state.username = None

st.write("### Select your name:")
col1, col2 = st.columns(2)
with col1:
    if st.button("👦 Boston"):
        st.session_state.username = "Boston"
with col2:
    if st.button("🧒 Cannon"):
        st.session_state.username = "Cannon"

username = st.session_state.username

if username:
    st.subheader(f"Lunch selections for {username}")
    selections = {}
    # Only Mon–Fri
    week_days = [monday + timedelta(days=i) for i in range(5)]
    for day_obj in week_days:
        date_str = day_obj.date().isoformat()
        meal_data = meals_by_day.get(date_str, {"entrees": ["Cold Lunch"], "sides": []})

        st.markdown(f"**{day_obj.strftime('%A %b %d')}**")
        selections[date_str] = st.radio(
            "Choose an entree:",
            meal_data["entrees"],
            key=f"{username}_{date_str}"
        )
        if meal_data["sides"]:
            st.markdown("**Sides:**")
            for side in meal_data["sides"]:
                st.text(f"- {side}")

    # Save selections
    st.session_state.all_users = {username: selections}

    # Display table for current child
    df = pd.DataFrame(st.session_state.all_users).T
    df.columns = [datetime.fromisoformat(c).strftime("%a %b %d") for c in df.columns]
    st.subheader("📊 Your Selections")
    st.table(df)

    # Add to Calendar button
    if st.button("Add to Calendar"):
        try:
            service = load_gcal_service()
            for date_str, entree in selections.items():
                upsert_calendar_event(service, date_str, entree, username)
            st.success("Events synced with Google Calendar!")
        except Exception as e:
            st.error(f"Calendar error: {e}")
