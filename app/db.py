import os
import sqlite3
from datetime import datetime

DB_PATH = "output/radica_amoeba_internal_transaction/data/app.db"


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            name TEXT,
            password TEXT,
            role TEXT,
            amoeba TEXT,
            active INTEGER DEFAULT 1
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS amoebas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_code TEXT UNIQUE,
            submit_date TEXT,
            submitter_email TEXT,
            submitter_name TEXT,
            submitter_amoeba TEXT,
            counterparty_amoeba TEXT,
            category TEXT,
            description TEXT,
            amount REAL,
            currency TEXT,
            approver_email TEXT,
            approver_name TEXT,
            attachment_name TEXT,
            status TEXT,
            approval_comment TEXT,
            approval_datetime TEXT
        )
    ''')

    conn.commit()
    conn.close()


def seed_data():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM amoebas")
    if cur.fetchone()[0] == 0:
        for a in ["Sales", "Marketing", "Product", "Finance", "Operations"]:
            cur.execute("INSERT INTO amoebas (name) VALUES (?)", (a,))

    cur.execute("SELECT COUNT(*) FROM categories")
    if cur.fetchone()[0] == 0:
        for c in ["Internal Recharge", "Shared Cost", "Department Allocation", "Adjustment"]:
            cur.execute("INSERT INTO categories (name) VALUES (?)", (c,))

    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        users = [
            ("radicafinace", "Radica Finance", "radica!23", "admin", "Finance", 1),
            ("manager@radica.com", "Department Manager", "Admin123!", "approver", "Operations", 1),
            ("staff@radica.com", "Staff User", "Admin123!", "submitter", "Marketing", 1),
        ]
        cur.executemany(
            "INSERT INTO users (email, name, password, role, amoeba, active) VALUES (?, ?, ?, ?, ?, ?)",
            users,
        )

    conn.commit()
    conn.close()


def fetch_all(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def execute(query, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()


def next_txn_code():
    return f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
