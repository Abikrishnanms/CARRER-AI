"""
auth/auth_utils.py

Helper functions for user signup and login, backed by Postgres.
"""

import bcrypt
from database.postgres_client import PostgresClient


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def signup_user(username: str, email: str, password: str, full_name: str = None, location: str = None):
    p = PostgresClient()
    try:
        existing = p.get_user_by_username(username)
        if existing:
            return {"success": False, "error": "Username already exists"}

        hashed = hash_password(password)
        user_id = p.create_user(username, email, hashed, full_name, location)
        return {"success": True, "user_id": user_id}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        p.close()


def login_user(username: str, password: str):
    p = PostgresClient()
    try:
        row = p.get_user_by_username(username)
        if not row:
            return {"success": False, "error": "User not found"}

        user_id, uname, email, hashed, full_name, location = row
        if not verify_password(password, hashed):
            return {"success": False, "error": "Incorrect password"}

        return {
            "success": True,
            "user": {
                "id": user_id,
                "username": uname,
                "email": email,
                "full_name": full_name,
                "location": location,
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        p.close()