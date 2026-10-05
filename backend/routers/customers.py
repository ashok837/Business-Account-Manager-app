from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models.models import Customer, Order, Payment, User, Tenant
from schemas.schemas import CustomerCreate, CustomerUpdate, CustomerOut, OrderOut, PaymentOut
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    customer = Customer(**payload.model_dump(), tenant_id=tenant.id)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("", response_model=List[CustomerOut])
def list_customers(search: Optional[str] = Query(None, description="Search by name, phone, or email"),
                    db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Customer).filter(Customer.tenant_id == tenant.id)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Customer.name.ilike(like), Customer.phone.ilike(like), Customer.email.ilike(like)))
    return query.order_by(Customer.id.desc()).all()


def _get_owned_customer(customer_id: int, tenant: Tenant, db: Session) -> Customer:
    """Fetch a customer, scoped to the tenant - prevents cross-tenant ID guessing (IDOR)."""
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant.id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(customer_id: int, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    return _get_owned_customer(customer_id, tenant, db)


@router.get("/{customer_id}/orders", response_model=List[OrderOut])
def get_customer_orders(customer_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    customer = _get_owned_customer(customer_id, tenant, db)
    results = []
    for o in customer.orders:
        item = OrderOut.model_validate(o)
        item.customer_name = customer.name
        for i, oi in enumerate(item.items):
            oi.product_name = o.items[i].product.name if o.items[i].product else None
        results.append(item)
    return results


@router.get("/{customer_id}/payments", response_model=List[PaymentOut])
def get_customer_payments(customer_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    customer = _get_owned_customer(customer_id, tenant, db)
    results = []
    for p in customer.payments:
        item = PaymentOut.model_validate(p)
        item.customer_name = customer.name
        results.append(item)
    return results


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, payload: CustomerUpdate, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    customer = _get_owned_customer(customer_id, tenant, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    customer = _get_owned_customer(customer_id, tenant, db)
    if customer.orders:
        raise HTTPException(status_code=400, detail="Cannot delete a customer with existing orders")
    db.delete(customer)
    db.commit()
    return None
