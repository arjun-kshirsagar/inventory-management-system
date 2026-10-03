from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.deps import DB, AdminUser
from app.core.security import hash_password
from app.models import User
from app.schemas.auth import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, _: AdminUser):
    return db.scalars(select(User).order_by(User.name)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, db: DB, _: AdminUser):
    user = User(
        email=data.email.lower(),
        name=data.name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A user with this email already exists") from None
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: DB, admin: AdminUser):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "User not found")
    if user.id == admin.id and (data.is_active is False or (data.role and data.role != admin.role)):
        raise HTTPException(400, "You cannot deactivate or demote yourself")
    changes = data.model_dump(exclude_unset=True)
    if password := changes.pop("password", None):
        user.password_hash = hash_password(password)
    for key, value in changes.items():
        setattr(user, key, value)
    db.commit()
    return user
