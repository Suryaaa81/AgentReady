# PROJECT STATUS: SUBMISSION CANDIDATE — local gates verified; deployment pending

Last verified 2026-08-27. This file is a snapshot, not a running log — see
git history for the full sequence of changes. Public Railway/Vercel
configuration and live URLs still need verification before submission.

## Quality gates (all verified locally, not just claimed)

| Gate | Result |
|---|---|
| `pytest` (backend) | 21/21 passing |
| `ruff check .` (backend) | clean |
| `mypy .` (backend) | clean — 0 errors across 50 source files |
| `npm run build` (frontend) | clean |
| `npm run lint` (frontend) | clean |
| End-to-end smoke test | verified against a live server + seeded SQLite DB: auth rejection (401/422), authenticated catalog fetch, policy fetch, checkout creation with correct inventory reservation |

Reproduce locally:

```bash
cd backend && source .venv/bin/activate && python -m pytest -q && python -m ruff check . && python -m mypy .
cd ../frontend && npm run build && npm run lint
```

## What's implemented

- Merchant catalog import (CSV), search, inventory tracking with row-level locking
- Checkout state machine (`CREATED → READY → AUTHORIZED/AUTHORIZATION_REQUIRED/FAILED → PAYMENT_PENDING → COMPLETED`, plus `EXPIRED`/`CANCELLED`)
- Policy engine: per-order threshold, daily spend limit (enforced against actual completed spend, not just per-order), category allowlist, AP2-style bounded purchase intents
- Razorpay Test Mode integration: server-side order creation, idempotent verification, constant-time HMAC signature check, row-locked payment records
- Gemini native function-calling agent, typed tool dispatch, capped tool-call loop (`MAX_AGENT_TOOL_ROUNDS`)
- Merchant API-key authentication (`POST /merchant/register`, `X-API-Key` on every merchant-scoped route) — see [docs/architecture.md](docs/architecture.md#authentication)
- Idempotent demo bootstrap: `backend/scripts/seed_demo.py` creates a merchant, default policy, sample catalog, and prints a usable API key
- One-command Windows setup: `backend/scripts/bootstrap_dev.ps1` creates env files, seeds the demo, and installs both dependency sets
- Immutable audit event log tied to every state transition
- `.well-known/agentready` capability discovery endpoint
- React/TypeScript merchant dashboard (KPIs, inventory, policy editor, CSV import) + chat UI, both wired to the authenticated API

## Known, deliberate limitations (see README.md "Known limitations" for detail)

- No key rotation/revocation endpoint yet — acceptable for a demo, would need one for real multi-tenant use
- Two checkout-lifecycle routes are intentionally left unauthenticated by design (checkout_id itself is the bearer capability) — documented in architecture.md, not an oversight
- Full agent/payment flow requires real `GEMINI_API_KEY` and Razorpay credentials to exercise end-to-end; without them the relevant endpoints fail clearly rather than silently

## Full report

See [FINAL_BUILDATHON_REPORT.md](FINAL_BUILDATHON_REPORT.md) for the complete problem/solution/stack-rationale writeup, and [docs/architecture.md](docs/architecture.md) for the system diagram, auth model, and full API surface.
