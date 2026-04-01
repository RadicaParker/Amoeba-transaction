import io
from datetime import datetime
import pandas as pd
import streamlit as st
from app.db import fetch_all, execute, next_txn_code


CURRENCIES = ["HKD", "CNY", "USD"]
STATUSES = ["Pending Approval", "Approved", "Rejected"]


def submit_transaction_page(user):
    st.subheader("Submit Transaction")
    amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
    categories = [r[0] for r in fetch_all("SELECT name FROM categories ORDER BY name")]
    approvers = fetch_all("SELECT email, name FROM users WHERE role IN ('approver','admin') AND active = 1 ORDER BY name")
    approver_map = {f"{name} ({email})": (email, name) for email, name in approvers if email != user['email']}

    with st.form("txn_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            counterparty_amoeba = st.selectbox("Counterparty Amoeba / Department", amoebas)
            category = st.selectbox("Category", categories)
            currency = st.selectbox("Currency", CURRENCIES)
            amount = st.number_input("Amount", min_value=0.0, step=0.01)
        with c2:
            approver_label = st.selectbox("Approver", list(approver_map.keys()))
            description = st.text_area("Description / Remarks")
            attachment = st.file_uploader("Attachment", type=None)

        submitted = st.form_submit_button("Submit")

    if submitted:
        approver_email, approver_name = approver_map[approver_label]
        attachment_name = attachment.name if attachment else ""
        execute(
            '''INSERT INTO transactions (
                txn_code, submit_date, submitter_email, submitter_name, submitter_amoeba,
                counterparty_amoeba, category, description, amount, currency,
                approver_email, approver_name, attachment_name, status, approval_comment, approval_datetime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                next_txn_code(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["email"], user["name"], user["amoeba"],
                counterparty_amoeba, category, description, amount, currency,
                approver_email, approver_name, attachment_name, "Pending Approval", "", ""
            )
        )
        st.success("Transaction submitted. Email approval logic can be added in the next version.")


def my_transactions_page(user):
    st.subheader("My Transactions")
    rows = fetch_all(
        "SELECT txn_code, submit_date, submitter_amoeba, counterparty_amoeba, category, amount, currency, approver_name, status, approval_comment, approval_datetime FROM transactions WHERE submitter_email = ? ORDER BY id DESC",
        (user["email"],),
    )
    df = pd.DataFrame(rows, columns=["Transaction ID", "Submit Date", "From Amoeba", "To Amoeba", "Category", "Amount", "Currency", "Approver", "Status", "Approval Comment", "Approval Datetime"])
    st.dataframe(df, use_container_width=True)


def approval_queue_page(user):
    st.subheader("Approval Queue")
    rows = fetch_all(
        "SELECT id, txn_code, submit_date, submitter_name, submitter_amoeba, counterparty_amoeba, category, amount, currency, description, status FROM transactions WHERE approver_email = ? AND status = 'Pending Approval' ORDER BY id DESC",
        (user["email"],),
    )

    if not rows:
        st.info("No pending approvals.")
        return

    for r in rows:
        txn_id, txn_code, submit_date, submitter_name, from_amoeba, to_amoeba, category, amount, currency, description, status = r
        with st.expander(f"{txn_code} | {submitter_name} | {amount:.2f} {currency}"):
            st.write(f"Submit Date: {submit_date}")
            st.write(f"From: {from_amoeba}")
            st.write(f"To: {to_amoeba}")
            st.write(f"Category: {category}")
            st.write(f"Description: {description}")
            comment = st.text_input(f"Comment for {txn_code}", key=f"comment_{txn_id}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Approve {txn_code}", key=f"approve_{txn_id}"):
                    execute(
                        "UPDATE transactions SET status = ?, approval_comment = ?, approval_datetime = ? WHERE id = ?",
                        ("Approved", comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txn_id),
                    )
                    st.success(f"{txn_code} approved")
                    st.rerun()
            with c2:
                if st.button(f"Reject {txn_code}", key=f"reject_{txn_id}"):
                    execute(
                        "UPDATE transactions SET status = ?, approval_comment = ?, approval_datetime = ? WHERE id = ?",
                        ("Rejected", comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txn_id),
                    )
                    st.warning(f"{txn_code} rejected")
                    st.rerun()


def admin_portal_page():
    st.subheader("Admin Portal")
    tab1, tab2, tab3, tab4 = st.tabs(["Users", "Amoebas", "Categories", "Export"])

    with tab1:
        st.markdown("### Users")
        users = fetch_all("SELECT email, name, role, amoeba, active FROM users ORDER BY name")
        st.dataframe(pd.DataFrame(users, columns=["Email", "Name", "Role", "Amoeba", "Active"]), use_container_width=True)
        with st.form("add_user"):
            email = st.text_input("Email / Login ID")
            name = st.text_input("Name")
            password = st.text_input("Password")
            role = st.selectbox("Role", ["submitter", "approver", "admin"])
            amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
            amoeba = st.selectbox("Amoeba", amoebas)
            if st.form_submit_button("Add User"):
                execute("INSERT INTO users (email, name, password, role, amoeba, active) VALUES (?, ?, ?, ?, ?, 1)", (email, name, password, role, amoeba))
                st.success("User added")
                st.rerun()

    with tab2:
        st.markdown("### Amoebas")
        amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
        st.write(amoebas)
        with st.form("add_amoeba"):
            new_amoeba = st.text_input("New Amoeba")
            if st.form_submit_button("Add Amoeba"):
                execute("INSERT INTO amoebas (name) VALUES (?)", (new_amoeba,))
                st.success("Amoeba added")
                st.rerun()

    with tab3:
        st.markdown("### Categories")
        cats = [r[0] for r in fetch_all("SELECT name FROM categories ORDER BY name")]
        st.write(cats)
        with st.form("add_cat"):
            new_cat = st.text_input("New Category")
            if st.form_submit_button("Add Category"):
                execute("INSERT INTO categories (name) VALUES (?)", (new_cat,))
                st.success("Category added")
                st.rerun()

    with tab4:
        st.markdown("### Export Transactions")
        rows = fetch_all("SELECT txn_code, submit_date, submitter_name, submitter_amoeba, counterparty_amoeba, category, description, amount, currency, approver_name, status, approval_comment, approval_datetime FROM transactions ORDER BY id DESC")
        df = pd.DataFrame(rows, columns=["Transaction ID", "Submit Date", "Submitter", "From Amoeba", "To Amoeba", "Category", "Description", "Amount", "Currency", "Approver", "Status", "Approval Comment", "Approval Datetime"])
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Download CSV", data=csv, file_name="transactions_export.csv", mime="text/csv")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Transactions")
        st.download_button(
            "Download Excel",
            data=output.getvalue(),
            file_name="transactions_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
