import io
from datetime import datetime
import pandas as pd
import streamlit as st
from db import fetch_all, fetch_one, execute, next_txn_code

CURRENCIES = ["HKD", "CNY", "USD"]


def submit_transaction_page(user):
    st.subheader("Submit Transaction")

    amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
    categories = [r[0] for r in fetch_all("SELECT name FROM categories ORDER BY name")]
    approvers = fetch_all(
        "SELECT email, name FROM users WHERE role IN ('approver', 'admin') AND active = 1 ORDER BY name"
    )

    approver_map = {}
    for email, name in approvers:
        if email != user["email"]:
            approver_map[name + " (" + email + ")"] = (email, name)

    with st.form("txn_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            counterparty_amoeba = st.selectbox("Counterparty Amoeba / Department", amoebas)
            category = st.selectbox("Category", categories)
            currency = st.selectbox("Currency", CURRENCIES)
            amount = st.number_input("Amount", min_value=0.0, step=0.01)

        with col2:
            approver_label = st.selectbox("Approver", list(approver_map.keys()))
            description = st.text_area("Description / Remarks")
            attachment = st.file_uploader("Attachment")

        submitted = st.form_submit_button("Submit")

    if submitted:
        approver_email, approver_name = approver_map[approver_label]
        attachment_name = ""
        if attachment is not None:
            attachment_name = attachment.name

        execute(
            """
            INSERT INTO transactions (
                txn_code, submit_date, submitter_email, submitter_name, submitter_amoeba,
                counterparty_amoeba, category, description, amount, currency,
                approver_email, approver_name, attachment_name, status, approval_comment, approval_datetime
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                next_txn_code(),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user["email"],
                user["name"],
                user["amoeba"],
                counterparty_amoeba,
                category,
                description,
                amount,
                currency,
                approver_email,
                approver_name,
                attachment_name,
                "Pending Approval",
                "",
                "",
            ),
        )
        st.success("Transaction submitted successfully.")


def my_transactions_page(user):
    st.subheader("My Transactions")

    rows = fetch_all(
        """
        SELECT txn_code, submit_date, submitter_amoeba, counterparty_amoeba, category,
               amount, currency, approver_name, status, approval_comment, approval_datetime
        FROM transactions
        WHERE submitter_email = ?
        ORDER BY id DESC
        """,
        (user["email"],),
    )

    df = pd.DataFrame(
        rows,
        columns=[
            "Transaction ID",
            "Submit Date",
            "From Amoeba",
            "To Amoeba",
            "Category",
            "Amount",
            "Currency",
            "Approver",
            "Status",
            "Approval Comment",
            "Approval Datetime",
        ],
    )
    st.dataframe(df, use_container_width=True)


def approval_queue_page(user):
    st.subheader("Approval Queue")

    rows = fetch_all(
        """
        SELECT id, txn_code, submit_date, submitter_name, submitter_amoeba,
               counterparty_amoeba, category, amount, currency, description, status
        FROM transactions
        WHERE approver_email = ? AND status = 'Pending Approval'
        ORDER BY id DESC
        """,
        (user["email"],),
    )

    if not rows:
        st.info("No pending approvals.")
        return

    for r in rows:
        txn_id = r[0]
        txn_code = r[1]
        submit_date = r[2]
        submitter_name = r[3]
        from_amoeba = r[4]
        to_amoeba = r[5]
        category = r[6]
        amount = r[7]
        currency = r[8]
        description = r[9]

        with st.expander(txn_code + " | " + submitter_name + " | " + str(amount) + " " + currency):
            st.write("Submit Date: " + submit_date)
            st.write("From: " + from_amoeba)
            st.write("To: " + to_amoeba)
            st.write("Category: " + category)
            st.write("Description: " + description)

            comment = st.text_input("Comment", key="comment_" + str(txn_id))
            col1, col2 = st.columns(2)

            with col1:
                if st.button("Approve " + txn_code, key="approve_" + str(txn_id)):
                    execute(
                        "UPDATE transactions SET status = ?, approval_comment = ?, approval_datetime = ? WHERE id = ?",
                        ("Approved", comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), txn_id),
                    )
                    st.success(txn_code + " approved")
                    st.rerun()

            with col2:
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

        users = fetch_all(
            "SELECT id, email, name, role, amoeba, active FROM users ORDER BY name"
        )
        users_df = pd.DataFrame(users, columns=["ID", "Email", "Name", "Role", "Amoeba", "Active"])
        st.dataframe(users_df, use_container_width=True)

        st.markdown("#### Add User")
        amoebas = [r[0] for r in fetch_all("SELECT name FROM amoebas ORDER BY name")]
        with st.form("add_user_form"):
            new_email = st.text_input("Email / Login ID")
            new_name = st.text_input("Name")
            new_password = st.text_input("Password")
            new_role = st.selectbox("Role", ["submitter", "approver", "admin"])
            new_amoeba = st.selectbox("Amoeba", amoebas, key="new_user_amoeba")
            add_user = st.form_submit_button("Add User")

        if add_user:
            execute(
                "INSERT INTO users (email, name, password, role, amoeba, active) VALUES (?, ?, ?, ?, ?, 1)",
                (new_email, new_name, new_password, new_role, new_amoeba),
            )
            st.success("User added.")
            st.rerun()

        st.markdown("#### Edit / Deactivate User")
        user_options = {str(u[0]) + " - " + u[2] + " (" + u[1] + ")": u[0] for u in users}
        if user_options:
            selected_user_label = st.selectbox("Select user", list(user_options.keys()))
            selected_user_id = user_options[selected_user_label]
            selected_user = fetch_one(
                "SELECT id, email, name, password, role, amoeba, active FROM users WHERE id = ?",
                (selected_user_id,),
            )

            with st.form("edit_user_form"):
                edit_email = st.text_input("Edit Email", value=selected_user[1])
                edit_name = st.text_input("Edit Name", value=selected_user[2])
                edit_password = st.text_input("Edit Password", value=selected_user[3])
                edit_role = st.selectbox(
                    "Edit Role",
                    ["submitter", "approver", "admin"],
                    index=["submitter", "approver", "admin"].index(selected_user[4]),
                )
                edit_amoeba = st.selectbox(
                    "Edit Amoeba",
                    amoebas,
                    index=amoebas.index(selected_user[5]) if selected_user[5] in amoebas else 0,
                )
                edit_active = st.selectbox(
                    "Active",
                    [1, 0],
                    index=0 if selected_user[6] == 1 else 1,
                    format_func=lambda x: "Yes" if x == 1 else "No",
                )

                col1, col2 = st.columns(2)
                with col1:
                    save_user = st.form_submit_button("Save User Changes")
                with col2:
                    deactivate_user = st.form_submit_button("Deactivate User")

            if save_user:
                execute(
                    """
                    UPDATE users
                    SET email = ?, name = ?, password = ?, role = ?, amoeba = ?, active = ?
                    WHERE id = ?
                    """,
                    (edit_email, edit_name, edit_password, edit_role, edit_amoeba, edit_active, selected_user_id),
                )
                st.success("User updated.")
                st.rerun()

            if deactivate_user:
                execute("UPDATE users SET active = 0 WHERE id = ?", (selected_user_id,))
                st.warning("User deactivated.")
                st.rerun()

    with tab2:
        st.markdown("### Amoeba Management")

        amoeba_rows = fetch_all("SELECT id, name FROM amoebas ORDER BY name")
        amoeba_df = pd.DataFrame(amoeba_rows, columns=["ID", "Amoeba"])
        st.dataframe(amoeba_df, use_container_width=True)

        st.markdown("#### Add Amoeba")
        with st.form("add_amoeba_form"):
            new_amoeba_name = st.text_input("New Amoeba Name")
            add_amoeba = st.form_submit_button("Add Amoeba")
        if add_amoeba:
            execute("INSERT INTO amoebas (name) VALUES (?)", (new_amoeba_name,))
            st.success("Amoeba added.")
            st.rerun()

        st.markdown("#### Edit / Delete Amoeba")
        amoeba_options = {str(a[0]) + " - " + a[1]: a[0] for a in amoeba_rows}
        if amoeba_options:
            selected_amoeba_label = st.selectbox("Select amoeba", list(amoeba_options.keys()))
            selected_amoeba_id = amoeba_options[selected_amoeba_label]
            selected_amoeba = fetch_one("SELECT id, name FROM amoebas WHERE id = ?", (selected_amoeba_id,))

            with st.form("edit_amoeba_form"):
                edit_amoeba_name = st.text_input("Edit Amoeba Name", value=selected_amoeba[1])
                col1, col2 = st.columns(2)
                with col1:
                    save_amoeba = st.form_submit_button("Save Amoeba")
                with col2:
                    delete_amoeba = st.form_submit_button("Delete Amoeba")

            if save_amoeba:
                execute("UPDATE amoebas SET name = ? WHERE id = ?", (edit_amoeba_name, selected_amoeba_id))
                st.success("Amoeba updated.")
                st.rerun()

            if delete_amoeba:
                used_count = fetch_one(
                    """
                    SELECT COUNT(*) FROM transactions
                    WHERE submitter_amoeba = ? OR counterparty_amoeba = ?
                    """,
                    (selected_amoeba[1], selected_amoeba[1]),
                )[0]
                if used_count > 0:
                    st.error("Cannot delete. This amoeba is already used in transactions.")
                else:
                    execute("DELETE FROM amoebas WHERE id = ?", (selected_amoeba_id,))
                    st.warning("Amoeba deleted.")
                    st.rerun()

    with tab3:
        st.markdown("### Category Management")

        category_rows = fetch_all("SELECT id, name FROM categories ORDER BY name")
        category_df = pd.DataFrame(category_rows, columns=["ID", "Category"])
        st.dataframe(category_df, use_container_width=True)

        st.markdown("#### Add Category")
        with st.form("add_category_form"):
            new_category_name = st.text_input("New Category Name")
            add_category = st.form_submit_button("Add Category")
        if add_category:
            execute("INSERT INTO categories (name) VALUES (?)", (new_category_name,))
            st.success("Category added.")
            st.rerun()

        st.markdown("#### Edit / Delete Category")
        category_options = {str(c[0]) + " - " + c[1]: c[0] for c in category_rows}
        if category_options:
            selected_category_label = st.selectbox("Select category", list(category_options.keys()))
            selected_category_id = category_options[selected_category_label]
            selected_category = fetch_one(
                "SELECT id, name FROM categories WHERE id = ?",
                (selected_category_id,),
            )

            with st.form("edit_category_form"):
                edit_category_name = st.text_input("Edit Category Name", value=selected_category[1])
                col1, col2 = st.columns(2)
                with col1:
                    save_category = st.form_submit_button("Save Category")
                with col2:
                    delete_category = st.form_submit_button("Delete Category")

            if save_category:
                execute(
                    "UPDATE categories SET name = ? WHERE id = ?",
                    (edit_category_name, selected_category_id),
                )
                st.success("Category updated.")
                st.rerun()

            if delete_category:
                used_count = fetch_one(
                    "SELECT COUNT(*) FROM transactions WHERE category = ?",
                    (selected_category[1],),
                )[0]
                if used_count > 0:
                    st.error("Cannot delete. This category is already used in transactions.")
                else:
                    execute("DELETE FROM categories WHERE id = ?", (selected_category_id,))
                    st.warning("Category deleted.")
                    st.rerun()

    with tab4:
        st.markdown("### Export Transactions")

        rows = fetch_all(
            """
            SELECT txn_code, submit_date, submitter_name, submitter_amoeba, counterparty_amoeba,
                   category, description, amount, currency, approver_name, status,
                   approval_comment, approval_datetime
            FROM transactions
            ORDER BY id DESC
            """
        )

        df = pd.DataFrame(
            rows,
            columns=[
                "Transaction ID",
                "Submit Date",
                "Submitter",
                "From Amoeba",
                "To Amoeba",
                "Category",
                "Description",
                "Amount",
                "Currency",
                "Approver",
                "Status",
                "Approval Comment",
                "Approval Datetime",
            ],
        )

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
