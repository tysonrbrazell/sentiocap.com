"""
Auth router — register, login, me.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from passlib.context import CryptContext
from supabase import Client

from config import settings
from database import get_db
from models.schemas import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
    UserWithOrgResponse,
    OrgResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(
        minutes=settings.jwt_expire_minutes
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: str = Depends(
        lambda req: (
            req.headers.get("authorization", "").removeprefix("Bearer ").strip()
        )
    ),
    db: Client = Depends(get_db),
) -> dict:
    """Validate JWT and return the current user dict."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
        )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise ValueError("no sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    result = db.table("users").select("*").eq("id", user_id).single().execute()
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return result.data


# ---------------------------------------------------------------------------
# POST /api/auth/register
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, db: Client = Depends(get_db)):
    # Check for duplicate email
    existing = db.table("users").select("id").eq("email", payload.email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create organization
    org_data = {
        "name": payload.org_name,
        "sector": payload.sector,
    }
    org_result = db.table("organizations").insert(org_data).execute()
    org = org_result.data[0]

    # Create user
    user_data = {
        "org_id": org["id"],
        "email": payload.email,
        "name": payload.name,
        "role": "admin",
        "password_hash": hash_password(payload.password),
    }
    user_result = db.table("users").insert(user_data).execute()
    user = user_result.data[0]

    token = create_access_token({"sub": user["id"], "org_id": org["id"]})

    return RegisterResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            org_id=user["org_id"],
        ),
        org=OrgResponse(
            id=org["id"],
            name=org["name"],
            sector=org.get("sector"),
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Client = Depends(get_db)):
    result = db.table("users").select("*").eq("email", payload.email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = result.data[0]
    if not user.get("password_hash") or not verify_password(
        payload.password, user["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Update last login
    db.table("users").update({"last_login_at": datetime.now(timezone.utc).isoformat()}).eq(
        "id", user["id"]
    ).execute()

    token = create_access_token({"sub": user["id"], "org_id": user["org_id"]})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            role=user["role"],
            org_id=user["org_id"],
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserWithOrgResponse)
def me(current_user: dict = Depends(get_current_user), db: Client = Depends(get_db)):
    org_result = (
        db.table("organizations")
        .select("*")
        .eq("id", current_user["org_id"])
        .single()
        .execute()
    )
    org = org_result.data

    return UserWithOrgResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"],
        org_id=current_user["org_id"],
        org=OrgResponse(**org) if org else None,
    )
