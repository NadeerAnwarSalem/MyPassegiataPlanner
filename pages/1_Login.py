import streamlit as st
import requests
from firebase_admin import auth, firestore
from utils import sidebar_auth, get_text, lang_picker # Added get_text

# Initialize translations
T = get_text()

# Standard sidebar logic (includes the Language Popover)
sidebar_auth()
lang_picker()

API_KEY = "AIzaSyBWVdxH54JDtuCfjOb88OWITprRADXEjdw"
db = firestore.client()

def login_user(email, password):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    response = requests.post(url, json=payload)
    return response.json()

st.title(T['login_title'])

with st.form("login_form"):
    email = st.text_input(T['email'])
    password = st.text_input(T['password'], type="password")
    
    c1, c2 = st.columns([1.1, 8])
    with c1:    
        submit_button = st.form_submit_button(T['log_in'])
    with c2:
        signup_button = st.form_submit_button(T['sign_up'])

    if submit_button:
        try:
            result = login_user(email, password)
            if "error" in result:
                # Keeping the technical error message but translating the prefix
                st.error(f"Login failed: {result['error']['message']}")
            else:
                user_uid = result['localId']
                user_doc = db.collection("users").document(user_uid).get()
                
                st.session_state['logged_in'] = True 
                st.session_state['user_email'] = result['email']
                st.session_state['id_token'] = result['idToken']
                st.session_state['username'] = result.get('displayName', '')
                st.session_state['user_uid'] = user_uid
                
                st.write(f"{T['welcome_back']}, {st.session_state['username']}!")
                st.success(T['login_success'])
                st.info(T['redirecting'])
                st.switch_page("pages/3_Plan.py")
        except requests.exceptions.ConnectionError:
            st.error("Login failed: Check your connection and try again.")
        except Exception as e:
            st.error(f"Error: {e}")

    if signup_button:
        st.info(T['redirecting'])
        st.switch_page("pages/2_Signup.py")

st.divider()

with st.expander(T['forgot_pw']):
    reset_email = st.text_input(T['reset_link_msg'])
    if st.button(T['send_reset']):
        if reset_email:
            try:
                link = auth.generate_password_reset_link(reset_email)
                st.success("Reset link generated!")
                st.info(f"Link: {link}")
            except Exception as e:
                st.error(f"Error: {e}")