"""
Business assistant chatbot.

POST /chat  { "message": "...", "history": [{"role": "user"|"assistant", "content": "..."}] }

How it answers:
  1. Rule-based intents (sales, profit, low stock, pending payments, top
     products/customers, recent orders...) run tenant-scoped queries and
     answer from the logged-in business's own data. No API key needed.
  2. If ANTHROPIC_API_KEY is set in .env, anything the rules don't recognise
     is sent to Claude together with a small snapshot of the business's
     numbers, so it can answer free-form questions. Without a key, unknown
     questions get a helpful fallback listing what the bot can do.

SECURITY: every query filters by tenant.id (same rule as every other router).
"""
import json
import os
import re
import urllib.error
import urllib.request
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth.auth_utils import get_current_tenant, get_current_user, limiter
from database import get_db
from models.models import (
    Customer, Expense, Order, OrderItem, OrderStatus, Payment, PaymentStatus,
    Product, Tenant, User,
)

router = APIRouter(prefix="/chat", tags=["Chatbot"])

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")


class ChatTurn(BaseModel):
    role: str
    content: str = Field(max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    history: List[ChatTurn] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    suggestions: List[str] = []
    source: str = "rules"  # "rules" or "claude"


DEFAULT_SUGGESTIONS = ["Today's summary", "Low stock items", "Pending payments", "Top products"]


def money(n: float) -> str:
    return f"₹{float(n or 0):,.2f}"


# ---------------------------------------------------------------------------
# Data helpers (all tenant-scoped)
# ---------------------------------------------------------------------------
def _totals(db: Session, tid: int) -> dict:
    sales = db.query(func.coalesce(func.sum(OrderItem.line_total), 0.0)).join(
        Order, OrderItem.order_id == Order.id
    ).filter(Order.tenant_id == tid, Order.status != OrderStatus.CANCELLED).scalar()
    expenses = db.query(func.coalesce(func.sum(Expense.amount), 0.0)).filter(Expense.tenant_id == tid).scalar()

    outstanding = db.query(func.coalesce(func.sum(Order.total_amount), 0.0)).filter(
        Order.tenant_id == tid, Order.payment_status != PaymentStatus.PAID, Order.status != OrderStatus.CANCELLED
    ).scalar()
    paid_on_open = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).join(
        Order, Payment.order_id == Order.id
    ).filter(Order.tenant_id == tid, Order.payment_status != PaymentStatus.PAID,
             Order.status != OrderStatus.CANCELLED).scalar()

    return {
        "customers": db.query(func.count(Customer.id)).filter(Customer.tenant_id == tid).scalar(),
        "products": db.query(func.count(Product.id)).filter(Product.tenant_id == tid).scalar(),
        "orders": db.query(func.count(Order.id)).filter(Order.tenant_id == tid).scalar(),
        "sales": float(sales),
        "expenses": float(expenses),
        "profit": float(sales) - float(expenses),
        "pending": max(float(outstanding) - float(paid_on_open), 0.0),
    }


def _low_stock(db: Session, tid: int):
    return db.query(Product).filter(
        Product.tenant_id == tid, Product.quantity <= Product.low_stock_threshold
    ).order_by(Product.quantity.asc()).limit(10).all()


def _top_products(db: Session, tid: int):
    return db.query(Product.name, func.sum(OrderItem.quantity), func.sum(OrderItem.line_total)).join(
        OrderItem, OrderItem.product_id == Product.id
    ).join(Order, OrderItem.order_id == Order.id).filter(
        Order.tenant_id == tid, Product.tenant_id == tid, Order.status != OrderStatus.CANCELLED
    ).group_by(Product.id, Product.name).order_by(func.sum(OrderItem.line_total).desc()).limit(5).all()


def _top_customers(db: Session, tid: int):
    return db.query(Customer.name, func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0.0)).join(
        Order, Order.customer_id == Customer.id
    ).filter(
        Order.tenant_id == tid, Customer.tenant_id == tid, Order.status != OrderStatus.CANCELLED
    ).group_by(Customer.id, Customer.name).order_by(func.sum(Order.total_amount).desc()).limit(5).all()


def _recent_orders(db: Session, tid: int):
    return db.query(Order).filter(Order.tenant_id == tid).order_by(Order.id.desc()).limit(5).all()


# ---------------------------------------------------------------------------
# Rule-based intents
# ---------------------------------------------------------------------------
def _has(text: str, *words: str) -> bool:
    return any(re.search(rf"\b{re.escape(w)}", text) for w in words)


