# lunch_picker.py
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
DISTRICT = "linnmark12ia"
SCHOOL = "echo-hill"
MENU_TYPE = "lunch"

def build_api_url(year, month, day):
    return (
        f"https://{DISTRICT}.api.nutrislice.com/menu/api/weeks/school/"
        f"{SCHOOL}/menu-type/{MENU_TYPE}/{year}/{month:02d}/{day:02d}/"
    )

def fetch_week_menu(year, month, day):
    """Fetch Nutrislice weekly menu JSON for the given date."""
    url = build_api_url(year, month, day)
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def parse_menu(json_data):
    """
    Extract a dict of {date: [food options]} from Nutrislice JSON.
    Only include main and alternate lunch options (ignore sides).
    Add 'Cold lunch' as an option for each day.
    """
    meals_by_day = {}
    for day in json_data.get("days", []):
        date_str = day.get("date")  # 'YYYY-MM-DD'
        options = []

        for item in day.get("menu_items", []):
            food = item.get("food")
            if not food or not food.get("name"):
                continue

            # Include only main or alternate lunches
            category = item.get("category", "").lower()
            if "main" in category or "alternate" in category:
                options.append(food["name"])

        # Always add Cold lunch option
        options.append("Cold lunch")

        meals_by_day[date_str] = options
    return meals_by_day

def get_monday_of_week(date):
    """Return the Monday of the week containing the given date."""
    return date - timedelta(days=date.weekday())

# -------------------------
# STREAMLIT UI
# -------------------------
st.title("🍽 Echo Hill Lunch Picker")

# Determine the date for Monday, August 25, 2025
target_date = datetime(2025, 8, 25)
monday = get_monday_of_week(target_date)

# Fetch menu for the week of August 25, 2025
try:
    menu_json = fetch_week_menu(monday.year, monday.month, monday.day)
    meals_by_day = parse_menu(menu_json)
except Exception as e:
    st.error(f"Could not fetch menu: {e}")
    st.stop()

# Input: username (selectable from the start)
username = st.radio("Select your name:", ["Boston", "Cannon"])

# Store selections in session
if "all_users" not in st.session_state:
    st.session_state.all_users = {}

if username:
    st.subheader(f"Lunch selections for {username}")

    selections = {}
    for date_str, options in meals_by_day.items():
        weekday = datetime.fromisoformat(date_str).strftime("%A %b %d")
        selections[date_str] = st.radio(weekday, options, key=f"{username}_{date_str}")

    if st.button("Save My Choices"):
        st.session_state.all_users[username] = selections
        st.success("Choices saved!")

# Display table of all users
if st.session_state.all_users:
    df = pd.DataFrame(st.session_state.all_users).T
    df.columns = [
        datetime.fromisoformat(c).strftime("%a %b %d") for c in df.columns
    ]
    st.subheader("📊 All Selections")
    st.table(df)
