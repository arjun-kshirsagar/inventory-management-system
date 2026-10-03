from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import DocumentCounter


def financial_year(on: date) -> str:
    """Indian FY runs April-March: 2026-10-03 -> '2026-27'."""
    start = on.year if on.month >= 4 else on.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def next_document_number(db: Session, doc_type: str, prefix: str, on: date) -> str:
    """Gapless number within the caller's transaction (the counter row stays locked)."""
    fy = financial_year(on)
    db.execute(
        insert(DocumentCounter)
        .values(doc_type=doc_type, financial_year=fy, last_number=0)
        .on_conflict_do_nothing()
    )
    counter = db.scalars(
        select(DocumentCounter)
        .where(DocumentCounter.doc_type == doc_type, DocumentCounter.financial_year == fy)
        .with_for_update()
    ).one()
    counter.last_number += 1
    return f"{prefix}/{fy}/{counter.last_number:06d}"
