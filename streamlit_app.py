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
CALENDAR_ID = "449a3e735292d623fa0eec60e35d5f4b90c9dc5627c936cc94b4600056219d65@group.calendar.google.com"  # or your school calendar email

# -------------------------
# GOOGLE CALENDAR SETUP
# -------------------------
@st.cache_resource
def load_gcal_service():
    # Load service account credentials from Streamlit secrets
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds)

def create_calendar_event(service, date_str, entree, sides):
    """Create a calendar event from lunch selection"""
    start_time = datetime.fromisoformat(date_str).replace(hour=11, minute=0)
    end_time = start_time.replace(hour=12, minute=0)

    if entree == "Cold Lunch":
        description = "Cold Lunch"
    else:
        description = f"{entree}\n\nSides:\n" + "\n".join(sides)

    event = {
        "summary": f"Lunch: {entree}",
        "description": description,
        "start": {"dateTime": start_time.isoformat(), "timeZone": "America/Chicago"},
        "end": {"dateTime": end_time.isoformat(), "timeZone": "America/Chicago"},
    }

    return service.events().insert(calendarId=CALENDAR_ID, body=event).execute()

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
    meals_by_day = {}
    for day in json_data.get("days", []):
        date_str = day.get("date")
        entrees, sides = [], []

        for item in day.get("menu_items", []):
            food = item.get("food")
            if not food or not food.get("name"):
                continue
            category = item.get("category", "")
            if "Main Entrée" in category or "Alternate Entrée" in category:
                entrees.append(food["name"])
            else:
                sides.append(food["name"])

        entrees.append("Cold Lunch")
        meals_by_day[date_str] = {"entrees": entrees, "sides": sides}
    return meals_by_day

def get_monday_of_week(date):
    return date - timedelta(days=date.weekday())

# -------------------------
# STREAMLIT UI
# -------------------------
st.title("🍽 Echo Hill Lunch Picker")

target_date = datetime(2025, 8, 25)
monday = get_monday_of_week(target_date)

try:
    menu_json = fetch_week_menu(monday.year, monday.month, monday.day)
    meals_by_day = parse_menu(menu_json)
except Exception as e:
    st.error(f"Could not fetch menu: {e}")
    st.stop()

username = st.radio("Select your name:", ["Boston", "Cannon"])

if "all_users" not in st.session_state:
    st.session_state.all_users = {}

if username:
    st.subheader(f"Lunch selections for {username}")
    selections = {}
    for date_str, meal_data in meals_by_day.items():
        weekday = datetime.fromisoformat(date_str).strftime("%A %b %d")
        st.markdown(f"**{weekday}**")
        selections[date_str] = st.radio(
            "Choose an entree:", meal_data["entrees"], key=f"{username}_{date_str}"
        )
        if meal_data["sides"]:
            st.markdown("**Sides:**")
            for side in meal_data["sides"]:
                st.text(f"- {side}")

    if st.button("Save My Choices"):
        st.session_state.all_users[username] = selections
        st.success("Choices saved!")

# Display and push to calendar
if st.session_state.all_users:
    df = pd.DataFrame(st.session_state.all_users).T
    df.columns = [datetime.fromisoformat(c).strftime("%a %b %d") for c in df.columns]
    st.subheader("📊 All Selections")
    st.table(df)

    if st.button("📅 Push to Google Calendar"):
        try:
            service = load_gcal_service()
            for user, choices in st.session_state.all_users.items():
                for date_str, entree in choices.items():
                    sides = meals_by_day[date_str]["sides"]
                    create_calendar_event(service, date_str, entree, sides)
            st.success("Events created in Google Calendar!")
        except Exception as e:
            st.error(f"Calendar error: {e}")
