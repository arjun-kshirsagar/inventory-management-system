from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.deps import DB, AdminUser, CurrentUser
from app.models import TaxSlab
from app.schemas.settings import StoreSettingsIn, StoreSettingsOut, TaxSlabIn, TaxSlabOut
from app.services.store import get_store_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/store", response_model=StoreSettingsOut)
def get_store(db: DB, _: CurrentUser):
    settings = get_store_settings(db)
    db.commit()
    return settings


@router.put("/store", response_model=StoreSettingsOut)
def update_store(data: StoreSettingsIn, db: DB, _: AdminUser):
    settings = get_store_settings(db)
    for k, v in data.model_dump().items():
        setattr(settings, k, v)
    db.commit()
    return settings


@router.get("/tax-slabs", response_model=list[TaxSlabOut])
def list_tax_slabs(db: DB, _: CurrentUser):
    return db.scalars(select(TaxSlab).order_by(TaxSlab.hsn_prefix, TaxSlab.effective_from)).all()


@router.post("/tax-slabs", response_model=TaxSlabOut, status_code=201)
def create_tax_slab(data: TaxSlabIn, db: DB, _: AdminUser):
    slab = TaxSlab(**data.model_dump())
    db.add(slab)
    db.commit()
    return slab


@router.put("/tax-slabs/{slab_id}", response_model=TaxSlabOut)
def update_tax_slab(slab_id: int, data: TaxSlabIn, db: DB, _: AdminUser):
    slab = db.get(TaxSlab, slab_id)
    if slab is None:
        raise HTTPException(404, "Tax slab not found")
    for k, v in data.model_dump().items():
        setattr(slab, k, v)
    db.commit()
    return slab


@router.delete("/tax-slabs/{slab_id}", status_code=204)
def delete_tax_slab(slab_id: int, db: DB, _: AdminUser):
    slab = db.get(TaxSlab, slab_id)
    if slab is None:
        raise HTTPException(404, "Tax slab not found")
    db.delete(slab)
    db.commit()
