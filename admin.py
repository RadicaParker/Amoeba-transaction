import io
from datetime import datetime

import pandas as pd
import streamlit as st

from db import fetch_all, fetch_one, execute


def admin_portal_page():
    st.subheader("Admin Portal")
    tab1, tab2, tab3, tab4 = st.tabs(["Users", "Amoebas", "Categories", "Export"])

    # ── USERS ──────────────────────────────────
    with tab1:
        st.markdown("### User Management")
        users = fetch_all("SELECT id, email, name, role, amoeba
