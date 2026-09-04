import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import require_manager_or_admin, require_any_role
from app.database import supabase
from app.models import PolicyUpsertRequest, CustomerUpsertRequest

router = APIRouter(prefix="/api/policies", tags=["policies"])
logger = logging.getLogger("fnol.routers.policies")


@router.get("")
def list_policies(search: Optional[str] = Query(None), limit: int = 100, offset: int = 0, _: dict = Depends(require_any_role)):
    q = supabase.table("policies").select("*", count="exact")
    if search:
        q = q.or_(f"policy_number.ilike.%{search}%,holder_name.ilike.%{search}%,holder_email.ilike.%{search}%")
    q = q.order("policy_number").range(offset, offset + limit - 1)
    res = q.execute()
    return {"policies": res.data, "total": res.count}


@router.get("/{policy_number}")
def get_policy(policy_number: str, _: dict = Depends(require_any_role)):
    res = supabase.table("policies").select("*").eq("policy_number", policy_number).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Policy not found")
    return res.data[0]


@router.put("")
def upsert_policy(body: PolicyUpsertRequest, _: dict = Depends(require_manager_or_admin)):
    if body.holder_email:
        supabase.table("customers").upsert(
            {"email": body.holder_email, "name": body.holder_name}, on_conflict="email"
        ).execute()
    supabase.table("policies").upsert(body.model_dump(), on_conflict="policy_number").execute()
    return {"ok": True}


@router.delete("/{policy_number}")
def delete_policy(policy_number: str, _: dict = Depends(require_manager_or_admin)):
    supabase.table("policies").delete().eq("policy_number", policy_number).execute()
    return {"ok": True}


customers_router = APIRouter(prefix="/api/customers", tags=["customers"])


@customers_router.get("")
def list_customers(search: Optional[str] = Query(None), limit: int = 100, offset: int = 0, _: dict = Depends(require_any_role)):
    q = supabase.table("customers").select("*", count="exact")
    if search:
        q = q.or_(f"email.ilike.%{search}%,name.ilike.%{search}%")
    q = q.order("email").range(offset, offset + limit - 1)
    res = q.execute()
    return {"customers": res.data, "total": res.count}


@customers_router.put("")
def upsert_customer(body: CustomerUpsertRequest, _: dict = Depends(require_manager_or_admin)):
    supabase.table("customers").upsert(body.model_dump(), on_conflict="email").execute()
    return {"ok": True}
