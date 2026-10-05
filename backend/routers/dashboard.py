from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models.models import Customer, Product, Order, OrderItem, Expense, Payment, User, Tenant, OrderStatus, PaymentStatus
from schemas.schemas import DashboardStats, MonthlyPoint, OrderStatusCount
from auth.auth_utils import get_current_user, get_current_tenant
from routers.orders import _to_out as order_to_out
from routers.payments import _to_out as payment_to_out

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
              tenant: Tenant = Depends(get_current_tenant)):
    tid = tenant.id
    total_customers = db.query(func.count(Customer.id)).filter(Customer.tenant_id == tid).scalar()
    total_products = db.query(func.count(Product.id)).filter(Product.tenant_id == tid).scalar()
    total_orders = db.query(func.count(Order.id)).filter(Order.tenant_id == tid).scalar()

    total_sales = db.query(func.coalesce(func.sum(OrderItem.line_total), 0.0)).join(
        Order, OrderItem.order_id == Order.id
    ).filter(Order.tenant_id == tid, Order.status != OrderStatus.CANCELLED).scalar()

    total_expenses = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
        Expense.tenant_id == tid
    ).scalar()

    pending_payments = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
        Order.tenant_id == tid, Order.payment_status != PaymentStatus.PAID, Order.status != OrderStatus.CANCELLED
    ).scalar()
    paid_so_far = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).join(
        Order, Payment.order_id == Order.id
    ).filter(Order.tenant_id == tid, Order.payment_status != PaymentStatus.PAID,
              Order.status != OrderStatus.CANCELLED).scalar()
    pending_payments = round(pending_payments - paid_so_far, 2)

    total_profit = round(total_sales - total_expenses, 2)

    recent_orders = db.query(Order).filter(Order.tenant_id == tid).order_by(Order.id.desc()).limit(5).all()
    recent_payments = db.query(Payment).filter(Payment.tenant_id == tid).order_by(Payment.id.desc()).limit(5).all()

    return DashboardStats(
        total_customers=total_customers,
        total_products=total_products,
        total_orders=total_orders,
        total_sales=round(total_sales, 2),
        total_expenses=round(total_expenses, 2),
        total_profit=total_profit,
        pending_payments=max(pending_payments, 0.0),
        recent_orders=[order_to_out(o) for o in recent_orders],
        recent_payments=[payment_to_out(p) for p in recent_payments],
    )


@router.get("/monthly", response_model=List[MonthlyPoint])
def get_monthly_chart_data(months: int = 6, db: Session = Depends(get_db),
                            current_user: User = Depends(get_current_user),
                            tenant: Tenant = Depends(get_current_tenant)):
    tid = tenant.id
    today = datetime.utcnow()
    points: List[MonthlyPoint] = []
    for i in range(months - 1, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        sales = db.query(func.coalesce(func.sum(OrderItem.line_total), 0.0)).join(
            Order, OrderItem.order_id == Order.id
        ).filter(Order.tenant_id == tid, Order.order_date >= start, Order.order_date < end,
                  Order.status != OrderStatus.CANCELLED).scalar()

        expenses = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(
            Expense.tenant_id == tid, Expense.date >= start, Expense.date < end
        ).scalar()

        points.append(MonthlyPoint(
            month=start.strftime("%b %Y"),
            sales=round(sales, 2),
            expenses=round(expenses, 2),
            profit=round(sales - expenses, 2),
        ))
    return points


@router.get("/order-status-breakdown", response_model=List[OrderStatusCount])
def get_order_status_breakdown(db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                                tenant: Tenant = Depends(get_current_tenant)):
    rows = db.query(Order.status, func.count(Order.id)).filter(Order.tenant_id == tenant.id).group_by(Order.status).all()
    return [OrderStatusCount(status=status.value, count=count) for status, count in rows]
