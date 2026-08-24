from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router
from app.routers.well_known import router as well_known_router
from app.routers.merchant import router as merchant_router
from app.routers.catalog import router as catalog_router
from app.routers.checkout import router as checkout_router
from app.routers.agent import router as agent_router
from app.routers.payment import router as payment_router
from app.routers.audit import router as audit_router

app = FastAPI(
    title="AgentReady Gateway",
    description=(
        "Merchant-side agentic-commerce gateway. "
        "MCP-enabled, ACP-style checkout lifecycle, UCP-inspired capability discovery, "
        "AP2-inspired bounded authorization, Razorpay payment execution."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

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
