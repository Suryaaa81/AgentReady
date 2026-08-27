# AgentReady Gateway

> Merchant-side agentic-commerce gateway — turns a merchant's catalog, inventory, and policies into an AI-accessible, policy-gated, auditable commerce interface with Razorpay payment execution.

**Status:** ruff clean · mypy clean (0 errors) · 21/21 backend tests passing · frontend build & lint clean. Full writeup: [FINAL_BUILDATHON_REPORT.md](FINAL_BUILDATHON_REPORT.md).

## Problem

AI buyers (agents) need a structured, bounded, auditable way to browse merchant catalogs, verify inventory/pricing/policies, and complete purchases — without trusting the agent with money or state mutation. AgentReady provides that interface.

## Protocol Positioning

> MCP-enabled, ACP-style checkout lifecycle, UCP-inspired capability discovery, AP2-inspired bounded authorization, Razorpay payment execution — not a claim of full protocol compliance.

## Demo Flow (success path)

```
AI buyer asks for shoes
→ search_products("shoes")
→ check_inventory(variant_id)
→ get_shipping_policy / get_return_policy
→ create_checkout
→ policy check → ALLOW
→ request_payment → Razorpay test order
→ server-side signature verify
→ mark paid → finalize inventory → confirm order → write audit receipt
→ agent receives confirmation + receipt
```

## Demo Flow (failure — stockout)

```
AI buyer asks for shoes
→ search_products → check_inventory → create_checkout
→ between checkout and payment: inventory drops to 0
→ policy revalidation → OUT_OF_STOCK
→ checkout → FAILED, no payment initiated
→ audit event written
→ agent receives rejection + explanation
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (or Supabase project)

### One-command setup (Windows PowerShell)

From the repository root:

```powershell
.\backend\scripts\bootstrap_dev.ps1
```

This creates the backend virtual environment, installs both dependency sets,
writes `backend/.env`, creates the SQLite schema and demo data, writes the
one-time API key to `frontend/.env`, and installs frontend dependencies. Run
the two commands it prints in separate terminals. Vite reads `.env` when the
dev server starts, so restart `npm run dev` after changing it.

### Manual backend setup

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"

# Copy env and fill in DATABASE_URL (SQLite is fine for local dev)
Copy-Item ..\.env.example .env

# Run migrations (Postgres) — for local SQLite dev, seed_demo.py below
# creates the schema itself, this step is only needed against Postgres
alembic upgrade head

# Bootstrap a demo merchant, API key, and sample catalog
python scripts/seed_demo.py --frontend-env ..\frontend\.env
# → prints an API key ONCE. Copy it — it's needed for every authenticated
#   request and cannot be retrieved again after this point.

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Manual frontend setup

```bash
cd frontend
npm install

Copy-Item .env.example .env
# Set VITE_MERCHANT_API_KEY to the key printed by seed_demo.py.

npm run dev
# → http://localhost:5173
```

For macOS/Linux, use `cp` instead of `Copy-Item` and
`source .venv/bin/activate` instead of the Windows activation command.

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `DATABASE_URL` | backend `.env` | PostgreSQL connection string; the default local SQLite file is absolute and lives in `backend/` |
| `ENV` | backend `.env` | `development` or `production` |
| `CORS_ORIGINS` | backend `.env` | Comma-separated allowed origins |
| `GEMINI_API_KEY` | backend `.env` | Phase 4 — Gemini function-calling |
| `RAZORPAY_KEY_ID` | backend `.env` | Phase 5 — Razorpay test key |
| `RAZORPAY_KEY_SECRET` | backend `.env` | Phase 5 — Razorpay test secret |
| `RAZORPAY_WEBHOOK_SECRET` | backend `.env` | Phase 5 — webhook verification |
| `VITE_API_URL` | frontend `.env` / Vercel | Backend base URL |
| `VITE_MERCHANT_API_KEY` | frontend `.env` / Vercel | Merchant API key from `POST /merchant/register` or `seed_demo.py` |

## Security

- Secrets in env vars only — `.env` is gitignored, `.env.example` has no real values.
- Every merchant-scoped route requires `X-API-Key`; the server derives merchant identity from the authenticated key, never from anything the client asserts (`app/security.py`). See [docs/architecture.md](docs/architecture.md#authentication) for exactly which routes are auth-required vs. intentionally public.
- API keys are hashed (SHA-256) at rest and shown to the merchant exactly once, at registration.
- Backend is the sole source of truth for price, stock, policy, and payment state.
- The LLM may never mutate checkout/order/payment state or override the policy engine — it only calls typed tools and relays their results.
- All inputs validated server-side (Pydantic schemas).
- Razorpay signature verified server-side (constant-time compare) before any state change.
- Inventory reservation and payment verification both use row-level locking (`SELECT ... FOR UPDATE`) to stay correct under concurrent requests.
- Daily spend limits are enforced against actual completed spend, not just per-checkout — closes the "split one purchase into several small ones" bypass.

## Known limitations

- No merchant-facing key rotation/revocation UI yet — regenerating a key currently means registering a new merchant record. Fine for a demo, would need a proper `/merchant/rotate-key` endpoint for real multi-tenant use.
- `POST /checkout/sessions/{id}/cancel` and `/authorize` are intentionally unauthenticated (see Authentication in architecture.md) — this is a deliberate trade-off, not an oversight, but worth being able to explain if asked.
- Gemini and Razorpay calls require real API keys (`GEMINI_API_KEY`, `RAZORPAY_KEY_ID`/`RAZORPAY_KEY_SECRET`/`RAZORPAY_WEBHOOK_SECRET`) to actually reach those services — without them, `/agent/chat` and `/payment/*` return a clear error rather than failing silently, but the full flow can't be demoed end-to-end until keys are configured.

## Architecture

See [docs/architecture.md](docs/architecture.md).
