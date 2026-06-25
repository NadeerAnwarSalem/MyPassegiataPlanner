import streamlit as st
import firebase_admin
import io

from translations import lang_dict
from firebase_admin import firestore, auth, credentials
from deep_translator import GoogleTranslator
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_calendar_service():
    google_secrets_dict = dict(st.secrets["gcp_service_account"])
    
    # FIX: Clean the private key for Google Calendar too!
    if "private_key" in google_secrets_dict:
        google_secrets_dict["private_key"] = google_secrets_dict["private_key"].replace("\\n", "\n")
        
    creds = service_account.Credentials.from_service_account_info(
        google_secrets_dict, scopes=SCOPES
    )
    return build('calendar', 'v3', credentials=creds)

def add_passegiata_to_calendar(title, passegiata_datetime, duration_minutes, description=""):
    try:
        service = get_calendar_service()

        # calculate time based on the provided datetime and duration
        start_time = passegiata_datetime.isoformat()
        end_time = (passegiata_datetime + timedelta(minutes=duration_minutes)).isoformat()

        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/Rome',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/Rome',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                    {'method': 'popup', 'minutes': 5 * 60},       #  5 hours before
                ],
            },
        }

        event_result = service.events().insert(calendarId='nadeersalem02@gmail.com', body=event).execute()
        return [event_result.get('id'), event_result.get('htmlLink')]  # Return the ID and link of the created event
    except Exception as e:  
        st.error(f"Error adding event to Google Calendar: {e}")
        return None

@st.cache_data
def translate_realtime(text, target_lang="Italiano"):
    """Translates any string into the current session language."""
    if not text or text == "N/A":
        return text
        
    target_langg = "it" if target_lang == "Italiano" else "en"
    
    try:
        translated = GoogleTranslator(source='auto', target=target_langg).translate(text)
        return translated
    except Exception as e:
        # If translation fails (e.g., no internet), return the original text
        return text
    
@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        key_dict = dict(st.secrets["firebase"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(dict(key_dict))
        app = firebase_admin.initialize_app(cred)
    else:
        app = firebase_admin.get_app()
    
    return firestore.client(app=app)

db = init_db()



def translate_logic(value, category, from_lang, to_lang):
    """Generic index-based translation helper."""
    try:
        from_list = lang_dict[from_lang][category]
        to_list = lang_dict[to_lang][category]
        if value in from_list:
            return to_list[from_list.index(value)]
    except:
        pass
    return value

def get_text():
    """Returns the dictionary for the currently selected language."""
    if 'lang' not in st.session_state:
        st.session_state['lang'] = "Italiano" # Default
    return lang_dict[st.session_state['lang']]

def lang_picker():
    with st.popover("🌐 Language / Lingua"):
        st.radio(
            "Select Language", 
            ["Italiano", "English"], 
            key="lang", 
            on_change=lambda: st.rerun
        )

def sidebar_auth():
    """Call this at the top of every page script."""
    
    T = get_text() # Get current translations
    
    if 'logged_in' in st.session_state:
        if st.session_state['logged_in']:
            if st.sidebar.button(T['log_out'], type="primary"):
                st.session_state.clear()
        else:
            st.sidebar.info(T['please_login'])
            if st.sidebar.button(T['go_to_login']):
                st.switch_page("pages/1_Login.py")

# Update your lists to be dynamic:
def get_species_list():
    return get_text()['species_list']

def get_gender_list():
    return get_text()['genders']


@st.dialog("Confirm Action")
def confirm_dialog(message, action_key):
    st.write(message)
    c1, c2 = st.columns([1, 1])
    with c1:
        if st.button("Yes, Proceed", key=f"confirm_{action_key}"):
            st.session_state[f"confirm_{action_key}"] = True
            st.rerun()
    with c2:
        if st.button("Cancel", key=f"confirm_{action_key}"):
            st.session_state[f"confirm_{action_key}"] = False 
            st.rerun()

def get_confirmation(action_key):
    return st.session_state.get(f"confirm_{action_key}", False)

def reset_confirm_state(action_key):
    st.session_state[f"confirm_{action_key}"] = False