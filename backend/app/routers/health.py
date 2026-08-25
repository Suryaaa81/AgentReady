from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """
    Returns backend status and DB connectivity.
    Used by frontend health badge and Railway health check.
    """
    db_ok = False
    db_error: str | None = None
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        db_error = str(exc)

    return {
        "status": "ok" if db_ok else "degraded",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "0.1.0",
        "phase": 1,
        "services": {
            "database": "ok" if db_ok else "error",
            **({"database_error": db_error} if db_error else {}),
        },
    }
