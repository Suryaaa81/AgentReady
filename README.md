# AgentReady Gateway

> Merchant-side agentic-commerce gateway — turns a merchant's catalog, inventory, and policies into an AI-accessible, policy-gated, auditable commerce interface with Razorpay payment execution.

**Status:** ruff clean · mypy clean (0 errors across 38 files) · 32 passed + 1 skipped (live API) backend tests passing · frontend Vite build & oxlint clean. Full writeup: [FINAL_BUILDATHON_REPORT.md](FINAL_BUILDATHON_REPORT.md).

## Problem

AI buyers (agents) need a structured, bounded, auditable way to browse merchant catalogs, verify inventory/pricing/policies, and complete purchases — without trusting the agent with money or state mutation. AgentReady provides that interface.

## Judge Quick Read

- **Track:** AI Growth & Agentic Commerce
- **Product:** A merchant gateway that makes catalog, policy, inventory, checkout, and Razorpay payments safe for AI buyers
- **Differentiator:** The model selects typed tools; the backend alone decides price, stock, policy, payment, and state
- **Proof:** Automated backend tests, clean Ruff/mypy/frontend gates, authenticated payment actions, durable audit receipts, oversell prevention, expired session invalidation, and explicit stockout / policy rejection failure paths
- **Best demo:** Ask for a product, trigger a policy decision, show the reserved inventory, then force a stockout and show the rejected payment plus audit event

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

## Demo Flow (failure — stockout or policy rejection)

```
AI buyer asks for shoes
→ search_products → check_inventory → create_checkout
→ between checkout and payment: inventory drops to 0 or session expires
→ policy revalidation / checkout validation → FAILED / EXPIRED
→ reserved inventory returned to available pool, no payment initiated
→ audit event written
→ agent receives rejection + explanation
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (or local SQLite for dev)

### One-command setup (Windows PowerShell)

From the repository root:

```powershell
.\backend\scripts\bootstrap_dev.ps1
```

This creates the backend virtual environment, installs both dependency sets,
writes `backend/.env`, runs database migrations, creates the demo data, writes the
one-time API key to `frontend/.env`, and installs frontend dependencies.

### Manual backend setup

```powershell
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"

# Copy env and configure credentials
Copy-Item ..\.env.example .env

# Run migrations
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

## Quality Gates & Verification

Run the entire suite locally:

```bash
# Backend (from backend/):
pytest -q
ruff check .
mypy app

# Frontend (from frontend/):
npm run build
npx oxlint
```

## Environment Variables

| Variable | Where | Description |
|---|---|---|
| `DATABASE_URL` | backend `.env` | PostgreSQL connection string; default local SQLite is `sqlite:///agentready_dev.db` |
| `ENV` | backend `.env` | `development` or `production` |
| `CORS_ORIGINS` | backend `.env` | Comma-separated allowed origins |
| `GEMINI_API_KEY` | backend `.env` | Gemini function-calling credentials (`google-genai` SDK) |
| `RAZORPAY_KEY_ID` | backend `.env` | Razorpay Test Mode key ID |
| `RAZORPAY_KEY_SECRET` | backend `.env` | Razorpay Test Mode secret |
| `RAZORPAY_WEBHOOK_SECRET` | backend `.env` | Razorpay webhook verification secret |
| `PAYMENT_PROVIDER` | backend `.env` | `mock` for local development; `razorpay` in production |
| `VITE_API_URL` | frontend `.env` | Backend base URL (default `http://localhost:8000`) |
| `VITE_MERCHANT_API_KEY` | frontend `.env` | Merchant API key from `POST /merchant/register` or `seed_demo.py` |

## Security & Architectural Safeguards

- **Secrets in env vars only**: `.env` is gitignored, `.env.example` has no sensitive values.
- **Server-Derived Identity**: Every merchant route requires `X-API-Key`. Identity is derived server-side via SHA-256 hash lookup (`app/security.py`), never trusted from client assertion.
- **Backend as Single Source of Truth**: The LLM may never mutate checkout/order/payment state directly or override policy decisions. It only calls typed tools and relays results.
- **Oversell Prevention & Row Locking**: `SELECT ... FOR UPDATE` row locks inventory on checkout creation. Inventory is reserved during `READY`/`AUTHORIZED`/`PAYMENT_PENDING` and released back to available pool on `CANCELLED`/`FAILED`/`EXPIRED`. On `COMPLETED`, reserved stock is finalized.
- **Fail-Closed Payment Verification**: Razorpay signatures are verified using constant-time HMAC-SHA256 compare. If signature verification fails, checkout and payment are marked `FAILED` and reserved inventory is immediately returned.
- **Session Expiry Re-validation**: Checkouts re-validate expiration and limits before payment order creation.
- **Daily Spend Limits**: Enforced against actual completed spend across the merchant today, blocking restructuring bypasses.

## Known Limitations / Not Working

- **External Live Keys Required for End-to-End Live API Calls**: Native Gemini agent execution (`POST /agent/chat`) requires a valid, active `GEMINI_API_KEY`. Real Razorpay order capture requires valid `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` (the repo provides a full offline test suite and mock payment provider mode for environments without live credentials).
- **Merchant Key Rotation UI**: There is currently no web UI for self-service key rotation/revocation; generating a new key requires registering a merchant or updating the DB record directly.
- **Public Checkout Polling Routes**: `GET /checkout/sessions/{id}` and `GET /audit/checkout/{id}` are intentionally unauthenticated capability tokens (like Stripe Checkout sessions) so AI buyers can poll status without holding the merchant's private admin key.

## Architecture

See [docs/architecture.md](docs/architecture.md) for data models, system diagram, and detailed router specs.
