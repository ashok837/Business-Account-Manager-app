import csv
import io
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import get_db
from models.models import Order, OrderItem, Customer, Product, Expense, Payment, User, Tenant, OrderStatus, PaymentStatus
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/reports", tags=["Reports"])


def _period_bounds(period: str):
    now = datetime.utcnow()
    if period == "daily":
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
    elif period == "weekly":
        start = now - timedelta(days=now.weekday())
        start = datetime(start.year, start.month, start.day)
        end = start + timedelta(days=7)
    else:
        start = datetime(now.year, now.month, 1)
        end = datetime(now.year + 1, 1, 1) if now.month == 12 else datetime(now.year, now.month + 1, 1)
    return start, end


def _csv_response(filename: str, header: list, rows: list):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _sales_query(db: Session, tenant_id: int, date_from=None, date_to=None, customer_id=None, product_id=None,
                  payment_status=None):
    query = (
        db.query(OrderItem)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.tenant_id == tenant_id, Order.status != OrderStatus.CANCELLED)
    )
    if date_from:
        query = query.filter(Order.order_date >= date_from)
    if date_to:
        query = query.filter(Order.order_date <= date_to)
    if customer_id:
        query = query.filter(Order.customer_id == customer_id)
    if product_id:
        query = query.filter(OrderItem.product_id == product_id)
    if payment_status:
        query = query.filter(Order.payment_status == payment_status)
    return query


@router.get("/sales")
def sales_report(period: Optional[str] = Query(None, pattern="^(daily|weekly|monthly)$"),
                  date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                  customer_id: Optional[int] = Query(None), product_id: Optional[int] = Query(None),
                  payment_status: Optional[PaymentStatus] = Query(None),
                  export: Optional[str] = Query(None, pattern="^(csv)$"),
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                  tenant: Tenant = Depends(get_current_tenant)):
    if period and not (date_from or date_to):
        date_from, date_to = _period_bounds(period)

    rows = _sales_query(db, tenant.id, date_from, date_to, customer_id, product_id, payment_status).all()

    total_sales = round(sum(r.line_total for r in rows), 2)
    line_items = [
        {
            "date": r.order.order_date.isoformat(),
            "order_id": r.order_id,
            "customer": r.order.customer.name,
            "product": r.product.name,
            "quantity": r.quantity,
            "unit_price": r.unit_price,
            "total": r.line_total,
            "payment_status": r.order.payment_status.value,
        }
        for r in rows
    ]

    if export == "csv":
        header = ["Date", "Order ID", "Customer", "Product", "Quantity", "Unit Price", "Total", "Payment Status"]
        csv_rows = [[li["date"], li["order_id"], li["customer"], li["product"], li["quantity"],
                     li["unit_price"], li["total"], li["payment_status"]] for li in line_items]
        return _csv_response("sales_report.csv", header, csv_rows)

    return {"total_sales": total_sales, "count": len(line_items), "items": line_items}


@router.get("/expenses")
def expense_report(date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                    category: Optional[str] = Query(None),
                    export: Optional[str] = Query(None, pattern="^(csv)$"),
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                    tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Expense).filter(Expense.tenant_id == tenant.id)
    if date_from:
        query = query.filter(Expense.date >= date_from)
    if date_to:
        query = query.filter(Expense.date <= date_to)
    if category:
        query = query.filter(Expense.category == category)
    rows = query.order_by(Expense.date.desc()).all()

    total = round(sum(e.amount for e in rows), 2)
    by_category = {}
    for e in rows:
        by_category[e.category] = round(by_category.get(e.category, 0) + e.amount, 2)

    if export == "csv":
        header = ["Date", "Category", "Description", "Amount", "Payment Method"]
        csv_rows = [[e.date.isoformat(), e.category, e.description or "", e.amount, e.payment_method.value]
                    for e in rows]
        return _csv_response("expense_report.csv", header, csv_rows)

    return {
        "total_expenses": total,
        "by_category": by_category,
        "items": [
            {"id": e.id, "date": e.date.isoformat(), "category": e.category, "description": e.description,
             "amount": e.amount, "payment_method": e.payment_method.value}
            for e in rows
        ],
    }


@router.get("/profit")
def profit_report(date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                   tenant: Tenant = Depends(get_current_tenant)):
    sales_rows = _sales_query(db, tenant.id, date_from, date_to).all()
    total_sales = round(sum(r.line_total for r in sales_rows), 2)

    exp_query = db.query(Expense).filter(Expense.tenant_id == tenant.id)
    if date_from:
        exp_query = exp_query.filter(Expense.date >= date_from)
    if date_to:
        exp_query = exp_query.filter(Expense.date <= date_to)
    total_expenses = round(sum(e.amount for e in exp_query.all()), 2)

    return {
        "total_revenue": total_sales,
        "total_expenses": total_expenses,
        "net_profit": round(total_sales - total_expenses, 2),
    }


@router.get("/customers")
def customer_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                     tenant: Tenant = Depends(get_current_tenant)):
    customers = db.query(Customer).filter(Customer.tenant_id == tenant.id).all()
    results = []
    for c in customers:
        active_orders = [o for o in c.orders if o.status != OrderStatus.CANCELLED]
        total_spent = round(sum(o.total_amount for o in active_orders), 2)
        paid = round(sum(p.amount for p in c.payments), 2)
        results.append({
            "customer_id": c.id,
            "name": c.name,
            "total_orders": len(active_orders),
            "total_spent": total_spent,
            "total_paid": paid,
            "outstanding_balance": round(total_spent - paid, 2),
        })
    return results


@router.get("/products")
def product_stock_report(db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                          tenant: Tenant = Depends(get_current_tenant)):
    products = db.query(Product).filter(Product.tenant_id == tenant.id).all()
    results = []
    for p in products:
        units_sold = sum(oi.quantity for oi in p.order_items if oi.order.status != OrderStatus.CANCELLED)
        revenue = sum(oi.line_total for oi in p.order_items if oi.order.status != OrderStatus.CANCELLED)
        results.append({
            "product_id": p.id,
            "name": p.name,
            "category": p.category,
            "current_stock": p.quantity,
            "low_stock": p.quantity <= p.low_stock_threshold,
            "units_sold": units_sold,
            "revenue": round(revenue, 2),
        })
    return results


@router.get("/payments")
def payment_report(date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                    payment_status: Optional[PaymentStatus] = Query(None),
                    export: Optional[str] = Query(None, pattern="^(csv)$"),
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                    tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Payment).filter(Payment.tenant_id == tenant.id)
    if date_from:
        query = query.filter(Payment.payment_date >= date_from)
    if date_to:
        query = query.filter(Payment.payment_date <= date_to)
    if payment_status:
        query = query.filter(Payment.status == payment_status)
    rows = query.order_by(Payment.payment_date.desc()).all()

    if export == "csv":
        header = ["Date", "Customer", "Order ID", "Amount", "Method", "Status"]
        csv_rows = [[p.payment_date.isoformat(), p.customer.name, p.order_id, p.amount,
                     p.payment_method.value, p.status.value] for p in rows]
        return _csv_response("payment_report.csv", header, csv_rows)

    total = round(sum(p.amount for p in rows), 2)
    return {
        "total_collected": total,
        "items": [
            {"id": p.id, "date": p.payment_date.isoformat(), "customer": p.customer.name, "order_id": p.order_id,
             "amount": p.amount, "method": p.payment_method.value, "status": p.status.value}
            for p in rows
        ],
    }
