from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models.models import Product, User, Tenant
from schemas.schemas import ProductCreate, ProductUpdate, ProductOut, StockUpdate
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/products", tags=["Products"])


def _to_out(p: Product) -> ProductOut:
    out = ProductOut.model_validate(p)
    out.low_stock = p.quantity <= p.low_stock_threshold
    return out


def _get_owned_product(product_id: int, tenant: Tenant, db: Session) -> Product:
    """Fetch a product scoped to the tenant - prevents cross-tenant ID guessing (IDOR)."""
    product = db.query(Product).filter(Product.id == product_id, Product.tenant_id == tenant.id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    product = Product(**payload.model_dump(), tenant_id=tenant.id)
    db.add(product)
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.get("", response_model=List[ProductOut])
def list_products(search: Optional[str] = Query(None), category: Optional[str] = Query(None),
                   low_stock_only: bool = Query(False),
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                   tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Product).filter(Product.tenant_id == tenant.id)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(like), Product.category.ilike(like)))
    if category:
        query = query.filter(Product.category == category)
    products = query.order_by(Product.id.desc()).all()
    results = [_to_out(p) for p in products]
    if low_stock_only:
        results = [p for p in results if p.low_stock]
    return results


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                 tenant: Tenant = Depends(get_current_tenant)):
    return _to_out(_get_owned_product(product_id, tenant, db))


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    product = _get_owned_product(product_id, tenant, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.patch("/{product_id}/stock", response_model=ProductOut)
def update_stock(product_id: int, payload: StockUpdate, db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    """Manually adjust stock, e.g. after a restock delivery or inventory correction."""
    product = _get_owned_product(product_id, tenant, db)
    new_qty = product.quantity + payload.change
    if new_qty < 0:
        raise HTTPException(status_code=400, detail="Insufficient stock for this adjustment")
    product.quantity = new_qty
    db.commit()
    db.refresh(product)
    return _to_out(product)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                    tenant: Tenant = Depends(get_current_tenant)):
    product = _get_owned_product(product_id, tenant, db)
    if product.order_items:
        raise HTTPException(status_code=400, detail="Cannot delete a product that has existing orders")
    db.delete(product)
    db.commit()
    return None
