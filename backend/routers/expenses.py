from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models.models import Expense, User, Tenant
from schemas.schemas import ExpenseCreate, ExpenseUpdate, ExpenseOut
from auth.auth_utils import get_current_user, get_current_tenant

router = APIRouter(prefix="/expenses", tags=["Expenses"])


def _get_owned_expense(expense_id: int, tenant: Tenant, db: Session) -> Expense:
    expense = db.query(Expense).filter(Expense.id == expense_id, Expense.tenant_id == tenant.id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


@router.post("", response_model=ExpenseOut, status_code=201)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    data = payload.model_dump()
    if not data.get("date"):
        data["date"] = datetime.utcnow()
    expense = Expense(**data, tenant_id=tenant.id)
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=List[ExpenseOut])
def list_expenses(category: Optional[str] = Query(None),
                   date_from: Optional[datetime] = Query(None), date_to: Optional[datetime] = Query(None),
                   db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                   tenant: Tenant = Depends(get_current_tenant)):
    query = db.query(Expense).filter(Expense.tenant_id == tenant.id)
    if category:
        query = query.filter(Expense.category == category)
    if date_from:
        query = query.filter(Expense.date >= date_from)
    if date_to:
        query = query.filter(Expense.date <= date_to)
    return query.order_by(Expense.date.desc()).all()


@router.get("/{expense_id}", response_model=ExpenseOut)
def get_expense(expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                 tenant: Tenant = Depends(get_current_tenant)):
    return _get_owned_expense(expense_id, tenant, db)


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(expense_id: int, payload: ExpenseUpdate, db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user), tenant: Tenant = Depends(get_current_tenant)):
    expense = _get_owned_expense(expense_id, tenant, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    db.commit()
    db.refresh(expense)
    return expense


@router.delete("/{expense_id}", status_code=204)
def delete_expense(expense_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
                    tenant: Tenant = Depends(get_current_tenant)):
    expense = _get_owned_expense(expense_id, tenant, db)
    db.delete(expense)
    db.commit()
    return None
