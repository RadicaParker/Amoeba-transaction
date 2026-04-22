import psycopg2
from datetime import datetime
import streamlit as st


def get_conn():
    url = st.secrets["DATABASE_URL"]
    conn = psycopg2.connect(url, sslmode="require")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT,
            password TEXT,
            role TEXT,
            amoeba TEXT,
            active SMALLINT DEFAULT 1
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS amoebas (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            txn_code TEXT UNIQUE,
            submit_date TEXT,
            submitter_email TEXT,
            submitter_name TEXT,
            submitter_amoeba TEXT,
            counterparty_amoeba TEXT,
            category TEXT,
            description TEXT,
            amount FLOAT,
            currency TEXT,
            approver_email TEXT,
            approver_name TEXT,
            attachment_name TEXT,
            status TEXT,
            approval_comment TEXT,
            approval_datetime TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS approval_tokens (
            id SERIAL PRIMARY KEY,
            token TEXT UNIQUE,
            txn_code TEXT,
            approver_email TEXT,
            action TEXT,
            expiry_datetime TEXT,
            used INTEGER DEFAULT 0,
            used_datetime TEXT
        )
    """)

    conn.commit()
    cur.close()
    conn.close()


def seed_data():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM amoebas")
    if cur.fetchone()[0] == 0:
        for a in ["Sales", "Marketing", "Product", "Finance", "Operations"]:
            cur.execute("INSERT INTO amoebas (name) VALUES (%s)", (a,))

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        for c in [
            "Internal Recharge",
            "Shared Cost",
            "Department Allocation",
            "Adjustment",
        ]:
            cur.execute("INSERT INTO categories (name) VALUES (%s)", (c,))

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        users = [
            ("radicafinace", "Radica Finance", "radica!23", "admin", "Finance"),
            ("manager@radica.com", "Department Manager", "Admin123!", "approver", "Operations"),
            ("staff@radica.com", "Staff User", "Admin123!", "submitter", "Marketing"),
        ]
        for u in users:
            cur.execute(
                "INSERT INTO users (email, name, password, role, amoeba, active) VALUES (%s, %s, %s, %s, %s, 1)",
                u,
            )

    conn.commit()
    cur.close()
    conn.close()


def fetch_all(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_one(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row


def execute(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    cur.close()
    conn.close()


def next_txn_code():
    return "TXN-" + datetime.now().strftime("%Y%m%d%H%M%S")
