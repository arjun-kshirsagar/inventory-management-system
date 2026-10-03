from sqlalchemy.orm import Session

from app.models import StoreSettings


def get_store_settings(db: Session) -> StoreSettings:
    settings = db.get(StoreSettings, 1)
    if settings is None:
        settings = StoreSettings(id=1)
        db.add(settings)
        db.flush()
    return settings
