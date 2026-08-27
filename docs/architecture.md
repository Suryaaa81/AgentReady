# Architecture — AgentReady Gateway

> Living document. Updated at the end of each phase.

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AgentReady Gateway                             │
│                                                                         │
│  ┌─────────────┐    HTTPS/JSON    ┌──────────────────────────────────┐  │
│  │  AI Buyer   │ ───────────────► │  FastAPI Backend (Railway)       │  │
│  │  (Agent)    │                  │                                  │  │
│  └─────────────┘                  │  ┌──────────────────────────┐   │  │
│                                   │  │  Policy Engine           │   │  │
│  ┌─────────────┐    React SPA      │  │  (backend-only, no LLM)  │   │  │
│  │  Merchant   │ ───────────────► │  └──────────────────────────┘  │  │
│  │  Dashboard  │                  │                                  │  │
│  │  (Vercel)   │                  │  ┌──────────────────────────┐   │  │
│  └─────────────┘                  │  │  Razorpay Test Mode      │   │  │
│                                   │  │  (Test Mode)             │   │  │
│                                   │  └──────────────────────────┘  │  │
│                                   └──────────────┬───────────────────┘  │
│                                                  │ SQLAlchemy           │
│                                   ┌──────────────▼───────────────────┐  │
│                                   │  PostgreSQL (Supabase)           │  │
│                                   └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Agent Flow and Function Calling

The conversational flow for autonomous purchases and agent interactions is:

User → Gemini (LLM) → Native Function Calling → Backend (authoritative tools) → Checkout → Razorpay (Test Mode) → Audit Trail

Important constraints:
- All inventory, pricing, policies, checkout state, and payment status are authoritative server-side and are never fabricated by the LLM. The server executes any function-calling requests and returns verified results to the model and client.
- Tool execution is idempotent where applicable (checkout → order creation → payment).


## State Machine (checkout_sessions — backend-owned only)

```
CREATED
  │
  ▼
READY ──────────────────────────────────────────────────────────────────►CANCELLED
  │
  ├── policy ALLOW ──────────────────────────────────────────────────────►PAYMENT_PENDING
  │                                                                          │
  ├── policy REQUIRE_HUMAN_APPROVAL ─────────────────────────────────────►AUTHORIZATION_REQUIRED
  │                                                                          │ (human approves)
  │                                                                          ▼
  │                                                                       AUTHORIZED
  │                                                                          │
  │                                                                          ▼
  │                                                                       PAYMENT_PENDING
  │                                                                          │
  ├── policy REJECT ─────────────────────────────────────────────────────►FAILED
  │
  ▼
COMPLETED

Side states reachable from most states:
  EXPIRED (TTL elapsed)
  FAILED  (OUT_OF_STOCK | PRICE_CHANGED | POLICY_REJECTED | LIMIT_EXCEEDED | INVALID_INTENT | PAYMENT_FAILED)
```

## Database Schema

### merchants
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR | |
| email | VARCHAR UNIQUE | |
| api_key_hash | VARCHAR | future auth |
| created_at | TIMESTAMPTZ | UTC |
| updated_at | TIMESTAMPTZ | UTC |

### merchant_policies
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| merchant_id | UUID FK | |
| max_autonomous_amount | NUMERIC(12,2) | |
| currency | VARCHAR(3) | ISO-4217 |
| daily_limit | NUMERIC(12,2) | |
| allowed_categories | JSONB | array of strings |
| max_delivery_days | INTEGER | |
| min_return_days | INTEGER | |
| approval_threshold | NUMERIC(12,2) | |
| expires_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### products
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| merchant_id | UUID FK | |
| sku | VARCHAR | unique per merchant |
| name | VARCHAR | |
| description | TEXT | |
| category | VARCHAR | |
| base_price | NUMERIC(12,2) | |
| currency | VARCHAR(3) | |
| is_active | BOOLEAN | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### product_variants
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| product_id | UUID FK | |
| sku | VARCHAR UNIQUE | |
| attributes | JSONB | size, color, etc. |
| price_override | NUMERIC(12,2) | nullable |
| created_at | TIMESTAMPTZ | |

### inventory
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| variant_id | UUID FK UNIQUE | |
| available_qty | INTEGER | |
| reserved_qty | INTEGER | |
| updated_at | TIMESTAMPTZ | |

### checkout_sessions
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| merchant_id | UUID FK | |
| status | VARCHAR | state machine |
| failure_reason | VARCHAR | nullable |
| currency | VARCHAR(3) | |
| total_amount | NUMERIC(12,2) | |
| expires_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### checkout_items
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| checkout_id | UUID FK | |
| variant_id | UUID FK | |
| quantity | INTEGER | |
| unit_price | NUMERIC(12,2) | snapshot at checkout time |
| created_at | TIMESTAMPTZ | |

