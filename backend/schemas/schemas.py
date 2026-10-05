"""
Pydantic request/response schemas.

Naming convention:
    XCreate  -> payload accepted when creating X
    XUpdate  -> payload accepted when updating X (all fields optional)
    XOut     -> shape returned to the client
"""
import re
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator

from models.models import UserRole, OrderStatus, PaymentStatus, PaymentMethod


def _validate_password_strength(password: str) -> str:
    """Shared password policy: 8+ chars, at least one letter and one digit."""
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters long")
    if not re.search(r"[A-Za-z]", password):
        raise ValueError("password must contain at least one letter")
    if not re.search(r"[0-9]", password):
        raise ValueError("password must contain at least one number")
    return password


# ---------------------------------------------------------------------------
# Tenants (businesses / workspaces)
# ---------------------------------------------------------------------------
class TenantOut(BaseModel):
    id: int
    business_name: str
    slug: str
    address: Optional[str] = None
    gst_number: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TenantUpdate(BaseModel):
    business_name: Optional[str] = None
    address: Optional[str] = None
    gst_number: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------
class RegisterBusiness(BaseModel):
    """Signup for a brand-new business: creates a Tenant + its first Admin user."""
    business_name: str = Field(min_length=2, max_length=150)
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v):
        return _validate_password_strength(v)


class StaffCreate(BaseModel):
    """An existing Admin creates another user account within their own tenant."""
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8)
    role: UserRole = UserRole.STAFF

    @field_validator("password")
    @classmethod
    def _check_password(cls, v):
        return _validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    tenant_id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    tenant: TenantOut


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenOnly(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------
class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    phone: str = Field(min_length=7, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_digits(cls, v):
        digits = "".join(ch for ch in v if ch.isdigit() or ch == "+")
        if len(digits) < 7:
            raise ValueError("phone number must contain at least 7 digits")
        return v


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None


class CustomerOut(CustomerBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------
class ProductBase(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    category: Optional[str] = None
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    description: Optional[str] = None


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None


class StockUpdate(BaseModel):
    change: int  # positive to add stock, negative to remove
    reason: Optional[str] = None


class ProductOut(ProductBase):
    id: int
    created_at: datetime
    low_stock: bool = False

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: int
    items: List[OrderItemCreate] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    status: OrderStatus


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    payment_status: Optional[PaymentStatus] = None


class OrderItemOut(BaseModel):
    id: int
    product_id: int
    product_name: Optional[str] = None
    quantity: int
    unit_price: float
    line_total: float

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    total_amount: float
    order_date: datetime
    status: OrderStatus
    payment_status: PaymentStatus
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Sales (read-only view derived from orders/order_items)
# ---------------------------------------------------------------------------
class SaleOut(BaseModel):
    id: int  # order_item id
    order_id: int
    customer_name: str
    product_name: str
    quantity: int
    unit_price: float
    total_amount: float
    date: datetime
    payment_status: PaymentStatus


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
class ExpenseBase(BaseModel):
    category: str
    description: Optional[str] = None
    amount: float = Field(gt=0)
    date: Optional[datetime] = None
    payment_method: PaymentMethod = PaymentMethod.CASH


class ExpenseCreate(ExpenseBase):
    pass


class ExpenseUpdate(BaseModel):
    category: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    date: Optional[datetime] = None
    payment_method: Optional[PaymentMethod] = None


class ExpenseOut(ExpenseBase):
    id: int
    date: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class PaymentCreate(BaseModel):
    order_id: int
    amount: float = Field(gt=0)
    payment_method: PaymentMethod = PaymentMethod.CASH


class PaymentOut(BaseModel):
    id: int
    customer_id: int
    customer_name: Optional[str] = None
    order_id: int
    amount: float
    payment_method: PaymentMethod
    payment_date: datetime
    status: PaymentStatus

    class Config:
        from_attributes = True


class PaymentSummary(BaseModel):
    order_id: int
    total_order_amount: float
    amount_paid: float
    remaining_balance: float
    payment_status: PaymentStatus


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------
class InvoiceCreate(BaseModel):
    order_id: int
    discount: float = Field(default=0.0, ge=0)
    tax_percent: float = Field(default=0.0, ge=0)


class InvoiceOut(BaseModel):
    id: int
    order_id: int
    invoice_number: str
    invoice_date: datetime
    subtotal: float
    discount: float
    tax_percent: float
    tax_amount: float
    grand_total: float
    payment_status: Optional[PaymentStatus] = None
    customer: Optional[CustomerOut] = None
    items: List[OrderItemOut] = []

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dashboard / Reports
# ---------------------------------------------------------------------------
class DashboardStats(BaseModel):
    total_customers: int
    total_products: int
    total_orders: int
    total_sales: float
    total_expenses: float
    total_profit: float
    pending_payments: float
    recent_orders: List[OrderOut]
    recent_payments: List[PaymentOut]


class MonthlyPoint(BaseModel):
    month: str
    sales: float
    expenses: float
    profit: float


class OrderStatusCount(BaseModel):
    status: str
    count: int