def rule_based_answer(message: str, db: Session, tenant: Tenant, user: User) -> Optional[ChatResponse]:
    t = message.lower().strip()
    tid = tenant.id

    if _has(t, "hello", "hi", "hey", "good morning", "good evening") and len(t.split()) <= 4:
        first = (user.full_name or "there").split()[0]
        return ChatResponse(
            reply=f"Hi {first}! I'm your business assistant for {tenant.business_name}. "
                  "Ask me about sales, profit, stock, payments, customers or orders.",
            suggestions=DEFAULT_SUGGESTIONS,
        )

    if _has(t, "help", "what can you do", "commands"):
        return ChatResponse(
            reply="I can look up live numbers from your workspace:\n"
                  "• Sales, expenses and profit\n• Low-stock products\n• Pending payments\n"
                  "• Top products and top customers\n• Recent orders\n• Customer / product / order counts\n\n"
                  "I can also explain where to find things, e.g. \"how do I create an invoice?\"",
            suggestions=DEFAULT_SUGGESTIONS,
        )

    if _has(t, "summary", "overview", "snapshot", "how is my business", "how's my business", "dashboard"):
        s = _totals(db, tid)
        return ChatResponse(
            reply=f"Here's your business snapshot:\n"
                  f"• Sales: {money(s['sales'])}\n• Expenses: {money(s['expenses'])}\n"
                  f"• Profit: {money(s['profit'])}\n• Pending payments: {money(s['pending'])}\n"
                  f"• {s['orders']} orders · {s['customers']} customers · {s['products']} products",
            suggestions=["Low stock items", "Top customers", "Recent orders"],
        )

    if _has(t, "profit", "earning", "net income"):
        s = _totals(db, tid)
        verdict = "You're in the green." if s["profit"] >= 0 else "Expenses currently exceed sales."
        return ChatResponse(
            reply=f"Total profit is {money(s['profit'])} ({money(s['sales'])} sales − {money(s['expenses'])} expenses). {verdict}",
            suggestions=["Total expenses", "Today's summary"],
        )

    if _has(t, "expense", "spending", "spent", "cost"):
        s = _totals(db, tid)
        rows = db.query(Expense.category, func.sum(Expense.amount)).filter(
            Expense.tenant_id == tid
        ).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).limit(3).all()
        extra = ""
        if rows:
            extra = "\nBiggest categories: " + ", ".join(f"{c} ({money(a)})" for c, a in rows)
        return ChatResponse(reply=f"Total expenses recorded: {money(s['expenses'])}.{extra}",
                            suggestions=["What's my profit?", "Today's summary"])

    if _has(t, "sale", "revenue", "turnover", "income"):
        s = _totals(db, tid)
        return ChatResponse(
            reply=f"Total sales (excluding cancelled orders): {money(s['sales'])} across {s['orders']} orders.",
            suggestions=["Top products", "Top customers", "What's my profit?"],
        )

    if _has(t, "low stock", "out of stock", "running out", "restock", "reorder", "inventory", "stock"):
        items = _low_stock(db, tid)
        if not items:
            return ChatResponse(reply="Great news — nothing is at or below its low-stock threshold right now. ✅",
                                suggestions=["Top products", "Today's summary"])
        lines = "\n".join(f"• {p.name}: {p.quantity} left (alert at {p.low_stock_threshold})" for p in items)
        return ChatResponse(reply=f"{len(items)} product(s) need restocking:\n{lines}\n\n"
                                  "Tip: use the Stock button on the Products page to add inventory.",
                            suggestions=["Top products", "Pending payments"])

    if _has(t, "pending", "unpaid", "outstanding", "due", "owe", "collect"):
        s = _totals(db, tid)
        rows = db.query(Order).filter(
            Order.tenant_id == tid, Order.payment_status != PaymentStatus.PAID,
            Order.status != OrderStatus.CANCELLED,
        ).order_by(Order.id.desc()).limit(5).all()
        lines = "\n".join(f"• Order #{o.id} — {o.customer.name} — {money(o.total_amount)} ({o.payment_status.value})" for o in rows)
        body = f"Outstanding payments total {money(s['pending'])}."
        if lines:
            body += f"\nLatest unpaid orders:\n{lines}"
        return ChatResponse(reply=body, suggestions=["Recent orders", "Today's summary"])

    if _has(t, "top product", "best seller", "best selling", "bestseller", "popular product", "top selling"):
        rows = _top_products(db, tid)
        if not rows:
            return ChatResponse(reply="No sales yet, so there's no best-seller to show. Create an order to get started.",
                                suggestions=DEFAULT_SUGGESTIONS)
        lines = "\n".join(f"{i}. {n} — {int(q)} sold, {money(r)}" for i, (n, q, r) in enumerate(rows, 1))
        return ChatResponse(reply=f"Your top products by revenue:\n{lines}", suggestions=["Low stock items", "Top customers"])

    if _has(t, "top customer", "best customer", "biggest customer", "loyal"):
        rows = _top_customers(db, tid)
        if not rows:
            return ChatResponse(reply="No orders yet, so there are no top customers to show.", suggestions=DEFAULT_SUGGESTIONS)
        lines = "\n".join(f"{i}. {n} — {c} order(s), {money(a)}" for i, (n, c, a) in enumerate(rows, 1))
        return ChatResponse(reply=f"Your top customers by order value:\n{lines}", suggestions=["Top products", "Pending payments"])

    if _has(t, "recent order", "latest order", "new order", "last order", "orders"):
        rows = _recent_orders(db, tid)
        if not rows:
            return ChatResponse(reply="There are no orders yet. Head to Orders → New Order to create the first one.",
                                suggestions=DEFAULT_SUGGESTIONS)
        lines = "\n".join(f"• #{o.id} — {o.customer.name} — {money(o.total_amount)} — {o.status.value}" for o in rows)
        return ChatResponse(reply=f"Your latest orders:\n{lines}", suggestions=["Pending payments", "Top customers"])

    if _has(t, "how many customer", "number of customer", "total customer", "customers"):
        s = _totals(db, tid)
        return ChatResponse(reply=f"You have {s['customers']} customer(s) and {s['products']} product(s) in your workspace.",
                            suggestions=["Top customers", "Top products"])

    if _has(t, "invoice"):
        return ChatResponse(
            reply="Invoices are generated from orders: open the Invoices page, choose an order, set any discount and tax %, "
                  "then download the PDF.",
            suggestions=["Pending payments", "Recent orders"],
        )

    if _has(t, "report", "export", "pdf", "download"):
        return ChatResponse(reply="The Reports page has sales, expense and profit reports that you can filter by date and export as PDF.",
                            suggestions=["Today's summary", "What's my profit?"])

    if _has(t, "add user", "staff", "team member", "employee"):
        role = "As an admin you can" if user.role.value == "admin" else "Only admins can"
        return ChatResponse(reply=f"{role} add staff accounts from the Users page in the sidebar.", suggestions=DEFAULT_SUGGESTIONS)

    if _has(t, "thank", "thanks", "thx"):
        return ChatResponse(reply="You're welcome! Anything else I can look up?", suggestions=DEFAULT_SUGGESTIONS)

    return None


