# Radica Amoeba Internal Transaction V2

This version adds:
- Gmail SMTP email alert after submission
- Approve and Reject links in email
- 7-day approval link expiry
- Token-based approval update from email click

## Required Streamlit secrets
```toml
GMAIL_SENDER = "financeradica81@gmail.com"
GMAIL_APP_PASSWORD = "your_app_password_without_spaces"
APP_BASE_URL = "https://amoeba-transaction-d4zywffc4tufcr7aovr8ev.streamlit.app/"
```
