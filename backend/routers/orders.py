from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.models import Order, OrderItem, Customer, Product, User, Tenant, OrderStatus, PaymentStatus
from schemas.schemas import OrderCreate, OrderOut, OrderStatusUpdate, OrderUpdate
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/orders", tags=["Orders"])


def _to_out(order: Order) -> OrderOut:
    out = OrderOut.model_validate(order)
    out.customer_name = order.customer.name if order.customer else None
    for i, oi in enumerate(order.items):
        out.items[i].product_name = oi.product.name if oi.product else None
    return out


def _get_owned_order(order_id: int, tenant: Tenant, db: Session) -> Order:
    """Fetch an order scoped to the tenant - prevents cross-tenant ID guessing (IDOR)."""
    order = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant.id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Invalid order ID")
    return order


@router.post("", response_model=OrderOut, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    """
    Business logic on order creation:
      1. Check customer exists AND belongs to this tenant.
      2. Check each product exists AND belongs to this tenant.
      3. Check sufficient stock for each product.
      4. Calculate line totals and order total.
      5. Create the order + order items.
      6. Reduce product stock.
      7. Set initial payment status (Pending).
    """
    customer = db.query(Customer).filter(Customer.id == payload.customer_id, Customer.tenant_id == tenant.id).first()
    if not customer:
        raise HTTPException(status_code=400, detail="Invalid customer ID")

    products_by_id = {}
    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id, Product.tenant_id == tenant.id).first()
        if not product:
            raise HTTPException(status_code=400, detail=f"Invalid product ID: {item.product_id}")
        if product.quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.name}'. Available: {product.quantity}, requested: {item.quantity}",
            )
        products_by_id[item.product_id] = product

    order = Order(tenant_id=tenant.id, customer_id=customer.id, status=OrderStatus.PENDING,
                  payment_status=PaymentStatus.PENDING)
    db.add(order)
    db.flush()  # get order.id before committing

    total = 0.0
    for item in payload.items:
        product = products_by_id[item.product_id]
        line_total = round(product.price * item.quantity, 2)
        total += line_total
        db.add(OrderItem(
            order_id=order.id,
            product_id=product.id,
            quantity=item.quantity,
            unit_price=product.price,
            line_total=line_total,
        ))
        product.quantity -= item.quantity

    order.total_amount = round(total, 2)
    db.commit()
    db.refresh(order)
    return _to_out(order)


@router.get("", response_model=List[OrderOut])
def list_orders(status: Optional[OrderStatus] = Query(None),
                 payment_status: Optional[PaymentStatus] = Query(None),
                 customer_id: Optional[int] = Query(None),
                 db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                 tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Order).filter(Order.tenant_id == tenant.id)
    if status:
        query = query.filter(Order.status == status)
    if payment_status:
        query = query.filter(Order.payment_status == payment_status)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    orders = query.order_by(Order.id.desc()).all()
    return [_to_out(o) for o in orders]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
              tenant: Tenant = Depends(get_current_tenant)):
    return _to_out(_get_owned_order(order_id, tenant, db))


@router.put("/{order_id}", response_model=OrderOut)
def update_order(order_id: int, payload: OrderUpdate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    order = _get_owned_order(order_id, tenant, db)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] == OrderStatus.CANCELLED and order.status != OrderStatus.CANCELLED:
        _restore_stock(order, db)
    for field, value in data.items():
        setattr(order, field, value)
    db.commit()
    db.refresh(order)
    return _to_out(order)


def _restore_stock(order: Order, db: Session):
    """Restore product stock for every item in a cancelled order."""
    for item in order.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product:
            product.quantity += item.quantity


@router.patch("/{order_id}/status", response_model=OrderOut)
def update_order_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    order = _get_owned_order(order_id, tenant, db)

    if payload.status == OrderStatus.CANCELLED and order.status != OrderStatus.CANCELLED:
        _restore_stock(order, db)
        if order.payment_status != PaymentStatus.PENDING:
            order.payment_status = PaymentStatus.PENDING

    order.status = payload.status
    db.commit()
    db.refresh(order)
    return _to_out(order)


@router.delete("/{order_id}", status_code=204)
def delete_order(order_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                  tenant: Tenant = Depends(get_current_tenant)):
    order = _get_owned_order(order_id, tenant, db)
    if order.status not in (OrderStatus.PENDING, OrderStatus.CANCELLED):
        raise HTTPException(status_code=400, detail="Only pending or cancelled orders can be deleted")
    if order.status == OrderStatus.PENDING:
        _restore_stock(order, db)
    db.delete(order)
    db.commit()
    return None
