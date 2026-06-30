from datetime import datetime, timedelta

import pandas as pd
import io
from xhtml2pdf import pisa
import streamlit as st
import firebase_admin
from firebase_admin import auth, credentials, firestore
from utils import sidebar_auth, get_text, lang_picker , add_passegiata_to_calendar, get_calendar_service

st.set_page_config(
    page_title="Passeggiata Planner",  # Change this to whatever name you want
    page_icon="🚶‍♂️",                  # Can be an emoji or a URL to a custom logo image
    layout="centered"
)

# Initialize translations
T = get_text()

lang_picker()  # Ensure the language picker is available in the sidebar

@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate('permission.json')
        app = firebase_admin.initialize_app(cred)
    else:
        app = firebase_admin.get_app()
    
    return firestore.client(app=app)

db = init_db()
sidebar_auth()

# ------------------------------------------------------------------
# BACKEND OPERATIONS FUNCTIONS
# ------------------------------------------------------------------
def update_entire_passegiata(doc_id, cal_event_id, name_key, phone_key, people_key, cost_key, duration_key):
    try:
        updated_data = {
            "name": st.session_state.get(name_key),
            "phone": st.session_state.get(phone_key),
            "num_people": st.session_state.get(people_key),
            "cost_per_person": st.session_state.get(cost_key),
            "total_cost": st.session_state.get(people_key) * st.session_state.get(cost_key),
            "duration": st.session_state.get(duration_key),
        }

        db.collection("passegiate").document(doc_id).set(updated_data, merge=True)

        # Update Google Calendar event if it exists
        if cal_event_id:
            service = get_calendar_service()
            event = service.events().get(calendarId='nadeersalem02@gmail.com', eventId=cal_event_id).execute()

            # Update the event details
            event['summary'] = f"Passegiata with {updated_data['name']}"
            event['description'] = f"Passegiata for {updated_data['num_people']} people. Contact: {updated_data['phone']}"

            # Update the duration if it has changed
            if updated_data['duration']:
                duration_hours = int(updated_data['duration'].split()[0])
                start_time = event['start']['dateTime']
                end_time = (datetime.fromisoformat(start_time) + timedelta(hours=duration_hours)).isoformat()
                event['end']['dateTime'] = end_time

            service.events().update(calendarId='nadeersalem02@gmail.com', eventId=cal_event_id, body=event).execute()


        st.toast("📝 Passegiata updated successfully!")
    except Exception as e:
        st.error(f"Failed to update document: {e}")

def update_payment_status(doc_id, box_key):
    try:
        new_value = st.session_state.get(box_key)
        if new_value:
            db.collection("passegiate").document(doc_id).update({
                "payment_method": new_value
            })
            st.toast(f"✅ Payment updated to {new_value}!")
    except Exception as e:
        st.error(f"Failed to update database: {e}")

def update_paid_status(doc_id, box_key):
    try:
        is_paid = st.session_state.get(box_key)
        if is_paid is not None:
            db.collection("passegiate").document(doc_id).set({
                "paid": is_paid
            }, merge=True)
            
            if is_paid:
                st.toast("💰 Marked as Paid!")
            else:
                st.toast("⚠️ Marked as Unpaid!")
    except Exception as e:
        st.error(f"Failed to update database: {e}")

def update_confirmed_status(doc_id, box_key):
    try:
        is_confirmed = st.session_state.get(box_key)
        if is_confirmed is not None:
            db.collection("passegiate").document(doc_id).set({
                "confirmed": is_confirmed
            }, merge=True)
            
            if is_confirmed:
                st.toast("✅ Marked as Confirmed!")
            else:
                st.toast("⚠️ Marked as Unconfirmed!")
    except Exception as e:
        st.error(f"Failed to update database: {e}")

