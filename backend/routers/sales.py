from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models.models import OrderItem, Order, Customer, Product, User, Tenant, PaymentStatus
from schemas.schemas import SaleOut
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/sales", tags=["Sales"])


@router.get("", response_model=List[SaleOut])
def list_sales(customer_id: Optional[int] = Query(None), product_id: Optional[int] = Query(None),
                payment_status: Optional[PaymentStatus] = Query(None),
                date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                tenant: Tenant = Depends(get_current_tenant)):
    """Sales are derived from order line items (each order item = one sale line)."""
    query = (
        db.query(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .join(Product, OrderItem.product_id == Product.id)
        .filter(Order.tenant_id == tenant.id)
    )
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    if product_id:
        query = query.filter(OrderItem.product_id == product_id)
    if payment_status:
        query = query.filter(Order.payment_status == payment_status)
    if date_from:
        query = query.filter(Order.order_date >= date_from)
    if date_to:
        query = query.filter(Order.order_date <= date_to)

    rows = query.order_by(Order.order_date.desc()).all()
    results = []
    for oi in rows:
        results.append(SaleOut(
            id=oi.id,
            order_id=oi.order_id,
            customer_name=oi.order.customer.name,
            product_name=oi.product.name,
            quantity=oi.quantity,
            unit_price=oi.unit_price,
            total_amount=oi.line_total,
            date=oi.order.order_date,
            payment_status=oi.order.payment_status,
        ))
    return results
