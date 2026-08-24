# AgentReady Gateway

> Merchant-side agentic-commerce gateway — turns a merchant's catalog, inventory, and policies into an AI-accessible, policy-gated, auditable commerce interface with Razorpay payment execution.

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

### Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"

# Copy env and fill in DATABASE_URL
cp ../.env.example .env

# Run migrations
alembic upgrade head

# Start dev server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# Copy env
echo "VITE_API_URL=http://localhost:8000" > .env

npm run dev
# → http://localhost:5173
```

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `DATABASE_URL` | backend `.env` | PostgreSQL connection string |
| `ENV` | backend `.env` | `development` or `production` |
| `CORS_ORIGINS` | backend `.env` | Comma-separated allowed origins |
| `GEMINI_API_KEY` | backend `.env` | Phase 4 — Gemini function-calling |
| `RAZORPAY_KEY_ID` | backend `.env` | Phase 5 — Razorpay test key |
| `RAZORPAY_KEY_SECRET` | backend `.env` | Phase 5 — Razorpay test secret |
| `RAZORPAY_WEBHOOK_SECRET` | backend `.env` | Phase 5 — webhook verification |
| `VITE_API_URL` | frontend `.env` / Vercel | Backend base URL |

## Security

- Secrets in env vars only — `.env` is gitignored, `.env.example` has no real values.
- Backend is the sole source of truth for price, stock, policy, and payment state.
- The LLM may never mutate checkout/order/payment state or override the policy engine.
- All inputs validated server-side (Pydantic schemas).
- Razorpay signature verified server-side before any state change.

## Limitations (Phase 1)

- No auth/multi-tenancy yet — merchant_id is passed as a header placeholder.
- No Gemini or Razorpay wiring yet.
- No catalog import yet.

## Architecture

See [docs/architecture.md](docs/architecture.md).