### purchase_intents
| Column | Type | Notes |
|---|---|---|
| intent_id | UUID PK | |
| merchant_id | UUID FK | |
| max_amount | NUMERIC(12,2) | |
| currency | VARCHAR(3) | |
| allowed_category | VARCHAR | |
| expires_at | TIMESTAMPTZ | |
| status | VARCHAR | ACTIVE / CONSUMED / EXPIRED |
| created_at | TIMESTAMPTZ | |

### orders
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| checkout_id | UUID FK UNIQUE | |
| merchant_id | UUID FK | |
| status | VARCHAR | |
| total_amount | NUMERIC(12,2) | |
| currency | VARCHAR(3) | |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### payments
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| order_id | UUID FK | |
| razorpay_order_id | VARCHAR | |
| razorpay_payment_id | VARCHAR | nullable until captured |
| status | VARCHAR | |
| amount | NUMERIC(12,2) | |
| currency | VARCHAR(3) | |
| receipt_data | JSONB | durable verified receipt snapshot |
| verified_at | TIMESTAMPTZ | nullable |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

### audit_events
| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| merchant_id | UUID FK | |
| checkout_id | UUID FK | nullable |
| event_type | VARCHAR | |
| actor | VARCHAR | agent / merchant / system |
| payload | JSONB | |
| created_at | TIMESTAMPTZ | immutable |

## Authentication

Every merchant gets one API key, issued once at `POST /merchant/register`
and never shown again — only its SHA-256 hash is stored
(`merchants.api_key_hash`). Callers send it as `X-API-Key` on every
authenticated request.

`merchant_id` is never accepted from the client anymore. Every route that
used to take it as a query/body parameter now derives it from the
authenticated key instead (`app/security.py::get_current_merchant`) — a
caller can only ever act as the merchant whose key it holds. Two routes
are deliberately left unauthenticated by design, not by oversight:
`GET /checkout/sessions/{id}` and `GET /audit/checkout/{id}` — the
`checkout_id` itself is an unguessable UUID that functions as a bearer
capability for that one resource, the same pattern Stripe Checkout
Sessions use, so an AI buyer polling for status doesn't need the
merchant's own key.

## API Surface

(routes as implemented — see `backend/app/routers/` for the source of truth)

### Discovery — public
- `GET /health`
- `GET /.well-known/agentready?merchant_id={id}` — capability profile

### Merchant
- `POST /merchant/register` — public; creates a merchant + default policy, returns the API key once
- `GET /merchant/policies` — auth required
- `PUT /merchant/policies` — auth required

### Catalog — auth required
- `GET /catalog/products`
- `POST /catalog/import` (CSV upload)
- `GET /catalog/search?query=`

### Checkout
- `POST /checkout/sessions` — auth required
- `GET /checkout/sessions/{id}` — public (see Authentication above)
- `POST /checkout/sessions/{id}/cancel` — public
- `POST /checkout/sessions/{id}/authorize` — public
- `POST /checkout/intents` — auth required

### Agent
- `POST /agent/chat` — auth required; Gemini function-calling loop, capped at `MAX_AGENT_TOOL_ROUNDS` (default 8)

### Payment
- `POST /payment/order` — auth required; creates a Razorpay Test Mode order
- `POST /payment/verify` — auth required; HMAC-SHA256 signature check, constant-time compare, row-locked

### Audit
- `GET /audit/merchant` — auth required
- `GET /audit/checkout/{id}` — public (see Authentication above)

For local development, `backend/scripts/bootstrap_dev.ps1` creates a
cwd-independent SQLite database at `backend/agentready_dev.db`, seeds the
demo merchant and catalog, and writes the Vite API key to `frontend/.env`.
Production deployments use PostgreSQL and Alembic migrations instead.

## Build Log

- **Foundation**: monorepo structure, database models, schemas, deployments, health checks.
- **Catalog & policy**: CSV import, policy engine rules, discovery endpoint.
- **Checkout**: state machine, row-locked inventory reservation.
- **Agent**: Gemini native function-calling, typed tool dispatch, capped tool-call loop.
- **Payments**: Razorpay Test Mode order creation, idempotent verification, HMAC signature check.
- **Audit**: immutable event log tied to every state transition.
- **Auth**: merchant registration, hashed API keys, `X-API-Key` dependency on every merchant-scoped route.
- **Quality gates**: ruff clean, mypy clean (0 errors across 51 source files), 26/26 backend tests passing, frontend build + lint clean.
- **Bootstrap**: `backend/scripts/seed_demo.py` — idempotent demo merchant + sample catalog for any fresh database.
- **Phase 8-9**: Demo data, E2E Testing, Polish (Implemented).
