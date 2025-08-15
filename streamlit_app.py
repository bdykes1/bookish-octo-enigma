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
    """Extract a dict of {date: [food options]} from Nutrislice JSON."""
    meals_by_day = {}
    for day in json_data.get("days", []):
        date_str = day.get("date")  # 'YYYY-MM-DD'
        items = []
        for item in day.get("menu_items", []):
            food = item.get("food")
            if food and food.get("name"):
                items.append(food["name"])
        meals_by_day[date_str] = items
    return meals_by_day

def get_monday_of_week(date):
    """Return the Monday of the week containing the given date."""
    return date - timedelta(days=date.weekday())

# -------------------------
# STREAMLIT UI
# -------------------------
st.title("🍽 Echo Hill Lunch Picker")

# Determine current week's Monday
today = datetime.today()
monday = get_monday_of_week(today)

# Fetch menu for current week
try:
    menu_json = fetch_week_menu(monday.year, monday.month, monday.day)
    meals_by_day = parse_menu(menu_json)
except Exception as e:
    st.error(f"Could not fetch menu: {e}")
    st.stop()

# Input: username
username = st.text_input("Enter your name")

# Store selections in session
if "all_users" not in st.session_state:
    st.session_state.all_users = {}

if username:
    st.subheader(f"Lunch selections for {username}")

    selections = {}
    for date_str, options in meals_by_day.items():
        weekday = datetime.fromisoformat(date_str).strftime("%A %b %d")
        if options:
            selections[date_str] = st.radio(weekday, options, key=f"{username}_{date_str}")
        else:
            selections[date_str] = None

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
