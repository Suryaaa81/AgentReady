# Architecture Decisions

> Record of significant design decisions. Add an entry whenever a non-obvious choice is made.

---

## ADR-001 — Modular Monolith over Microservices

**Date:** 2026-08-24  
**Status:** Accepted

**Context:** Buildathon MVP timeline (9 days). Low operational overhead required.

**Decision:** Single FastAPI process with internal module boundaries (`routers/`, `models/`, `services/`). No Kafka, Redis, or Kubernetes unless proven necessary.

**Consequences:** Simpler deploy (single Railway service), easier debugging, easier demo. Scaling conversation deferred post-MVP.

---

## ADR-002 — Backend is Sole Source of Truth

**Date:** 2026-08-24  
**Status:** Accepted (Authority Rule — never override)

**Context:** LLM agents must never be trusted to report price, stock, or payment state.

**Decision:** All price/inventory reads go through backend queries. Policy engine runs server-side only. Razorpay payment success is verified server-side via HMAC signature before any state mutation.

**Consequences:** No client-side optimistic updates for financial state. LLM receives only structured backend responses.

---

## ADR-003 — Gemini via Native Function-Calling (no standalone MCP process)

**Date:** 2026-08-24  
**Status:** Accepted

**Context:** Master prompt specifies "MCP-shaped contract — no standalone MCP server process."

**Decision:** Agent tools are typed Python functions that call backend services directly. Gemini SDK receives a `tools` list with JSON schemas matching those functions.

**Consequences:** No extra process to deploy. Tool contract is defined in Python, not a separate spec file.

---

## ADR-004 — NUMERIC for all monetary values

**Date:** 2026-08-24  
**Status:** Accepted

**Context:** Floating-point cannot represent money exactly.

**Decision:** All price/amount columns use `NUMERIC(12,2)` in PostgreSQL. Python side uses `Decimal`.

**Consequences:** No float arithmetic on money anywhere in the codebase.

---

## ADR-005 — UUID primary keys throughout

**Date:** 2026-08-24  
**Status:** Accepted

**Context:** Agent-facing IDs must be non-guessable and globally unique for future multi-tenant isolation.

**Decision:** All PKs are `UUID` generated server-side (`uuid4`).

**Consequences:** Slightly larger index footprint vs integer PK. Acceptable for MVP scale.

---

## ADR-006 — Deploy early (end of Phase 1)

**Date:** 2026-08-24  
**Status:** Accepted

**Context:** Master prompt requires skeleton deploy live by end of Phase 1.

**Decision:** Railway (backend), Vercel (frontend), Supabase (PostgreSQL) configured in Phase 1 even before business logic exists. Health endpoint is the only live route.

**Consequences:** Forces CI/CD discipline from day 1. Catches deploy-config issues early.
