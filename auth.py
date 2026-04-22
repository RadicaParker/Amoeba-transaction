import streamlit as st
from db import fetch_all


def login_page():
    st.title("Radica Amoeba Internal Transaction")
    st.subheader("Login")

    with st.form("login_form"):
        email = st.text_input("Login ID / Email")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

    if submit:
        rows = fetch_all(
            """
            SELECT email, name, role, amoeba
            FROM users
            WHERE email = :email
              AND password = :password
              AND active = TRUE
            """,
            {"email": email, "password": password},
        )

        if rows:
            r = rows[0]
            st.session_state.user = {
                "email": r[0],
                "name": r[1],
                "role": r[2],
                "amoeba": r[3],
            }
            st.rerun()
        else:
            st.error("Invalid login ID or password.")


def logout():
    st.session_state.user = None
    st.rerun()