def delete_passegiata(doc_id, cal_event_id):
    try:
        db.collection("passegiate").document(doc_id).delete()
        
        if cal_event_id:
            service = get_calendar_service()
            service.events().delete(
                calendarId='nadeersalem02@gmail.com',
                eventId=cal_event_id
            ).execute()

        st.toast("🗑️ Passegiata deleted!")
    except Exception as e:
        st.error(f"Failed to delete: {e}")

# ------------------------------------------------------------------
# MAIN INTERFACE & FILTER CONTROLS
# ------------------------------------------------------------------
st.title("Scheduled Passegiate 🐾")
st.divider()

# Start building our base Firestore collection query path
query_ref = db.collection("passegiate")

# Filter popover element
with st.popover("🔍 Filter Schedule"):
    time_slots = ["17:30 - 18:30", "19:00 - 20:00"]
    selected_time = st.selectbox("Select Time Slot", options=["All"] + time_slots)
    selected_date = st.date_input("Select Date", value=None)
    confirmed_status = st.selectbox("Show only confirmed passegiate", options=["All", "Confirmed", "Pending"])
    paid_status = st.selectbox("Show only paid passegiate", options=["All", "Paid", "Unpaid"])
    payment_method = st.selectbox("Filter by Payment Method", options=["All", "CASH", "POS"])
    



# Apply the conditions to our Firestore query if target dates/times are active
if selected_date is not None:
    query_ref = query_ref.where("date", "==", str(selected_date))
if selected_time != "All":
    query_ref = query_ref.where("time", "==", str(selected_time))
if confirmed_status != "All":
    query_ref = query_ref.where("confirmed", "==", confirmed_status == "Confirmed")
if paid_status != "All":
    query_ref = query_ref.where("paid", "==", paid_status == "Paid")
if payment_method != "All":
    query_ref = query_ref.where("payment_method", "==", payment_method)

# Execute the final queried reference
passegiate_entries = list(query_ref.stream())

# ------------------------------------------------------------------
# CARD DISPLAY LOOP
# ------------------------------------------------------------------
if not passegiate_entries:
    st.info("No passegiate found matching your filters.")
