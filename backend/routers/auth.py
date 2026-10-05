import re
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db
from models.models import User, UserRole, Tenant
from schemas.schemas import (
    RegisterBusiness, StaffCreate, UserOut, Token, UserLogin,
    RefreshRequest, AccessTokenOnly, TenantOut, TenantUpdate,
)
from auth.auth_utils import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    revoke_refresh_token, use_refresh_token, get_current_user, require_admin,
    get_current_tenant, register_failed_login, register_successful_login, is_locked,
    limiter,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "business"


def _unique_slug(base_slug: str, db: Session) -> str:
    slug = base_slug
    suffix = 1
    while db.query(Tenant).filter(Tenant.slug == slug).first():
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    return slug


def _issue_token_pair(user: User, tenant: Tenant, db: Session) -> Token:
    return Token(
        access_token=create_access_token(user),
        refresh_token=create_refresh_token(user, db),
        user=user,
        tenant=tenant,
    )


@router.post("/register-business", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
def register_business(request: Request, payload: RegisterBusiness, db: Session = Depends(get_db)):
    """
    Sign up a brand-new business. Creates a Tenant (workspace) and its first
    user as Admin. Rate-limited per IP to slow down automated mass sign-ups.
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    tenant = Tenant(business_name=payload.business_name, slug=_unique_slug(_slugify(payload.business_name), db))
    db.add(tenant)
    db.flush()  # get tenant.id

    user = User(
        tenant_id=tenant.id,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.refresh(tenant)
    return _issue_token_pair(user, tenant, db)


@router.post("/staff", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_staff(payload: StaffCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Admin-only: add a Staff (or additional Admin) user to the caller's own tenant."""
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="A user with this email already exists")

    user = User(
        tenant_id=admin.tenant_id,
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login-json", response_model=Token)
@limiter.limit("10/minute")
def login_json(request: Request, payload: UserLogin, db: Session = Depends(get_db)):
    """JSON login used by the frontend. Rate-limited and lockout-protected against brute force."""
    user = db.query(User).filter(User.email == payload.email).first()

    # Constant-shape response whether the email exists or not, to avoid
    # leaking which emails are registered.
    generic_error = HTTPException(status_code=401, detail="Incorrect email or password")

    if not user:
        raise generic_error
    if is_locked(user):
        raise HTTPException(
            status_code=403,
            detail=f"This account is temporarily locked due to repeated failed logins. Try again later.",
        )
    if not verify_password(payload.password, user.hashed_password):
        register_failed_login(user, db)
        raise generic_error
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=403, detail="This business account is not active")

    register_successful_login(user, db)
    return _issue_token_pair(user, tenant, db)


@router.post("/refresh", response_model=AccessTokenOnly)
def refresh_access_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a still-valid refresh token for a new short-lived access token."""
    user = use_refresh_token(payload.refresh_token, db)
    return AccessTokenOnly(access_token=create_access_token(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Revoke a refresh token server-side (the access token simply expires on its own, quickly)."""
    revoke_refresh_token(payload.refresh_token, db)
    return None


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/tenant", response_model=TenantOut)
def read_current_tenant(tenant: Tenant = Depends(get_current_tenant)):
    return tenant


@router.put("/tenant", response_model=TenantOut)
def update_current_tenant(payload: TenantUpdate, db: Session = Depends(get_db),
                           tenant: Tenant = Depends(get_current_tenant), admin: User = Depends(require_admin)):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Admin only: list every user account within the admin's own tenant."""
    return db.query(User).filter(User.tenant_id == admin.tenant_id).order_by(User.id).all()


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    """Admin only: deactivate a user account within the admin's own tenant (soft delete)."""
    user = db.query(User).filter(User.id == user_id, User.tenant_id == admin.tenant_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