# ---------------------------------------------------------------------------
# Optional Claude fallback (stdlib only, no extra dependency)
# ---------------------------------------------------------------------------
def claude_answer(message: str, history: List[ChatTurn], db: Session, tenant: Tenant) -> Optional[str]:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    s = _totals(db, tenant.id)
    low = [f"{p.name} ({p.quantity} left)" for p in _low_stock(db, tenant.id)]
    top = [f"{n} ({money(r)})" for n, _, r in _top_products(db, tenant.id)]
    system = (
        f"You are the in-app assistant for '{tenant.business_name}', a small business using a management app "
        "(pages: Dashboard, Customers, Products, Orders, Sales, Expenses, Payments, Invoices, Reports, Users). "
        "Answer briefly and practically using ONLY the data below; if the data doesn't contain the answer, say so "
        "and point to the relevant page. Amounts are in Indian rupees (₹).\n\n"
        f"Snapshot: sales {money(s['sales'])}, expenses {money(s['expenses'])}, profit {money(s['profit'])}, "
        f"pending payments {money(s['pending'])}, {s['orders']} orders, {s['customers']} customers, "
        f"{s['products']} products.\nLow stock: {', '.join(low) or 'none'}.\nTop products: {', '.join(top) or 'none'}."
    )
    msgs = [{"role": h.role, "content": h.content} for h in history[-10:] if h.role in ("user", "assistant")]
    msgs.append({"role": "user", "content": message})
    # The API requires the first message to be from the user.
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)

    body = json.dumps({"model": ANTHROPIC_MODEL, "max_tokens": 500, "system": system, "messages": msgs}).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=body, method="POST",
        headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text").strip()
        return text or None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


FALLBACK = (
    "I'm not sure about that one yet. I can help with sales, profit, expenses, low stock, pending payments, "
    "top products/customers and recent orders — try one of the suggestions below."
)


@router.post("", response_model=ChatResponse)
@limiter.limit("30/minute")
def chat(request: Request, payload: ChatRequest, db: Session = Depends(get_db),
         current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    answer = rule_based_answer(payload.message, db, tenant, current_user)
    if answer:
        return answer

    text = claude_answer(payload.message, payload.history, db, tenant)
    if text:
        return ChatResponse(reply=text, suggestions=DEFAULT_SUGGESTIONS, source="claude")
    return ChatResponse(reply=FALLBACK, suggestions=DEFAULT_SUGGESTIONS)
