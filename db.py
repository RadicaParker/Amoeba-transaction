import streamlit as st
from sqlalchemy import text
from datetime import datetime


def get_conn():
    return st.connection("postgresql", type="sql")


def init_db():
    conn = get_conn()

    create_sql = """
    CREATE TABLE IF NOT EXISTS users (
        id BIGSERIAL PRIMARY KEY,
        email TEXT UNIQUE,
        name TEXT,
        password TEXT,
        role TEXT,
        amoeba TEXT,
        active BOOLEAN DEFAULT TRUE
    );

    CREATE TABLE IF NOT EXISTS amoebas (
        id BIGSERIAL PRIMARY KEY,
        name TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS categories (
        id BIGSERIAL PRIMARY KEY,
        name TEXT UNIQUE
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id BIGSERIAL PRIMARY KEY,
        txn_code TEXT UNIQUE,
        submit_date TIMESTAMP,
        submitter_email TEXT,
        submitter_name TEXT,
        submitter_amoeba TEXT,
        counterparty_amoeba TEXT,
        category TEXT,
        description TEXT,
        amount NUMERIC,
        currency TEXT,
        approver_email TEXT,
        approver_name TEXT,
        attachment_name TEXT,
        status TEXT,
        approval_comment TEXT,
        approval_datetime TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS approval_tokens (
        id BIGSERIAL PRIMARY KEY,
        token TEXT UNIQUE,
        txn_code TEXT,
        approver_email TEXT,
        action TEXT,
        expiry_datetime TIMESTAMP,
        used BOOLEAN DEFAULT FALSE,
        used_datetime TIMESTAMP
    );
    """

    with conn.session as s:
        for stmt in create_sql.split(";"):
            stmt = stmt.strip()
            if stmt:
                s.execute(text(stmt))
        s.commit()


def seed_data():
    conn = get_conn()

    with conn.session as s:
        amoeba_count = s.execute(text("SELECT COUNT(*) FROM amoebas")).scalar()
        if amoeba_count == 0:
            for a in ["Sales", "Marketing", "Product", "Finance", "Operations"]:
                s.execute(text("INSERT INTO amoebas (name) VALUES (:name)"), {"name": a})

        category_count = s.execute(text("SELECT COUNT(*) FROM categories")).scalar()
        if category_count == 0:
            for c in [
                "Internal Recharge",
                "Shared Cost",
                "Department Allocation",
                "Adjustment",
            ]:
                s.execute(text("INSERT INTO categories (name) VALUES (:name)"), {"name": c})

        user_count = s.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if user_count == 0:
            users = [
                {
                    "email": "radicafinace",
                    "name": "Radica Finance",
                    "password": "radica!23",
                    "role": "admin",
                    "amoeba": "Finance",
                    "active": True,
                },
                {
                    "email": "manager@radica.com",
                    "name": "Department Manager",
                    "password": "Admin123!",
                    "role": "approver",
                    "amoeba": "Operations",
                    "active": True,
                },
                {
                    "email": "staff@radica.com",
                    "name": "Staff User",
                    "password": "Admin123!",
                    "role": "submitter",
                    "amoeba": "Marketing",
                    "active": True,
                },
            ]
            for u in users:
                s.execute(
                    text("""
                        INSERT INTO users (email, name, password, role, amoeba, active)
                        VALUES (:email, :name, :password, :role, :amoeba, :active)
                    """),
                    u,
                )

        s.commit()


def fetch_all(query, params=None):
    if params is None:
        params = {}
    conn = get_conn()
    with conn.session as s:
        result = s.execute(text(query), params)
        return result.fetchall()


def fetch_one(query, params=None):
    if params is None:
        params = {}
    conn = get_conn()
    with conn.session as s:
        result = s.execute(text(query), params)
        return result.fetchone()


def execute(query, params=None):
    if params is None:
        params = {}
    conn = get_conn()
    with conn.session as s:
        s.execute(text(query), params)
        s.commit()


def next_txn_code():
    return "TXN-" + datetime.now().strftime("%Y%m%d%H%M%S")
