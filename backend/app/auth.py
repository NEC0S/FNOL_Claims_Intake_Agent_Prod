import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.database import supabase

logger = logging.getLogger("fnol.auth")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def get_user_by_email(email: str) -> Optional[dict]:
    res = supabase.table("app_users").select("*").eq("email", email).limit(1).execute()
    return res.data[0] if res.data else None


def authenticate_user(email: str, password: str) -> Optional[dict]:
    user = get_user_by_email(email)
    if not user or not user.get("is_active", True):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def ensure_bootstrap_admin() -> None:
    """Creates the first admin/manager account from env vars if the
    app_users table is empty."""
    res = supabase.table("app_users").select("id").limit(1).execute()
    if res.data:
        return
    supabase.table("app_users").insert({
        "email": settings.ADMIN_EMAIL,
        "password_hash": hash_password(settings.ADMIN_PASSWORD),
        "full_name": "Administrator",
        "role": "admin",
        "is_active": True,
    }).execute()
    logger.warning(
        "ensure_bootstrap_admin: created initial admin account %s -- "
        "log in and change the password immediately.", settings.ADMIN_EMAIL,
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_by_email(email)
    if user is None or not user.get("is_active", True):
        raise credentials_exception
    return user


def require_roles(*roles: str):
    async def _checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(roles)}",
            )
        return user
    return _checker


# Convenience dependencies
require_manager_or_admin = require_roles("manager", "admin")
require_any_role = require_roles("manager", "admin", "checker")
require_admin = require_roles("admin")
