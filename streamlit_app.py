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
    Extract a dict of {date: {"entrees": [...], "sides": [...]}} from Nutrislice JSON.
    Include main and alternate entrees as selectable options, plus 'Cold lunch'.
    Sides are listed but not selectable.
    """
    meals_by_day = {}
    for day in json_data.get("days", []):
        date_str = day.get("date")  # 'YYYY-MM-DD'
        entrees = []
        sides = []

        for item in day.get("menu_items", []):
            food = item.get("food")
            if not food or not food.get("name"):
                continue

            category = item.get("category", "")

            # Case-insensitive check for entrees
            if "main entree" in category.lower() or "alternate entree" in category.lower():
                entrees.append(food["name"])
            else:
                sides.append(food["name"])

        # Always add Cold Lunch as an entree option
        entrees.append("Cold Lunch")

        meals_by_day[date_str] = {"entrees": entrees, "sides": sides}
    return meals_by_day

def get_monday_of_week(date):
    """Return the Monday of the week containing the given date."""
    return date - timedelta(days=date.weekday())

# -------------------------
# STREAMLIT UI
# -------------------------
st.title("🍽 Echo Hill Lunch Picker")

# Target week: Monday, August 25, 2025
target_date = datetime(2025, 8, 25)
monday = get_monday_of_week(target_date)

# Fetch menu
try:
    menu_json = fetch_week_menu(monday.year, monday.month, monday.day)
    meals_by_day = parse_menu(menu_json)
except Exception as e:
    st.error(f"Could not fetch menu: {e}")
    st.stop()

# User selection
username = st.radio("Select your name:", ["Boston", "Cannon"])

# Store selections in session
if "all_users" not in st.session_state:
    st.session_state.all_users = {}

if username:
    st.subheader(f"**Lunch selections for {username}**")
    selections = {}
    for date_str, meal_data in meals_by_day.items():
        weekday = datetime.fromisoformat(date_str).strftime("%A %b %d")
        st.markdown(f"**{weekday}**")

        # Entree selection (radio buttons)
        selections[date_str] = st.radio("Choose an entree:", meal_data["entrees"], key=f"{username}_{date_str}")

        # Display sides below (not selectable), one per line
        if meal_data["sides"]:
            st.markdown("**Sides:**")
            for side in meal_data["sides"]:
                st.text(f"- {side}")

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
