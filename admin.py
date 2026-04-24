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
        users = fetch_all(
            "SELECT id, email, name, role, amoeba, active FROM users ORDER BY name"
        )
        users_df = pd.DataFrame(
            users, columns=["ID", "Email", "Name", "Role", "Amoeba", "Active"]
        )
        st.dataframe(users_df, use_container_width=True)

        amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]

        st.markdown("#### Add New User")
        with st.form("add_user_form"):
            nu_email = st.text_input("Email / Login ID")
            nu_name = st.text_input("Full Name")
            nu_password = st.text_input("Password")
            nu_role = st.selectbox("Role", ["submitter", "approver", "admin"])
            nu_amoeba = st.selectbox("Amoeba", amoebas, key="add_user_amoeba")
            add_user_btn = st.form_submit_button("Add User")

        if add_user_btn:
            if not nu_email or not nu_name or not nu_password:
                st.error("Email, name and password are required.")
            else:
                try:
                    execute(
                        "INSERT INTO users (email, name, password, role, amoeba, active) VALUES (%s, %s, %s, %s, %s, 1::smallint)",
                        (nu_email, nu_name, nu_password, nu_role, nu_amoeba),
                    )
                    st.success("User added successfully.")
                    st.rerun()
                except Exception:
                    st.error("Email already exists. Please use a different email.")

        st.markdown("#### Edit / Deactivate Existing User")
        user_options = {
            str(u[0]) + " - " + u[2] + " (" + u[1] + ")": u[0] for u in users
        }
        if user_options:
            sel_label = st.selectbox(
                "Select user to edit", list(user_options.keys()), key="edit_user_select"
            )
            sel_id = user_options[sel_label]
            sel = fetch_one(
                "SELECT id, email, name, password, role, amoeba, active FROM users WHERE id=%s",
                (sel_id,),
            )
            if sel:
                with st.form("edit_user_form"):
                    ed_email = st.text_input("Email", value=sel[1])
                    ed_name = st.text_input("Name", value=sel[2])
                    ed_password = st.text_input("Password", value=sel[3])
                    ed_role = st.selectbox(
                        "Role", ["submitter", "approver", "admin"],
                        index=["submitter", "approver", "admin"].index(sel[4]),
                    )
                    ed_amoeba = st.selectbox(
                        "Amoeba", amoebas,
                        index=amoebas.index(sel[5]) if sel[5] in amoebas else 0,
                    )
                    ed_active = st.selectbox(
                        "Status", [1, 0],
                        index=0 if sel[6] == 1 else 1,
                        format_func=lambda x: "Active" if x == 1 else "Deactivated",
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        save_user_btn = st.form_submit_button("Save Changes")
                    with col2:
                        deactivate_btn = st.form_submit_button("Deactivate User")

                if save_user_btn:
                    execute(
                        "UPDATE users SET email=%s, name=%s, password=%s, role=%s, amoeba=%s, active=%s::smallint WHERE id=%s",
                        (ed_email, ed_name, ed_password, ed_role, ed_amoeba, ed_active, sel_id),
                    )
                    st.success("User updated.")
                    st.rerun()

                if deactivate_btn:
                    execute(
                        "UPDATE users SET active=0::smallint WHERE id=%s",
                        (sel_id,),
                    )
                    st.warning("User deactivated.")
                    st.rerun()

    # ── AMOEBAS ────────────────────────────────
    with tab2:
        st.markdown("### Amoeba Management")
        amoeba_rows = fetch_all(
            "SELECT id, name, approver_email, approver_name FROM amoebas ORDER BY name"
        )
        amoeba_df = pd.DataFrame(
            amoeba_rows, columns=["ID", "Amoeba", "Approver Email", "Approver Name"]
        )
        st.dataframe(amoeba_df, use_container_width=True)

        st.markdown("#### Add New Amoeba")
        with st.form("add_amoeba_form"):
            new_amoeba_name = st.text_input("Amoeba Name")
            add_amoeba_btn = st.form_submit_button("Add Amoeba")

        if add_amoeba_btn:
            if not new_amoeba_name:
                st.error("Amoeba name is required.")
            else:
                try:
                    execute(
                        "INSERT INTO amoebas (name, approver_email, approver_name) VALUES (%s, %s, %s)",
                        (new_amoeba_name, "", ""),
                    )
                    st.success("Amoeba added.")
                    st.rerun()
                except Exception:
                    st.error("Amoeba name already exists.")

        st.markdown("#### Edit / Delete / Assign Approver")
        amoeba_options = {
            str(a[0]) + " - " + a[1]: a[0] for a in amoeba_rows
        }
        if amoeba_options:
            sel_amoeba_label = st.selectbox(
                "Select amoeba to edit", list(amoeba_options.keys()), key="edit_amoeba_select"
            )
            sel_amoeba_id = amoeba_options[sel_amoeba_label]
            sel_amoeba = fetch_one(
                "SELECT id, name, approver_email, approver_name FROM amoebas WHERE id=%s",
                (sel_amoeba_id,),
            )

            if sel_amoeba:
                # -- build approver dropdown from users with role approver or admin --
                approver_users = fetch_all(
                    "SELECT email, name FROM users WHERE role IN ('approver','admin') AND active=1 ORDER BY name"
                )
                approver_options = {"-- No Approver --": ("", "")}
                for au_email, au_name in approver_users:
                    approver_options[au_name + " (" + au_email + ")"] = (au_email, au_name)

                current_approver_email = sel_amoeba[2] or ""
                current_approver_key = "-- No Approver --"
                for k, v in approver_options.items():
                    if v[0] == current_approver_email:
                        current_approver_key = k
                        break

                approver_keys = list(approver_options.keys())
                current_index = approver_keys.index(current_approver_key)

                with st.form("edit_amoeba_form"):
                    ed_amoeba_name = st.text_input("Amoeba Name", value=sel_amoeba[1])
                    ed_approver_label = st.selectbox(
                        "Assign Approver",
                        approver_keys,
                        index=current_index,
                    )
                    col1, col2 = st.columns(2)
                    with col1:
                        save_amoeba_btn = st.form_submit_button("Save Changes")
                    with col2:
                        delete_amoeba_btn = st.form_submit_button("Delete Amoeba")

                if save_amoeba_btn:
                    new_approver_email, new_approver_name = approver_options[ed_approver_label]
                    execute(
                        "UPDATE amoebas SET name=%s, approver_email=%s, approver_name=%s WHERE id=%s",
                        (ed_amoeba_name, new_approver_email, new_approver_name, sel_amoeba_id),
                    )
                    st.success("Amoeba updated with approver: " + (new_approver_name or "None"))
                    st.rerun()

                if delete_amoeba_btn:
                    used = fetch_one(
                        "SELECT COUNT(*) FROM transactions WHERE submitter_amoeba=%s OR counterparty_amoeba=%s",
                        (sel_amoeba[1], sel_amoeba[1]),
                    )[0]
                    if used > 0:
                        st.error("Cannot delete. This amoeba is used in " + str(used) + " transaction(s).")
                    else:
                        execute(
                            "DELETE FROM amoebas WHERE id=%s",
                            (sel_amoeba_id,),
                        )
                        st.warning("Amoeba deleted.")
                        st.rerun()

    # ── CATEGORIES ─────────────────────────────
    with tab3:
        st.markdown("### Category Management")
        cat_rows = fetch_all("SELECT id, name FROM categories ORDER BY name")
        cat_df = pd.DataFrame(cat_rows, columns=["ID", "Category"])
        st.dataframe(cat_df, use_container_width=True)

        st.markdown("#### Add New Category")
        with st.form("add_cat_form"):
            new_cat_name = st.text_input("Category Name")
            add_cat_btn = st.form_submit_button("Add Category")

        if add_cat_btn:
            if not new_cat_name:
                st.error("Category name is required.")
            else:
                try:
                    execute(
                        "INSERT INTO categories (name) VALUES (%s)",
                        (new_cat_name,),
                    )
                    st.success("Category added.")
                    st.rerun()
                except Exception:
                    st.error("Category name already exists.")

        st.markdown("#### Edit / Delete Existing Category")
        cat_options = {str(c[0]) + " - " + c[1]: c[0] for c in cat_rows}
        if cat_options:
            sel_cat_label = st.selectbox(
                "Select category to edit", list(cat_options.keys()), key="edit_cat_select"
            )
            sel_cat_id = cat_options[sel_cat_label]
            sel_cat = fetch_one(
                "SELECT id, name FROM categories WHERE id=%s",
                (sel_cat_id,),
            )
            if sel_cat:
                with st.form("edit_cat_form"):
                    ed_cat_name = st.text_input("Category Name", value=sel_cat[1])
                    col1, col2 = st.columns(2)
                    with col1:
                        save_cat_btn = st.form_submit_button("Save Changes")
                    with col2:
                        delete_cat_btn = st.form_submit_button("Delete Category")

                if save_cat_btn:
                    execute(
                        "UPDATE categories SET name=%s WHERE id=%s",
                        (ed_cat_name, sel_cat_id),
                    )
                    st.success("Category updated.")
                    st.rerun()

                if delete_cat_btn:
                    used = fetch_one(
                        "SELECT COUNT(*) FROM transactions WHERE category=%s",
                        (sel_cat[1],),
                    )[0]
                    if used > 0:
                        st.error("Cannot delete. This category is used in " + str(used) + " transaction(s).")
                    else:
                        execute(
                            "DELETE FROM categories WHERE id=%s",
                            (sel_cat_id,),
                        )
                        st.warning("Category deleted.")
                        st.rerun()

    # ── EXPORT ─────────────────────────────────
    with tab4:
        st.markdown("### Export Transactions")

        rows = fetch_all(
            """SELECT txn_code, submit_date, submitter_name, submitter_amoeba,
                      counterparty_amoeba, category, description, amount, currency,
                      approver_name, status, approval_comment, approval_datetime
               FROM transactions ORDER BY id DESC"""
        )

        df = pd.DataFrame(rows, columns=[
            "Transaction ID", "Submit Date", "Submitter", "From Amoeba",
            "To Amoeba", "Category", "Description", "Amount", "Currency",
            "Approver", "Status", "Approval Comment", "Approval Datetime",
        ])

        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name="transactions_export.csv",
            mime="text/csv",
        )

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        st.download_button(
            "Download Excel",
            data=output.getvalue(),
            file_name="transactions_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
