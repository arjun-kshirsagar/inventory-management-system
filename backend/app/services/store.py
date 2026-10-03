from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import StoreSettings


def get_store_settings(db: Session) -> StoreSettings:
    settings = db.get(StoreSettings, 1)
    if settings is None:
        settings = StoreSettings(id=1)
        db.add(settings)
        db.flush()
    return settings


def store_today() -> date:
    """Today's date in the store's timezone (decides invoice FY and GST rate dates)."""
    return datetime.now(ZoneInfo(get_settings().store_timezone)).date()
