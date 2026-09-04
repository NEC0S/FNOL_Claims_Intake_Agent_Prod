from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---- Auth -------------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    email: str
    full_name: Optional[str] = None


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: str = Field(default="checker", pattern="^(admin|manager|checker)$")


class UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


# ---- Claims -------------------------------------------------------------
class NewClaimRequest(BaseModel):
    raw_email_text: str
    claimant_email: EmailStr
    damage_estimate: float = 0.0
    claim_id: Optional[str] = None
    source: str = "manual"


class ResumeClaimRequest(BaseModel):
    followup_email_text: str
    damage_estimate: Optional[float] = None


class ReviewActionRequest(BaseModel):
    action: str = Field(pattern="^(approve|reject|request_info|escalate|note)$")
    notes: Optional[str] = None
    new_status: Optional[str] = None


class ClaimUpdateRequest(BaseModel):
    status: Optional[str] = None
    policy_number: Optional[str] = None
    incident_date: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None
    fault_claimed: Optional[str] = None
    damage_type: Optional[str] = None
    damage_estimate: Optional[float] = None
    payout: Optional[float] = None


# ---- Settings -------------------------------------------------------------
class SettingsUpdateRequest(BaseModel):
    values: Dict[str, Any]


# ---- SQL query tool -------------------------------------------------------
class SqlQueryRequest(BaseModel):
    sql: str
    limit: int = 500


class SqlQueryResponse(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    row_count: int
    truncated: bool


# ---- Policies / customers (manager data entry) ----------------------------
class PolicyUpsertRequest(BaseModel):
    policy_number: str
    holder_name: str
    holder_email: Optional[EmailStr] = None
    address: Optional[str] = None
    coverage_limit: float
    deductible: float
    start_date: str
    end_date: str


class CustomerUpsertRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
