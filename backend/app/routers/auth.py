import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import (
    authenticate_user, create_access_token, get_current_user, hash_password,
    verify_password, require_admin, get_user_by_email,
)
from app.database import supabase
from app.models import (
    LoginRequest, TokenResponse, UserCreateRequest, UserOut, ChangePasswordRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger("fnol.routers.auth")


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token({"sub": user["email"], "role": user["role"]})
    return TokenResponse(access_token=token, role=user["role"], email=user["email"], full_name=user.get("full_name"))


@router.post("/login-json", response_model=TokenResponse)
def login_json(body: LoginRequest):
    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token({"sub": user["email"], "role": user["role"]})
    return TokenResponse(access_token=token, role=user["role"], email=user["email"], full_name=user.get("full_name"))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(get_current_user)):
    return UserOut(id=user["id"], email=user["email"], full_name=user.get("full_name"), role=user["role"], is_active=user.get("is_active", True))


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    if not verify_password(body.old_password, user["password_hash"]):
        raise HTTPException(status_code=400, detail="Old password is incorrect")
    supabase.table("app_users").update({"password_hash": hash_password(body.new_password)}).eq("id", user["id"]).execute()
    return {"ok": True}


# ---- User management (admin only) -----------------------------------------
@router.get("/users", response_model=list[UserOut])
def list_users(_: dict = Depends(require_admin)):
    res = supabase.table("app_users").select("id,email,full_name,role,is_active").order("created_at").execute()
    return res.data


@router.post("/users", response_model=UserOut)
def create_user(body: UserCreateRequest, _: dict = Depends(require_admin)):
    if get_user_by_email(body.email):
        raise HTTPException(status_code=400, detail="A user with that email already exists")
    row = supabase.table("app_users").insert({
        "email": body.email,
        "password_hash": hash_password(body.password),
        "full_name": body.full_name,
        "role": body.role,
        "is_active": True,
    }).execute().data[0]
    return UserOut(id=row["id"], email=row["email"], full_name=row.get("full_name"), role=row["role"], is_active=row.get("is_active", True))


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(user_id: str, _: dict = Depends(require_admin)):
    supabase.table("app_users").update({"is_active": False}).eq("id", user_id).execute()
    return {"ok": True}


@router.patch("/users/{user_id}/activate")
def activate_user(user_id: str, _: dict = Depends(require_admin)):
    supabase.table("app_users").update({"is_active": True}).eq("id", user_id).execute()
    return {"ok": True}


@router.patch("/users/{user_id}/role")
def change_role(user_id: str, role: str, _: dict = Depends(require_admin)):
    if role not in ("admin", "manager", "checker"):
        raise HTTPException(status_code=400, detail="Invalid role")
    supabase.table("app_users").update({"role": role}).eq("id", user_id).execute()
    return {"ok": True}
