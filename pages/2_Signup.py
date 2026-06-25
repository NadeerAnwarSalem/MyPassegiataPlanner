import streamlit as st
import firebase_admin
import time
from firebase_admin import credentials, auth, firestore
from utils import get_text, sidebar_auth, lang_picker # Added sidebar_auth for the language selector

# Initialize translations
T = get_text()

# Ensure the language selector/logout logic is present
sidebar_auth()
lang_picker()

@st.cache_resource
def init_db():
    if not firebase_admin._apps:
        cred = credentials.Certificate('permissions.json')
        app = firebase_admin.initialize_app(cred)
    else:
        app = firebase_admin.get_app()
    
    return firestore.client(app=app)

# Initialize the db
db = init_db()

st.title(T['create_acc'])

with st.form("signup_form"):
    st.subheader(T['sign_up'])
    email = st.text_input(T['email'])
    password = st.text_input(T['password'], type="password")
    username = st.text_input(T['user_name'])

    submit = st.form_submit_button(T['register'])

    if submit:
        try:
            # 1. Create User in Firebase Auth
            user = auth.create_user(
                email=email,
                password=password,
                display_name=username
            )

            # 2. Save Extra Info to Firestore
            user_data = {
                "uid": user.uid,
                "email": email,
                "username": username,   
            }
            
            db.collection("users").document(user.uid).set(user_data)

            st.success(T['reg_success'])
            st.info(T['redirecting'])
            st.balloons()
            time.sleep(2)
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = email
            st.session_state['username'] = username
            st.session_state['user_uid'] = user.uid
            st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")