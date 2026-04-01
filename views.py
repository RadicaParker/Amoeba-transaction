import io
import smtplib
import secrets
import uuid
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import streamlit as st

from db import fetch_all, fetch_one, execute, next_txn_code

CURRENCIES = ["HKD", "CNY", "USD"]


# ─────────────────────────────────────────────
# EMAIL HELPERS
# ─────────────────────────────────────────────

def get_secrets():
    try:
        sender = st.secrets["GMAIL_SENDER"]
        password = st.secrets["GMAIL_APP_PASSWORD"]
        base_url = st.secrets["APP_BASE_URL"]
        return sender, password, base_url
    except Exception:
        return None, None, None


def send_approval_email(txn_code, submitter_name, submitter_amoeba,
                        counterparty_amoeba, category, amount, currency,
                        description, approver_email, approver_name):
    sender, password, base_url = get_secrets()
    if not sender:
        st.warning("Email secrets not configured. Email not sent.")
        return

    approve_token = str(uuid.uuid4())
    reject_token = str(uuid.uuid4())
    expiry = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    execute(
        """INSERT INTO approval_tokens
           (token, txn_code, approver_email, action, expiry_datetime, used)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (approve_token, txn_code, approver_email, "approve", expiry),
    )
    execute(
        """INSERT INTO approval_tokens
           (token, txn_code, approver_email, action, expiry_datetime, used)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (reject_token, txn_code, approver_email, "reject", expiry),
    )

    base_url = base_url.rstrip("/")
    approve_link = base_url + "/?token=" + approve_token
    reject_link = base_url + "/?token=" + reject_token

    subject = "Approval Required: " + txn_code

    body = """
    <html><body>
    <p>Dear """ + approver_name + """,</p>
    <p>A new internal transaction requires your approval.</p>
    <table border="1" cellpadding="6" cellspacing="0">
        <tr><td><b>Transaction ID</b></td><td>""" + txn_code + """</td></tr>
        <tr><td><b>Submitted By</b></td><td>""" + submitter_name + """</td></tr>
        <tr><td><b>From Amoeba</b></td><td>""" + submitter_amoeba + """</td></tr>
        <tr><td><b>To Amoeba</b></td><td>""" + counterparty_amoeba + """</td></tr>
        <tr><td><b>Category</b></td><td>""" + category + """</td></tr>
        <tr><td><b>Amount</b></td><td>""" + currency + " " + str(amount) + """</td></tr>
        <tr><td><b>Description</b></td><td>""" + description + """</td></tr>
    </table>
    <br>
    <p>
        <a href='""" + approve_link + """'
           style='background:#28a745;color:white;padding:10px 20px;
                  text-decoration:none;border-radius:5px;margin-right:10px;'>
           ✅ APPROVE
        </a>
        &nbsp;&nbsp;
        <a href='""" + reject_link + """'
           style='background:#dc3545;color:white;padding:10px 20px;
                  text-decoration:none;border-radius:5px;'>
           ❌ REJECT
        </a>
    </p>
    <p><small>These links expire in 7 days.</small></p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = approver_email
    msg.attach(MIMEText(body, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, approver_email, msg.as_string())
        st.success("Approval email sent to " + approver_name + " (" + approver_email + ")")
    except Exception as e:
        st.error("Email sending failed: " + str(e))


# ─────────────────────────────────────────────
# EMAIL LINK ACTION HANDLER
# ─────────────────────────────────────────────

def process_email_action():
    try:
        token = st.query_params.get("token")
    except Exception:
        return

    if not token:
        return

    if isinstance(token, list):
        token = token[0]

    token_row = fetch_one(
        """SELECT txn_code, approver_email, action, expiry_datetime, used
           FROM approval_tokens WHERE token = ?""",
        (token,),
    )

    if not token_row:
        st.error("Invalid approval link.")
        st.stop()

    txn_code, approver_email, action, expiry_datetime, used = token_row

    if used == 1:
        st.warning("This approval link has already been used.")
        st.stop()

    if datetime.now() > datetime.strptime(expiry_datetime, "%Y-%m-%d %H:%M:%S"):
        st.error("This approval link has expired.")
        st.stop()

    txn = fetch_one(
        "SELECT status FROM transactions WHERE txn_code = ?", (txn_code,)
    )
    if not txn:
        st.error("Transaction not found.")
        st.stop()

    if txn[0] != "Pending Approval":
        st.info("Transaction " + txn_code + " has already been processed.")
        st.stop()

    new_status = "Approved" if action == "approve" else "Rejected"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    execute(
        """UPDATE transactions
           SET status = ?, approval_comment = ?, approval_datetime = ?
           WHERE txn_code = ?""",
        (new_status, "Action taken via email link", now_str, txn_code),
    )
    execute(
        "UPDATE approval_tokens SET used = 1, used_datetime = ? WHERE token = ?",
        (now_str, token),
    )

    if new_status == "Approved":
        st.success("Transaction " + txn_code + " has been APPROVED.")
    else:
        st.warning("Transaction " + txn_code + " has been REJECTED.")

    st.query_params.clear()
    st.stop()


# ─────────────────────────────────────────────
# SUBMIT TRANSACTION
# ─────────────────────────────────────────────

def submit_transaction_page(user):
    st.subheader("Submit Transaction")

    amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
    categories = [r[0] for r in fetch_all("SELECT name FROM categories ORDER BY name")]
    approvers = fetch_all(
        """SELECT email, name FROM users
           WHERE role IN ('approver','admin') AND active = 1
           ORDER BY name"""
    )

    approver_map = {}
    for email, name in approvers:
        if email != user["email"]:
            approver_map[name + " (" + email + ")"] = (email, name)

    if not approver_map:
        st.warning("No approvers available.")
        return

    with st.form("txn_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            counterparty_amoeba = st.selectbox("Counterparty Amoeba / Department", amoebas)
            category = st.selectbox("Category", categories)
            currency = st.selectbox("Currency", CURRENCIES)
            amount = st.number_input("Amount", min_value=0.
