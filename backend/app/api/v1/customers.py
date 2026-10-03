from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, CurrentUser
from app.models import Customer
from app.schemas.sales import CustomerIn, CustomerOut

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=list[CustomerOut])
def search_customers(db: DB, _: CurrentUser, q: str = Query("", max_length=100), limit: int = 20):
    stmt = select(Customer).order_by(Customer.name).limit(limit)
    if q:
        stmt = stmt.where(or_(Customer.phone.contains(q), Customer.name.ilike(f"%{q}%")))
    return db.scalars(stmt).all()


@router.get("/by-phone/{phone}", response_model=CustomerOut)
def get_by_phone(phone: str, db: DB, _: CurrentUser):
    customer = db.scalar(select(Customer).where(Customer.phone == phone))
    if customer is None:
        raise HTTPException(404, "Customer not found")
    return customer


@router.post("", response_model=CustomerOut, status_code=201)
def create_customer(data: CustomerIn, db: DB, _: CurrentUser):
    customer = Customer(**data.model_dump())
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A customer with this phone number already exists") from None
    return customer


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(customer_id: int, data: CustomerIn, db: DB, _: CurrentUser):
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(404, "Customer not found")
    for k, v in data.model_dump().items():
        setattr(customer, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A customer with this phone number already exists") from None
    return customer
