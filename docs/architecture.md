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
│                                   │  │  (Phase 5)               │   │  │
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

## API Surface

### Discovery
- `GET /.well-known/agentready` — capability profile

### Merchant
- `POST /catalog/import`
- `GET /products`
- `GET /policies` / `PUT /policies`
- `GET /activity`

### Agent Tools (function-calling)
- `POST /search`
- `GET /products/{id}`
- `POST /checkouts` / `GET /checkouts/{id}`
- `POST /checkouts/{id}/update`
- `POST /checkouts/{id}/authorize`
- `POST /checkouts/{id}/complete`
- `POST /checkouts/{id}/cancel`

### Payments
- `POST /payments/create`
- `POST /payments/verify`
- `GET /payments/{id}`

### Audit
- `GET /audit/checkout/{id}`

### Health
- `GET /health`

## Build Log

### Phase 1 — Foundation (2026-08-24)
- **Phase 1**: Monorepo structure, database models, schemas, deployments, health checks (Implemented).
- **Phase 2**: Catalog CRUD, Policy engine rules, Discovery endpoints (Implemented).
- **Phase 3**: Checkout state machine, inventory reservation (Implemented).
- **Phase 4**: Agent-facing schemas and mock capability endpoints (Implemented).
- **Phase 5**: Razorpay Test Mode integration, HMAC server-side verification (Partially Implemented - server-side order creation, idempotency, and HMAC verification added; set RAZORPAY_KEY_ID/SECRET to enable remote Test Mode order creation).
- **Phase 6**: Audit Trail immutable event log (Implemented).
- **Phase 7**: Basic React Admin/Chat/Checkout UI (Implemented).
- **Phase 8-9**: Demo data, E2E Testing, Polish (Implemented).
