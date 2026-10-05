from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.models import Payment, Order, User, Tenant, PaymentStatus
from schemas.schemas import PaymentCreate, PaymentOut, PaymentSummary
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/payments", tags=["Payments"])


def _to_out(p: Payment) -> PaymentOut:
    out = PaymentOut.model_validate(p)
    out.customer_name = p.customer.name if p.customer else None
    return out


def _get_owned_order(order_id: int, tenant: Tenant, db: Session) -> Order:
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant.id).first()
    if not order:
        raise HTTPException(status_code=400, detail="Invalid order ID")
    return order


def _recompute_order_payment_status(order: Order, db: Session) -> None:
    paid_total = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.order_id == order.id
    ).scalar()
    if paid_total <= 0:
        order.payment_status = PaymentStatus.PENDING
    elif paid_total < order.total_amount:
        order.payment_status = PaymentStatus.PARTIALLY_PAID
    else:
        order.payment_status = PaymentStatus.PAID


@router.post("", response_model=PaymentOut, status_code=201)
def create_payment(payload: PaymentCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    order = _get_owned_order(payload.order_id, tenant, db)

    already_paid = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.order_id == order.id
    ).scalar()
    remaining = round(order.total_amount - already_paid, 2)
    if payload.amount > remaining + 0.01:
        raise HTTPException(status_code=400, detail=f"Payment amount exceeds remaining balance of {remaining}")

    payment = Payment(
        tenant_id=tenant.id,
        customer_id=order.customer_id,
        order_id=order.id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        status=PaymentStatus.PAID,
    )
    db.add(payment)
    db.flush()

    _recompute_order_payment_status(order, db)
    db.commit()
    db.refresh(payment)
    return _to_out(payment)


@router.get("", response_model=List[PaymentOut])
def list_payments(customer_id: Optional[int] = Query(None), order_id: Optional[int] = Query(None),
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                   tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Payment).filter(Payment.tenant_id == tenant.id)
    if customer_id:
        query = query.filter(Payment.customer_id == customer_id)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    payments = query.order_by(Payment.id.desc()).all()
    return [_to_out(p) for p in payments]


@router.get("/order/{order_id}/summary", response_model=PaymentSummary)
def payment_summary(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                     tenant: Tenant = Depends(get_current_tenant)):
    order = _get_owned_order(order_id, tenant, db)
    paid_total = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).filter(
        Payment.order_id == order.id
    ).scalar()
    return PaymentSummary(
        order_id=order.id,
        total_order_amount=order.total_amount,
        amount_paid=round(paid_total, 2),
        remaining_balance=round(order.total_amount - paid_total, 2),
        payment_status=order.payment_status,
    )


@router.get("/{payment_id}", response_model=PaymentOut)
def get_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                 tenant: Tenant = Depends(get_current_tenant)):
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.tenant_id == tenant.id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return _to_out(payment)


@router.delete("/{payment_id}", status_code=204)
def delete_payment(payment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                    tenant: Tenant = Depends(get_current_tenant)):
    """Reverse/delete a payment (e.g. it was recorded by mistake) and recompute the order's status."""
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.tenant_id == tenant.id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    order = db.query(Order).filter(Order.id == payment.order_id, Order.tenant_id == tenant.id).first()
    db.delete(payment)
    db.flush()
    if order:
        _recompute_order_payment_status(order, db)
    db.commit()
    return None
