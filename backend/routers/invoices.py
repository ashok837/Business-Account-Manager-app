from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.models import Invoice, Order, User, Tenant
from schemas.schemas import InvoiceCreate, InvoiceOut, OrderItemOut, CustomerOut
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/invoices", tags=["Invoices"])


def _next_invoice_number(tenant_id: int, db: Session) -> str:
    count = db.query(Invoice).filter(Invoice.tenant_id == tenant_id).count() + 1
    year = datetime.utcnow().year
    return f"INV-{year}-{count:04d}"


def _to_out(inv: Invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(inv)
    out.payment_status = inv.order.payment_status if inv.order else None
    out.customer = CustomerOut.model_validate(inv.order.customer) if inv.order and inv.order.customer else None
    items = []
    for oi in (inv.order.items if inv.order else []):
        item = OrderItemOut.model_validate(oi)
        item.product_name = oi.product.name if oi.product else None
        items.append(item)
    out.items = items
    return out


@router.post("", response_model=InvoiceOut, status_code=201)
def generate_invoice(payload: InvoiceCreate, db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    order = db.query(Order).filter(Order.id == payload.order_id, Order.tenant_id == tenant.id).first()
    if not order:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    existing = db.query(Invoice).filter(Invoice.order_id == order.id, Invoice.tenant_id == tenant.id).first()
    if existing:
        return _to_out(existing)

    subtotal = order.total_amount
    discount = payload.discount
    taxable = max(subtotal - discount, 0)
    tax_amount = round(taxable * (payload.tax_percent / 100), 2)
    grand_total = round(taxable + tax_amount, 2)

    invoice = Invoice(
        tenant_id=tenant.id,
        order_id=order.id,
        invoice_number=_next_invoice_number(tenant.id, db),
        subtotal=subtotal,
        discount=discount,
        tax_percent=payload.tax_percent,
        tax_amount=tax_amount,
        grand_total=grand_total,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return _to_out(invoice)


@router.get("", response_model=List[InvoiceOut])
def list_invoices(db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                   tenant: Tenant = Depends(get_current_tenant)):
    invoices = db.query(Invoice).filter(Invoice.tenant_id == tenant.id).order_by(Invoice.id.desc()).all()
    return [_to_out(i) for i in invoices]


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                 tenant: Tenant = Depends(get_current_tenant)):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant.id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _to_out(invoice)


@router.get("/business/info")
def business_info(tenant: Tenant = Depends(get_current_tenant)):
    """The calling tenant's own business details, used to render the invoice header."""
    return {
        "name": tenant.business_name,
        "address": tenant.address or "",
        "gst": tenant.gst_number or "",
    }
