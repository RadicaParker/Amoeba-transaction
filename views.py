import io
import uuid
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_one, execute, next_txn_code

CURRENCIES = ["HKD", "CNY", "USD"]


def send_approval_email(txn_code, approver_email, approver_name, submitter_name, amount, currency, category, description):
    sender = st.secrets["GMAIL_SENDER"]
    password = st.secrets["GMAIL_APP_PASSWORD"]
    base_url = st.secrets["APP_BASE_URL"].rstrip("/")

    approve_token = str(uuid.uuid4())
    reject_token = str(uuid.uuid4())
    expiry = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    execute(
        "INSERT INTO approval_tokens (txn_code, approver_email, action, token, expiry_datetime, used, used_datetime) VALUES (?, ?, ?, ?, ?, 0, '')",
        (txn_code, approver_email, "approve", approve_token, expiry),
    )
    execute(
        "INSERT INTO approval_tokens (txn_code, approver_email, action, token, expiry_datetime, used, used_datetime) VALUES (?, ?, ?, ?, ?, 0, '')",
        (txn_code, approver_email, "reject", reject_token, expiry),
    )

    approve_link = base_url + "?token=" + approve_token
    reject_link = base_url + "?token=" + reject_token

    subject = "Approval Needed: " + txn_code
    body = f"""
    <p>Dear {approver_name},</p>
    <p>A new transaction is waiting for your approval.</p>
    <ul>
      <li><b>Transaction ID:</b> {txn_code}</li>
      <li><b>Submitter:</b> {submitter_name}</li>
      <li><b>Amount:</b> {amount:.2f} {currency}</li>
      <li><b>Category:</b> {category}</li>
      <li><b>Description:</b> {description}</li>
      <li><b>Link Expiry:</b> {expiry}</li>
    </ul>
    <p><a href=\"{approve_link}\">Approve</a></p>
    <p><a href=\"{reject_link}\">Reject</a></p>
    <p>Regards,<br>Radica Amoeba Internal Transaction</p>
    """

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = approver_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender, password)
    server.sendmail(sender, approver_email, msg.as_string())
    server.quit()


def process_email_action():
    query_params = st.query_params
    token = query_params.get("token")
    if not token:
        return

    token_row = fetch_one(
        "SELECT txn_code, approver_email, action, expiry_datetime, used FROM approval_tokens WHERE token = ?",
        (token,),
    )

    if not token_row:
        st.error("Invalid approval link.")
        return

    txn_code, approver_email, action, expiry_datetime, used = token_row

    if used == 1:
        st.warning("This approval link has already been used.")
        return

    if datetime.now() > datetime.strptime(expiry_datetime, "%Y-%m-%d %H:%M:%S"):
        st.error("This approval link has expired.")
        return

    txn = fetch_one("SELECT status FROM transactions WHERE txn_code = ?", (txn_code,))
    if not txn:
        st.error("Transaction not found.")
        return

    if txn[0] != "Pending Approval":
        st.info("This transaction has already been processed.")
        return

    new_status = "Approved" if action == "approve" else "Rejected"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    execute(
        "UPDATE transactions SET status = ?, approval_comment = ?, approval_datetime = ? WHERE txn_code = ?",
        ("Approved" if action == "approve" else "Rejected", "Action from email link", now_str, txn_code),
    )
    execute(
        "UPDATE approval_tokens SET used = 1, used_datetime = ? WHERE token = ?",
        (now_str, token),
    )

    st.success("Transaction " + txn_code + " has been " + new_status + " via email link.")
    st.query_params.clear()


def submit_transaction_page(user):
    st.subheader("Submit Transaction")
    amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
    categories = [r[0] for r in fetch_all("SELECT name FROM categories ORDER BY name")]
    approvers = fetch_all("SELECT email, name FROM users WHERE role IN ('approver','admin') AND active = 1 ORDER BY name")
    approver_map = {name + " (" + email + ")": (email, name) for email, name in approvers if email != user["email"]}

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
            attachment = st.file_uploader("Attachment")

        submitted = st.form_submit_button("Submit")

    if submitted:
        approver_email, approver_name = approver_map[approver_label]
        attachment_name = attachment.name if attachment else ""
        txn_code = next_txn_code()
        execute(
            '''INSERT INTO transactions (
                txn_code, submit_date, submitter_email, submitter_name, submitter_amoeba,
                counterparty_amoeba, category, description, amount, currency,
                approver_email, approver_name, attachment_name, status, approval_comment, approval_datetime
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                txn_code, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["email"], user["name"], user["amoeba"],
                counterparty_amoeba, category, description, amount, currency,
                approver_email, approver_name, attachment_name, "Pending Approval", "", ""
            )
        )
        try:
            send_approval_email(txn_code, approver_email, approver_name, user["name"], amount, currency, category, description)
            st.success("Transaction submitted and approval email sent.")
        except Exception as e:
            st.warning("Transaction submitted, but email sending failed: " + str(e))


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
        with st.expander(txn_code + " | " + submitter_name + " | " + str(amount) + " " + currency):
            st.write("Submit Date: " + submit_date)
            st.write("From: " + from_amoeba)
            st.write("To: " + to_amoeba)
            st.write("Category: " + category)
            st.write("Description: " + description)
            comment = st.text_input("Comment for " + txn_code, key="comment_" + str(txn_id))
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Approve " + txn_code, key="approve_" + str(txn_id)):
                    execute(
                        "UPDATE transactions SET status = ?, approval_comment = ?, approval_datetime = ? WHERE id = ?",
                        ("Approved", comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txn_id),
                    )
                    st.success(txn_code + " approved")
                    st.rerun()
            with c2:
                if st.button("Reject " + txn_code, key="reject_" + str(txn_id)):
                    execute(
                        "UPDATE transactions SET status = ?, approval_comment = ?, approval_datetime = ? WHERE id = ?",
                        ("Rejected", comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txn_id),
                    )
                    st.warning(txn_code + " rejected")
                    st.rerun()


def admin_portal_page():
    st.subheader("Admin Portal")
    tab1, tab2, tab3, tab4 = st.tabs(["Users", "Amoebas", "Categories", "Export"])

    with tab1:
        st.markdown("### User Management")
        users = fetch_all("SELECT id, email, name, role, amoeba, active FROM users ORDER BY name")
        st.dataframe(pd.DataFrame(users, columns=["ID", "Email", "Name", "Role", "Amoeba", "Active"]), use_container_width=True)

    with tab2:
        st.markdown("### Amoeba Management")
        amoeba_rows = fetch_all("SELECT id, name FROM amoebas ORDER BY name")
        st.dataframe(pd.DataFrame(amoeba_rows, columns=["ID", "Amoeba"]), use_container_width=True)

    with tab3:
        st.markdown("### Category Management")
        category_rows = fetch_all("SELECT id, name FROM categories ORDER BY name")
        st.dataframe(pd.DataFrame(category_rows, columns=["ID", "Category"]), use_container_width=True)

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
        st.download_button("Download Excel", data=output.getvalue(), file_name="transactions_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
