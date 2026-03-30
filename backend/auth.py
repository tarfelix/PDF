import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

JWT_SECRET = "sp-pdf-editor-jwt-secret-2026"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 12

_security = HTTPBearer()

# Load users from JSON file
_users_path = Path(__file__).parent / "users.json"
with open(_users_path, encoding="utf-8") as f:
    USERS: dict[str, dict] = json.load(f)

logger.info("Loaded %d users", len(USERS))


def authenticate_user(email: str, password: str) -> dict | None:
    email = email.strip().lower()
    user = USERS.get(email)
    if not user:
        return None
    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return {"name": user["name"], "email": user["email"], "role": user["role"]}
    return None


def create_token(user: dict) -> str:
    payload = {
        "sub": user["email"],
        "name": user["name"],
        "role": user["role"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return {
            "email": payload["sub"],
            "name": payload["name"],
            "role": payload["role"],
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
