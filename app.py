import streamlit as st
from db import init_db, seed_data
from auth import login_page, logout
from views import (
    process_email_action,
    submit_transaction_page,
    my_transactions_page,
    approval_queue_page,
)
from admin import admin_portal_page

st.set_page_config(page_title="Radica Amoeba Internal Transaction", layout="wide")

init_db()
seed_data()

process_email_action()

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    login_page()
    st.stop()

user = st.session_state.user

st.title("Radica Amoeba Internal Transaction")
st.caption(
    "Logged in as: " + user["name"] +
    " (" + user["role"] + ") | Amoeba: " + user["amoeba"]
)

with st.sidebar:
    st.header("Navigation")
    menu = ["Submit Transaction", "My Transactions"]
    if user["role"] in ["approver", "admin"]:
        menu.append("Approval Queue")
    if user["role"] == "admin":
        menu.append("Admin Portal")
    page = st.radio("Go to", menu)
    if st.button("Logout"):
        logout()

if page == "Submit Transaction":
    submit_transaction_page(user)
elif page == "My Transactions":
    my_transactions_page(user)
elif page == "Approval Queue":
    approval_queue_page(user)
elif page == "Admin Portal":
    admin_portal_page()
