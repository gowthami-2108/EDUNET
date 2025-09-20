# edunet_auth.py
import os
import hashlib
import pandas as pd

USER_DB = "users.csv"

def hash_password(password: str) -> str:
    """Return a SHA-256 hex digest of the password (simple hashing)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def load_users() -> pd.DataFrame:
    """Load users DB or create empty DataFrame."""
    if os.path.exists(USER_DB):
        df = pd.read_csv(USER_DB)
        # ensure columns
        if "email" not in df.columns or "password" not in df.columns:
            return pd.DataFrame(columns=["email", "password"])
        return df[["email", "password"]]
    else:
        return pd.DataFrame(columns=["email", "password"])

def save_users(df: pd.DataFrame):
    """Persist users DB."""
    df.to_csv(USER_DB, index=False)

def register_user(email: str, password: str) -> (bool, str):
    """Register new user. Returns (success, message)."""
    users = load_users()
    email = email.strip().lower()
    if email in users["email"].values:
        return False, "User already exists."
    hashed = hash_password(password)
    new = pd.DataFrame([[email, hashed]], columns=["email", "password"])
    users = pd.concat([users, new], ignore_index=True)
    save_users(users)
    return True, "Registered successfully."

def login_user(email: str, password: str) -> bool:
    """Validate user credentials."""
    users = load_users()
    email = email.strip().lower()
    hashed = hash_password(password)
    matched = users[(users["email"] == email) & (users["password"] == hashed)]
    return not matched.empty
