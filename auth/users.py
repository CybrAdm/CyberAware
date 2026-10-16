import json
import re
import secrets
from datetime import datetime
from pathlib import Path

import streamlit as st
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from analytics.data_files import DATA_DIR


password_hasher = PasswordHasher()


def hash_password(password):
    return password_hasher.hash(password)


def verify_password(password, password_hash):
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


_ACTIVE = {}


def _query_token():
    value = st.query_params.get("session")
    if isinstance(value, list):
        value = value[0] if value else ""
    if not isinstance(value, str):
        return ""
    return value.strip()


def login_session(user):
    token = secrets.token_urlsafe(16)
    _ACTIVE[token] = user
    st.session_state["authenticated"] = True
    st.session_state["user"] = user
    st.session_state["session_token"] = token
    st.query_params["session"] = token


def logout_session():
    _ACTIVE.pop(st.session_state.get("session_token") or _query_token(), None)
    st.session_state["authenticated"] = False
    st.session_state["user"] = None
    st.session_state["session_token"] = None
    if "session" in st.query_params:
        del st.query_params["session"]


def restore_session():
    if st.session_state.get("authenticated") and st.session_state.get("user"):
        return
    token = _query_token()
    user = _ACTIVE.get(token)
    if not user:
        if token:
            del st.query_params["session"]
        return
    st.session_state["authenticated"] = True
    st.session_state["user"] = user
    st.session_state["session_token"] = token


def is_authenticated():
    return st.session_state.get("authenticated", False)


def get_current_user():
    return st.session_state.get("user")


def get_current_role():
    user = get_current_user()
    if user:
        return user.get("role")
    return None


def is_admin():
    return get_current_role() == "admin"


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")
ROLES = ("user", "admin")
DEMO_ADMIN_EMAIL = "admin@cyberaware.local"
DEMO_ADMIN_PASSWORD = "Admin@12345"


def users_path(path=None):
    if path is None:
        return DATA_DIR / "users.json"
    return Path(path)


def load_users(path=None):
    target = users_path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return data


def save_users(users, path=None):
    target = users_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(users, indent=2), encoding="utf-8")
    temporary.replace(target)


def _next_id(users):
    highest = 0
    for user in users:
        user_id = str(user.get("user_id", ""))
        if user_id.startswith("USR-") and user_id[4:].isdigit():
            highest = max(highest, int(user_id[4:]))
    return "USR-" + str(highest + 1).zfill(4)


def public_user(user):
    return {key: value for key, value in user.items() if key != "password_hash"}


def register_user(username, email, password, path=None):
    username = username.strip()
    email = email.strip().lower()

    if USERNAME_PATTERN.fullmatch(username) is None:
        raise ValueError(
            "Username must be 3 to 20 letters, numbers, or underscores."
        )
    if EMAIL_PATTERN.fullmatch(email) is None:
        raise ValueError("Enter a valid email address.")
    if not isinstance(password, str) or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    users = load_users(path)
    for user in users:
        if user.get("email", "").lower() == email:
            raise ValueError("An account with this email already exists.")
        if user.get("username", "").lower() == username.lower():
            raise ValueError("An account with this username already exists.")

    record = {
        "user_id": _next_id(users),
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "role": "user",
        "is_active": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    users.append(record)
    save_users(users, path)
    return public_user(record)


def login_user(email, password, path=None):
    if not isinstance(email, str) or not isinstance(password, str):
        return None

    email = email.strip().lower()
    for user in load_users(path):
        if user.get("email", "").lower() != email:
            continue
        if not user.get("is_active", True):
            return None
        if user.get("role") not in ROLES:
            return None
        if verify_password(password, user.get("password_hash", "")):
            return public_user(user)
        return None
    return None


def seed_admin(path=None):
    users = load_users(path)
    if users:
        return None

    record = {
        "user_id": "USR-0001",
        "username": "admin",
        "email": DEMO_ADMIN_EMAIL,
        "password_hash": hash_password(DEMO_ADMIN_PASSWORD),
        "role": "admin",
        "is_active": True,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_users([record], path)
    return public_user(record)


def require_login():
    if not is_authenticated():
        st.warning("Log in to open this page.")
        st.stop()


def require_admin():
    require_login()
    if not is_admin():
        st.error("This page is only available to an admin.")
        st.stop()
