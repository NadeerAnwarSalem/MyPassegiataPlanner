import streamlit as st
import requests
from datetime import datetime
from firebase_admin import firestore
from utils import sidebar_auth, get_text, lang_picker, add_passegiata_to_calendar


# Initialize translations
T = get_text()

# Standard sidebar logic (includes the Language Popover)
sidebar_auth()
lang_picker()

db = firestore.client()

if not st.session_state.get('logged_in'):
    st.warning(T['please_login'])
    st.stop()

st.title("Plan a Passegiata 🐾")



# ------------------------------------------------------------------
# 1. DATE SELECTION (Outside the form to trigger live availability queries)
# ------------------------------------------------------------------
selected_date = st.date_input(T["date"], min_value=datetime.today())

# Define your business slots and their global constraints
MAX_CAPACITY = 4
SLOT_CONFIGS = ["17:30 - 18:30", "19:00 - 20:00"]

# Query Firestore to check existing bookings for this specific date
existing_bookings = db.collection("passegiate").where("date", "==", str(selected_date)).stream()

# Calculate total spots taken per slot
booked_counts = {slot: 0 for slot in SLOT_CONFIGS}
for booking in existing_bookings:
    b_data = booking.to_dict()
    b_time = b_data.get("time")
    b_people = int(b_data.get("num_people", 0))
    if b_time in booked_counts:
        booked_counts[b_time] += b_people

# Generate readable availability options for the selectbox
slot_options = []
slot_availability = {}

for slot in SLOT_CONFIGS:
    spots_taken = booked_counts[slot]
    spots_left = MAX_CAPACITY - spots_taken
    slot_availability[slot] = spots_left
    
    if spots_left >= 2:
        label = f"{slot} ({spots_left} spots remaining)"
    elif spots_left > 0:
        label = f"❌ {slot} (Only {spots_left} left)"
    else:
        label = f"🔴 {slot} (FULLY BOOKED)"
    
    slot_options.append((slot, label))



# ------------------------------------------------------------------
# 2. BOOKING FORM
# ------------------------------------------------------------------
with st.form("plan_form"):
    st.subheader(T["Choose a date and time for your next walk!"])
    
    # Time Selectbox maps the clean internal keys ("17:30 - 18:30") to descriptive labels
    time = st.selectbox(
        T["time"], 
        options=[opt[0] for opt in slot_options],
        format_func=lambda x: next(opt[1] for opt in slot_options if opt[0] == x)
    )
    
    name = st.text_input(T["name"])
    
    with st.container():
        st.write(T["phone number"])
        c1, c2 = st.columns([1,5])
        with c1:
            countryCode = st.text_input(T["Country Code"], label_visibility="collapsed", value="+39", max_chars=4, help="Enter your country code (e.g., +39 for Italy)")
        with c2:
            phone = st.text_input(T["phone number"], label_visibility="collapsed", placeholder="123 456 7890")
            
    phone_number = f"{countryCode} {phone}" if countryCode and phone else ""
    
    # Calculate the maximum group size allowed right now for the selected slot
    current_spots_left = slot_availability.get(time, 0)
    max_allowed = min(MAX_CAPACITY, current_spots_left)
    
    num_people = st.number_input(T["num of ppl"], min_value=1, step=1, value=1)
        
    cost = st.text_input(T["how much"], value="35")  
    duration = st.selectbox(T["how long"], options=["1 hour", "2 hours", "3 hours"], index=0)
    
    submit = st.form_submit_button(T["Save Plan"])
    
    if submit:
        total_cost = int(num_people) * int(cost)
        current_spots_left = slot_availability.get(time, 0)
        if num_people > current_spots_left:
            st.error(f"❌ Cannot save! You entered {num_people} people, but {time} only has {current_spots_left} spots left.")
            st.stop()
        if not name or not phone_number:
            st.error("Please fill in all required fields.")
            st.stop()
            
        if num_people < 1:
            st.error("Cannot complete booking. Minimum 1 person required.")
            st.stop()
            
        if current_spots_left < num_people:
            st.error("Not enough spots available in this slot!")
            st.stop()

        try:
            # Add to Google Calendar
            combined_datetime = datetime.combine(selected_date, datetime.strptime(time.split(" - ")[0], "%H:%M").time())
            cal_event_id = add_passegiata_to_calendar(
                title=f"Passegiata with {name}",
                passegiata_datetime=combined_datetime,
                duration_minutes=int(duration.split()[0]) * 60,
                description=f"Passegiata for {num_people} people. Contact: {phone_number}"
            )
            if cal_event_id:
                passegiata_data = {
                    "date": str(selected_date),
                    "time": str(time),
                    "name": name,
                    "phone": phone_number,
                    "num_people": num_people,
                    "cost_per_person": int(cost),
                    "total_cost": total_cost,
                    "duration": duration,
                    "confirmed": False,
                    "paid": False,
                    "payment_method": "POS",
                    "calendar_event_id": cal_event_id[0],
                    "calendar_event_link": cal_event_id[1],
                    "registered_by": st.session_state.get('username', 'unknown'),
                    "created_at": firestore.SERVER_TIMESTAMP 
                }
                db.collection("passegiate").add(passegiata_data)
            st.success(f"Passegiata successfully planned for {selected_date} at {time}!")
            st.rerun()
        except Exception as e:
            st.error(f"Error saving passegiata: {e}")
        



# ------------------------------------------------------------------
# 3. ON-THE-PHONE LEDGER VIEW (Displays who is already booked today)
# ------------------------------------------------------------------
st.write("---")
st.subheader(f"📅 {T['daily_schedule']}: {selected_date}")

day_entries = db.collection("passegiate").where("date", "==", str(selected_date)).stream()
list_entries = [e.to_dict() for e in day_entries]

if not list_entries:
    st.info("No bookings registered yet for this day.")
else:
    import pandas as pd
    df_day = pd.DataFrame(list_entries)
    # Filter specific tracking columns to keep table narrow and readable on-screen
    display_cols = ["time", "name", "num_people", "phone", "registered_by"]
    df_clean = df_day[[col for col in display_cols if col in df_day.columns]]
    st.table(df_clean)