from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import SessionLocal
from app.limiter import limiter
from app.routers.agent import router as agent_router
from app.routers.audit import router as audit_router
from app.routers.catalog import router as catalog_router
from app.routers.checkout import router as checkout_router
from app.routers.health import router as health_router
from app.routers.merchant import router as merchant_router
from app.routers.payment import router as payment_router
from app.routers.well_known import router as well_known_router
from app.services.checkout import cleanup_expired_checkouts


async def cleanup_task():
    while True:
        try:
            with SessionLocal() as db:
                cleanup_expired_checkouts(db)
        except Exception:
            pass
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_task())
    yield
    task.cancel()


app = FastAPI(
    title="AgentReady Gateway",
    lifespan=lifespan,
    description=(
        "Merchant-side agentic-commerce gateway. "
        "MCP-enabled, ACP-style checkout lifecycle, UCP-inspired capability discovery, "
        "AP2-inspired bounded authorization, Razorpay payment execution."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health_router)
app.include_router(well_known_router)
app.include_router(merchant_router)
app.include_router(catalog_router)
app.include_router(checkout_router)
app.include_router(agent_router)
app.include_router(payment_router)
app.include_router(audit_router)
