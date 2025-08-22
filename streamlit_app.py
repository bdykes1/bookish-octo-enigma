    st.session_state.all_users = {username: selections}

    df = pd.DataFrame(st.session_state.all_users).T
    df.columns = [datetime.fromisoformat(c).strftime("%a %b %d") for c in df.columns]

    st.subheader("📊 Your Selections")
    st.dataframe(
        df,
        use_container_width=True,
        height=250,
        column_config={
            col: st.column_config.TextColumn(
                label=f"**{col}**",
                width="medium",
                help="Lunch choice for this day"
            )
            for col in df.columns
        }
    )

    if st.button("Add to Calendar"):
        try:
            service = load_gcal_service()
            for date_str, entree in selections.items():
                upsert_calendar_event(service, date_str, entree, username)
            st.success("Events synced with Google Calendar!")
        except Exception as e:
            st.error(f"Calendar error: {e}")