else:
    for entry in passegiate_entries:
        data = entry.to_dict()
        doc_id = entry.id 

        with st.container(border=True):
            # Header Row
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(f"🐾 Walk with {data.get('name', 'Anonymous')} ({'CONFIRMED' if data.get('confirmed', False) else 'PENDING'})")
            with col2:
                st.metric(label="Total Cost", value=f"{data.get('total_cost', 0)}€")
            
            # Details Grid
            details_col1, details_col2, details_col3 = st.columns(3)
            with details_col1:
                st.markdown(f"🗓️ **Date:** {data.get('date')}")
                st.markdown(f"🕒 **Time:** {data.get('time')}")
            with details_col2:
                st.markdown(f"👥 **People:** {data.get('num_people', 0)}")
                st.markdown(f"⏳ **Duration:** {data.get('duration', 'N/A')}")
            with details_col3:
                st.markdown(f"📞 **Phone:** `{data.get('phone', 'N/A')}`")
                st.markdown(f"💰 **Cost/Person:** {data.get('cost_per_person', 0)}€")
            
            # Management settings accessible only to logged in users
            if st.session_state.get('logged_in'):
                current_payment = data.get("payment_method", "POS")
                default_index = 0 if current_payment == "CASH" else 1
                
                current_paid_status = data.get("paid", False)
                current_confirmed_status = data.get("confirmed", False)
                paid_check_key = f"paid_{doc_id}"
                confirmed_check_key = f"confirmed_{doc_id}"

                box_key = f"payment_{doc_id}"
                
                with st.container():
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        st.checkbox(
                            "Paid", 
                            value=current_paid_status,
                            key=paid_check_key,
                            on_change=update_paid_status,
                            kwargs={"doc_id": doc_id, "box_key": paid_check_key}
                        ) 

                        st.checkbox(
                            "confirmed", 
                            value=current_confirmed_status,
                            key=confirmed_check_key,
                            on_change=update_confirmed_status,
                            kwargs={"doc_id": doc_id, "box_key": confirmed_check_key}
                        ) 

                        edit_name_key = f"edit_name_{doc_id}"
                        edit_phone_key = f"edit_phone_{doc_id}"
                        edit_people_key = f"edit_people_{doc_id}"
                        edit_cost_key = f"edit_cost_{doc_id}"
                        edit_duration_key = f"edit_duration_{doc_id}"
                        
                        with st.popover("✏️ Edit Details"):
                            st.write(f"### Editing Walk for {data.get('name')}")
                            st.text_input("Name", value=data.get("name", ""), key=edit_name_key)
                            st.text_input("Phone", value=data.get("phone", ""), key=edit_phone_key)
                            st.number_input("People", value=int(data.get("num_people", 2)), min_value=1, key=edit_people_key)
                            st.number_input("Cost per Person (€)", value=int(data.get("cost_per_person", 0)), min_value=0, key=edit_cost_key)
                            st.text_input("Duration", value=data.get("duration", ""), key=edit_duration_key)
                            
                            st.button(
                                "Save Changes", 
                                key=f"btn_{doc_id}",
                                on_click=update_entire_passegiata,
                                kwargs={
                                    "doc_id": doc_id,
                                    "name_key": edit_name_key,
                                    "phone_key": edit_phone_key,
                                    "people_key": edit_people_key,
                                    "cost_key": edit_cost_key,
                                    "duration_key": edit_duration_key,
                                    "cal_event_id": data.get("calendar_event_id")
                                }
                            )
                    with c2:
                        st.selectbox(
                            T['payment'], 
                            options=["CASH", "POS"], 
                            index=default_index,
                            key=box_key,
                            on_change=update_payment_status,
                            kwargs={"doc_id": doc_id, "box_key": box_key} 
                        )

                        st.button(
                            "Delete",
                            type="primary",
                            key=f"del_{doc_id}",
                            on_click=delete_passegiata,
                            kwargs={"doc_id": doc_id, "cal_event_id": data.get("calendar_event_id")},
                            use_container_width=True
                        )
            st.write("")
    
    #export all current entries to Excel-like table for admin users
    rows_list = []
    for entry in passegiate_entries:
        data = entry.to_dict()
        row = {
            "Date": entry.get('date'), 
            "Time": entry.get('time'), 
            "Name": entry.get('name'), 
            "Phone": entry.get('phone'), 
            "Num People": entry.get('num_people'), 
            "Confirmation": "Confirmed" if entry.get('confirmed') == True else "Not Confirmed"
        }
        rows_list.append(row)

df = pd.DataFrame(rows_list)

html_table = df.to_html(index=False, classes='walk-table')

html_string = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        @page {{
            size: letter;
            margin: 15mm;
        }}
        body {{
            font-family: Arial, sans-serif;
            color: #333;
        }}
        h2 {{
            color: #2e5a44;
            border-bottom: 2px solid #2e5a44;
            padding-bottom: 8px;
            margin-bottom: 20px;
        }}
        .walk-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        .walk-table th {{
            background-color: #2e5a44;
            color: white;
            font-weight: bold;
            padding: 10px;
            text-align: left;
            font-size: 12px;
        }}
        .walk-table td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
            font-size: 11px;
        }}
    </style>
</head>
<body>
    <h2>🚶 Planned Walks Report (Admin Export)</h2>
    <p style="font-size: 10px; color: #666;">Generated on: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>
    {html_table}
</body>
</html>
"""

def convert_html_to_pdf(html_src):
    pdf_buffer = io.BytesIO()
    # pisa writes the PDF bytes directly into our memory buffer
    pisa_status = pisa.CreatePDF(html_src, dest=pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


pdf_data = convert_html_to_pdf(html_string)


st.download_button(
    label="📥 Download Schedule as PDF",
    data=pdf_data,
    file_name='passegiate_report.pdf',
    mime='application/pdf'
)

# Session state initialization safety boundaries
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = None