from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


# Re-usable column helpers
def pk() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=new_uuid)


def fk_str(target: str) -> Mapped[str]:
    from sqlalchemy import ForeignKey
    return mapped_column(String(36), ForeignKey(target), nullable=False)


def fk_str_nullable(target: str) -> Mapped[str | None]:
    from sqlalchemy import ForeignKey
    return mapped_column(String(36), ForeignKey(target), nullable=True)


def ts_created() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.now(),
        nullable=False,
    )


def ts_updated() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
        nullable=False,
    )
