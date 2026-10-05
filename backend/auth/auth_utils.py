"""
Authentication & security utilities:
  - password hashing (bcrypt) and a shared strength policy (see schemas.py)
  - short-lived JWT access tokens + long-lived, revocable refresh tokens
  - FastAPI dependencies for: current user, current tenant, and role checks
  - account lockout after repeated failed logins (brute-force mitigation)

SECURITY NOTE ON TENANCY: `get_current_tenant` is the single choke point
every router depends on to scope its queries. Every router MUST filter its
queries by `tenant.id` and MUST verify that any referenced foreign row
(a customer_id, product_id, order_id, etc. passed in by the client) also
belongs to that same tenant before using it. Skipping either check is a
cross-tenant data leak (IDOR vulnerability), not just a bug.
"""
import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from database import get_db
from models.models import User, UserRole, Tenant, RefreshToken

load_dotenv()

# Single shared rate-limiter instance, imported by both main.py (to register
# the exception handler + app.state) and routers/auth.py (to decorate routes).
limiter = Limiter(key_func=get_remote_address)

SECRET_KEY = os.getenv("SECRET_KEY", "insecure-dev-secret-change-me")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))

MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
if ENVIRONMENT == "production" and SECRET_KEY == "insecure-dev-secret-change-me":
    raise RuntimeError(
        "Refusing to start in production with the default SECRET_KEY. "
        "Set a real, random SECRET_KEY in your environment (see .env.example)."
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ---------------------------------------------------------------------------
# Access tokens (short-lived JWT, carries user id + tenant id + role)
# ---------------------------------------------------------------------------
def create_access_token(user: User) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user.id),
        "tenant_id": user.tenant_id,
        "role": user.role.value,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Refresh tokens (opaque random string; only a hash is stored server-side so
# a leaked database dump can't be replayed as a valid token)
# ---------------------------------------------------------------------------
def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token(user: User, db: Session) -> str:
    raw_token = secrets.token_urlsafe(48)
    db.add(RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    ))
    db.commit()
    return raw_token


def revoke_refresh_token(raw_token: str, db: Session) -> None:
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_token(raw_token)).first()
    if row:
        row.revoked = True
        db.commit()


def use_refresh_token(raw_token: str, db: Session) -> User:
    """Validate a refresh token and return its owning (active) user, or raise 401."""
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    row = db.query(RefreshToken).filter(RefreshToken.token_hash == _hash_token(raw_token)).first()
    if not row or row.revoked or row.expires_at < datetime.utcnow():
        raise unauthorized
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user or not user.is_active:
        raise unauthorized
    return user


# ---------------------------------------------------------------------------
# Account lockout (brute-force mitigation, complements login-endpoint rate
# limiting configured in main.py)
# ---------------------------------------------------------------------------
def register_failed_login(user: User, db: Session) -> None:
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
    db.commit()


def register_successful_login(user: User, db: Session) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()


def is_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > datetime.utcnow())


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_tenant(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Tenant:
    """
    The tenant-scoping choke point. Every protected, business-data route
    should depend on this (directly or via current_user.tenant) and filter
    every query it runs by `tenant.id`.
    """
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This business account is not active")
    return tenant


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that only allows users with the admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires administrator privileges",
        )
    return current_user
