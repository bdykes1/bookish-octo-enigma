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


def create_or_update_calendar_event(service, date_str, entree, username):
    """Create or update a calendar event for a given user and date.
    If multiple exist, update one and delete extras."""
    
    # Pick start/end times by user
    if username == "Boston":
        start_time = datetime.fromisoformat(date_str).replace(hour=11, minute=0)
        end_time = start_time.replace(hour=12, minute=0)
    elif username == "Cannon":
        start_time = datetime.fromisoformat(date_str).replace(hour=12, minute=0)
        end_time = start_time.replace(hour=13, minute=0)
    else:
        start_time = datetime.fromisoformat(date_str).replace(hour=11, minute=0)
        end_time = start_time.replace(hour=12, minute=0)

    description = (
        f"{username} – {entree}"
        if entree != "Cold Lunch"
        else f"{username} is bringing a Cold Lunch"
    )

    event_body = {
        "summary": f"{username} – Lunch: {entree}",
        "description": description,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Chicago"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Chicago"},
    }

    # Search for events on that date (expand to whole day just in case)
    day_start = datetime.fromisoformat(date_str).replace(hour=0, minute=0, second=0)
    day_end = day_start.replace(hour=23, minute=59, second=59)

    events_result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=day_start.isoformat() + "Z",
        timeMax=day_end.isoformat() + "Z",
        singleEvents=True,
        orderBy="startTime"
    ).execute()

    events = events_result.get("items", [])

    # Filter for this user's lunch events
    user_events = [
        ev for ev in events
        if ev.get("summary", "").startswith(f"{username} – Lunch")
    ]

    if user_events:
        # Update the first event
        main_event = user_events[0]
        updated_event = service.events().update(
            calendarId=CALENDAR_ID,
            eventId=main_event["id"],
            body=event_body
        ).execute()

        # Delete duplicates
        for extra in user_events[1:]:
            service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=extra["id"]
            ).execute()

        return updated_event
    else:
        # No event exists, create one
        return service.events().insert(
            calendarId=CALENDAR_ID,
            body=event_body
        ).execute()

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
    Parses the Nutrislice API JSON and returns a dict of meals by day.
    Entrées are determined using display_name and menu_item_type/category_id.
    Sides are anything else.
    """
    meals_by_day = {}

    for day in json_data.get("days", []):
        date_str = day.get("date")
        entrees, sides = [], []

        for item in day.get("menu_items", []):
            food = item.get("food")
            if not food or not food.get("name"):
                continue

            # Prefer display_name if available
            name = food.get("display_name", food["name"]).strip()

            # Classify entree vs side
            menu_type = (item.get("menu_item_type") or "").lower()
            category = (item.get("category") or "").lower()
            
            if any(k in menu_type for k in ["main", "entree", "entrée", "alternate", "chef", "dish"]) \
               or any(k in category for k in ["main", "entree", "entrée", "alternate", "chef", "dish"]):
                entrees.append(name)
            elif menu_type.strip() == "" and category.strip() == "" and not any(
                s in name.lower() for s in ["fruit", "vegetable", "milk", "bread", "side"]
            ):
                entrees.append(name)
            else:
                sides.append(name)

        # Always add Cold Lunch
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
weekday = today.weekday()  # Monday=0 ... Sunday=6
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

if "all_users" not in st.session_state:
    st.session_state.all_users = {}

# Lunch selection + table (Mon–Fri only, scoped to current child)
if username:
    st.subheader(f"Lunch selections for {username}")
    selections = {}

    # Build Monday–Friday range from the chosen week
    week_days = [monday + timedelta(days=i) for i in range(5)]  # Mon–Fri

    for day_obj in week_days:
        date_str = day_obj.date().isoformat()
        meal_data = meals_by_day.get(date_str, {"entrees": ["Cold Lunch"], "sides": []})

        weekday_label = day_obj.strftime("%A %b %d")
        st.markdown(f"**{weekday_label}**")

        selections[date_str] = st.radio(
            "Choose an entree:",
            meal_data["entrees"],
            key=f"{username}_{date_str}"
        )

        if meal_data["sides"]:
            st.markdown("**Sides:**")
            for side in meal_data["sides"]:
                st.text(f"- {side}")

    # Save selections immediately
    st.session_state.all_users[username] = selections

    # --- Table for this child's choices only ---
    day_keys = [d.date().isoformat() for d in week_days]
    col_labels = [d.strftime("%a %b %d") for d in week_days]

    user_choices = st.session_state.all_users.get(username, {})
    df = pd.DataFrame([user_choices], index=[username])
    df = df.reindex(columns=day_keys)
    df.columns = col_labels

    st.subheader(f"📊 {username}'s Selections")
    st.table(df)

    # Add to Calendar button (only if at least one choice)
    if any(user_choices.values()):
        if st.button("Add to Calendar"):
            try:
                service = load_gcal_service()
                for date_str in day_keys:  # Only Mon–Fri
                    entree = user_choices.get(date_str)
                    if entree:  # only add if they selected something
                        create_or_update_calendar_event(service, date_str, entree, username)
                st.success(f"{username}'s events created/updated in Google Calendar!")
            except Exception as e:
                st.error(f"Calendar error: {e}")
