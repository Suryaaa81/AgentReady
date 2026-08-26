# AgentReady Gateway — Full Project Report

**Merchant-side agentic-commerce gateway for the Razorpay AI Buildathon 2026 (Track: AI Growth & Agentic Commerce)**

Repo: github.com/Suryaaa81/AgentReady

---

## 1. The Problem

AI shopping agents (ChatGPT, Gemini, Claude, and custom bots) are starting to browse, decide, and buy on a human's behalf. That creates a trust problem that didn't exist when a human was clicking "Buy Now" themselves:

- **A merchant cannot let an LLM directly touch price, inventory, or payment state.** LLMs hallucinate, can be prompt-injected by malicious product descriptions or user input, and have no inherent concept of "this stock count is authoritative." If the model is allowed to *say* "your order total is ₹500" and that number is trusted, a merchant is one bad completion away from a wrong charge or a phantom order.
- **A merchant also cannot let an agent transact with zero limits.** Even with a perfectly behaved model, someone has to answer: how much can an agent spend without a human approving it? What categories can it buy from? What happens if two agents try to buy the last unit at the same time? What happens if stock runs out *between* browsing and paying?
- **There is no single standard yet.** OpenAI/Stripe have ACP, Google/Shopify have UCP, Google also has AP2 for bounded cross-network authorization, Coinbase has x402 for stablecoin micropayments, and India's NPCI is drafting UAP over UPI Circle delegation (pending RBI approval). A merchant integrating "agentic commerce" today has to bet on a protocol landscape that hasn't converged.

**The specific problem AgentReady answers:** *How does a merchant expose a catalog, policies, and checkout to an AI buyer in a way that is bounded, auditable, and never trusts the model with money or state — while staying protocol-agnostic enough to not bet the wrong horse this early?*

---

## 2. The Solution

AgentReady is a backend-authoritative commerce gateway that sits between an AI buyer and a merchant's catalog/inventory/payment systems. The core design rule, enforced structurally rather than by convention:

> **The LLM may only call typed tools. It can never fabricate a price, a stock count, a checkout state, or a payment result — every one of those values is computed and returned by the backend, and the model just relays it.**

### 2.1 How a purchase actually flows

```
AI buyer: "I want running shoes under ₹3000"
  → search_products("running shoes")          [backend queries catalog + live inventory]
  → check_inventory(variant_id)                [backend returns real stock count]
  → get_shipping_policy / get_return_policy     [backend returns merchant's actual policy]
  → create_checkout(items)                      [backend reserves inventory, computes total]
  → policy engine evaluates: ALLOW / REQUIRE_HUMAN_APPROVAL / REJECT
  → request_payment → Razorpay Test Mode order created
  → buyer pays → Razorpay returns signature
  → backend verifies HMAC signature server-side (never trusts the client's word)
  → mark paid → finalize inventory → confirm order → write immutable audit event
  → agent receives a confirmation + receipt, not a raw claim it invented
```

### 2.2 The failure path is a first-class feature, not an afterthought

```
AI buyer: "I want running shoes"
  → search → check_inventory → create_checkout (stock was available at this point)
  → between checkout and payment, stock drops to 0 (another buyer took it)
  → policy re-validates at payment time → OUT_OF_STOCK
  → checkout → FAILED, no payment ever initiated
  → audit event written explaining exactly why
  → agent receives a rejection + explanation, not a stuck cart or a false charge
```

Most agentic-checkout demos only show the happy path. AgentReady's checkout state machine treats the failure path — stockout, price change, policy rejection, limit exceeded, expired session, invalid intent, payment failure — as states the system is *designed* to land in cleanly, not exceptions that crash the flow.

### 2.3 Checkout state machine

```
CREATED → READY
            ├── policy ALLOW ───────────────────► PAYMENT_PENDING → COMPLETED
            ├── policy REQUIRE_HUMAN_APPROVAL ──► AUTHORIZATION_REQUIRED
            │                                        │ (human approves)
            │                                        ▼
            │                                     AUTHORIZED → PAYMENT_PENDING → COMPLETED
            └── policy REJECT ──────────────────► FAILED

Reachable from most states: EXPIRED (TTL elapsed), CANCELLED,
FAILED (OUT_OF_STOCK | PRICE_CHANGED | POLICY_REJECTED | LIMIT_EXCEEDED |
        INVALID_INTENT | PAYMENT_FAILED)
```

This is a real, backend-owned finite state machine (persisted in `checkout_sessions.status`) — not a status string a route handler mutates freely. State transitions go through `checkout.update_checkout_status`, which validates the transition is legal before applying it.

### 2.4 Policy engine (the actual differentiator)

Every checkout is evaluated against a merchant-configured policy before any payment is attempted:

| Check | What it prevents |
|---|---|
| `max_autonomous_amount` | Agent auto-approving purchases above what the merchant is comfortable with |
| `approval_threshold` | Mid-size purchases route to `REQUIRE_HUMAN_APPROVAL` instead of auto-completing |
| `daily_limit` (enforced against today's completed spend) | An agent structuring one large purchase into several small ones, each individually under threshold |
| `allowed_categories` | Agent buying outside the merchant's intended product scope |
| Purchase-intent validation (AP2-style bounded authorization: max amount, category, expiry, currency) | A stale or over-scoped delegated authorization being reused |
| Currency match | Cross-currency confusion/mismatch |

None of this logic lives in a prompt. It's plain Python, deterministic, testable, and runs entirely server-side — the LLM never sees or influences the decision, it only receives the verdict.

### 2.5 Payment security

- Razorpay order creation happens server-side only, with idempotency (a retried `request_payment` call returns the existing order instead of double-charging).
- Payment verification uses `hmac.compare_digest` (constant-time comparison) against the Razorpay-provided signature — timing-attack-resistant, and the client's claimed payment status is never trusted without this check passing.
- A payment record locks its row (`with_for_update`) during verification so concurrent verification attempts can't race each other.
- Every state change writes an immutable `audit_events` row (`event_type`, `actor`, `payload`, timestamp) — giving a merchant a full forensic trail of what the agent asked for, what the policy engine decided, and what actually happened.

### 2.6 Discovery

`GET /.well-known/agentready?merchant_id={id}` returns a live capability profile — what tools this merchant's gateway exposes, following the same "put a machine-readable manifest at a well-known URL" pattern as `.well-known/mcp` and similar emerging discovery conventions, so an AI buyer platform can figure out what it's allowed to do without hardcoded integration per merchant.

---

## 3. Tech Stack — and why each piece was chosen

| Layer | Choice | Version | Why |
|---|---|---|---|
| Backend framework | **FastAPI** | ≥0.111 | Native async, automatic OpenAPI schema generation (useful for a project whose whole pitch is "machine-readable capability discovery"), Pydantic-based request validation out of the box — every tool call and checkout payload gets schema-validated for free instead of hand-rolled checks. |
| ORM | **SQLAlchemy 2.0** | ≥2.0 | The 2.0 API's typed `Mapped[]` declarative style catches a class of bugs at write-time (wrong column type, wrong nullability) before they become runtime errors — relevant here because money and inventory correctness is the whole point. |
| Migrations | **Alembic** | ≥1.13 | Standard companion to SQLAlchemy; versioned, reversible schema migrations matter when a `checkout_sessions.status` state machine and a `merchant_policies.daily_limit` column are going to keep evolving. |
| Database | **PostgreSQL** (via Supabase in prod, SQLite for local dev) | — | Needed real row-level locking (`SELECT ... FOR UPDATE`) for the payment-verification concurrency guard and the inventory-reservation logic — SQLite doesn't give you that under concurrent load, Postgres does. |
| Validation | **Pydantic v2** | ≥2.7 | Every tool the LLM can call has a typed schema; Pydantic is what turns "the model says it wants to buy X" into "the backend accepts a validated, typed `CheckoutItemCreate`" — this is the actual mechanism behind "the LLM can't fabricate state," not just a design principle in prose. |
| Rate limiting | **slowapi** | ≥0.1.9 | Lightweight FastAPI-native rate limiting — needed once you accept that an LLM-driven client can call your API far more erratically (bursty, retried, occasionally looping) than a human clicking a button. |
| LLM / agent layer | **Google Gemini** (`google-genai` SDK, `gemini-2.5-flash`) | — | Native function-calling support with typed `FunctionDeclaration` schemas maps directly onto the "typed tools only" architecture — the SDK's function-call/function-response message format *is* the mechanism that keeps the model's role to "decide which tool to call," while execution and truth stay server-side. Flash tier chosen for latency/cost on a conversational checkout flow where response time matters more than maximal reasoning depth. |
| Payments | **Razorpay** (Python SDK, Test Mode) | — | The project runs on Razorpay's own test-mode APIs because it's built *for* the Razorpay AI Buildathon — this is the payment rail the track exists to showcase. HMAC-SHA256 order/payment signature verification is Razorpay's documented server-side integrity check, implemented directly rather than trusting client-reported payment status. |
| Frontend framework | **React 19 + TypeScript** | React ^19.2, TS ~6.0 | TypeScript end-to-end (backend has typed Pydantic schemas, frontend has typed props/state) reduces the "the UI displayed a value the API never actually returned" class of bug — again relevant when the UI is showing checkout totals and payment status. |
| Build tool | **Vite** (with Rolldown) | ^8.2 | Fast dev server + build; standard modern choice over CRA/webpack for a React+TS SPA with a hard demo deadline. |
| Styling | **Tailwind CSS** | ^3.4 | Utility-first CSS let the merchant dashboard (KPIs, inventory table, policy editor, CSV import) get built and iterated on quickly without a separate design system to maintain. |
| Charts | **Recharts** | ^3.10 | Used for the dashboard's Revenue/Inventory visualizations — declarative React charting that composes naturally with the rest of the component tree. |
| Routing | **React Router** | ^7.18 | Standard SPA routing for Dashboard / Chat / Checkout views. |
| Linting | **ruff** (backend), **oxlint** (frontend) | — | Both are Rust-based, fast enough to run in a pre-commit/CI loop without friction — chosen over slower Python/JS-native linters (flake8/eslint) specifically so linting doesn't become a step people skip under deadline pressure. |
| Type checking | **mypy** | — | Configured for the backend; currently surfaces ~31 pre-existing errors (mostly `SQLAlchemy Numeric` → `float()` coercion patterns and missing third-party stubs for `google-genai`/`razorpay`) that haven't been cleaned up yet — noted honestly rather than glossed over, see §5. |
| Testing | **pytest** | ≥8.2 | 13 backend tests covering catalog/policy, checkout, health, payment, and policy-engine logic (including daily-limit structuring prevention) — all passing. |
| Backend hosting | **Railway** | — | Simple Docker-based deploy for a FastAPI + Postgres backend without managing infrastructure by hand; fits a buildathon timeline. |
| Frontend hosting | **Vercel** | — | Standard zero-config deploy target for a Vite/React SPA. |

### Why this combination specifically (the "why not X instead" answer)

- **Why not build the checkout flow as an MCP server directly, instead of a custom FastAPI backend?** MCP is the transport/interface layer; it doesn't give you a state machine, a policy engine, or payment-signature verification. The plan is MCP-*compatible* exposure of these same tools later — the typed-tool design already maps cleanly onto MCP's tool-call model — but the authoritative logic still needs to live somewhere, and that's this backend regardless of which transport (raw REST, MCP, ACP-over-MCP) eventually wraps it.
- **Why Gemini and not OpenAI's function calling or Claude's tool use?** Functionally similar typed function-calling capability across all three; Gemini was the pragmatic pick for API access/cost during the buildathon window. The tool layer (`TOOLS` dict + typed schemas in `agent.py`) is written generically enough that swapping the model provider is a matter of rewriting `_gemini_tool_declarations()`/`_extract_function_calls()` for a different SDK's message format, not redesigning the architecture.
- **Why Postgres over a simpler embedded DB for the "real" deployment?** Row-level locking (`with_for_update`) is used in two places that matter for correctness under concurrency: payment verification (so a duplicated webhook/retry can't double-process a payment) and would need to extend to inventory reservation under real concurrent checkout load. That's a Postgres feature, not a SQLite one.
- **Why not a no-SQL/document store for the catalog?** Products, variants, inventory, checkout sessions, orders, and payments are relationally linked with real foreign-key integrity requirements (a checkout item snapshotting a price at a point in time, an order uniquely tied to one checkout) — this is a textbook relational schema, and SQLAlchemy/Postgres is the boring, correct choice over forcing it into a document model.

---

## 4. Effectiveness — what's real vs. what's still a gap

**Solid, verified (tests pass, code reviewed line-by-line):**
- Payment signature verification is genuinely production-grade: constant-time compare, row locking, idempotent on retries, rejects a payment_id switch on an already-linked order.
- Checkout→order→payment idempotency is correct.
- Policy engine (including the daily-limit fix now shipped) closes the "structuring" bypass class.
- Gemini tool-calling loop is now capped (was previously unbounded — a real cost/DoS risk from a runaway or prompt-injected tool-call chain).
- 13/13 backend tests pass, ruff clean, frontend build and lint clean.

**Known, documented gaps:**
- No auth/multi-tenancy yet — `merchant_id` is a trusted header, not authenticated. Explicitly called out in the README as a Phase 1 limitation, not hidden.
- mypy has ~31 pre-existing type errors (Numeric/float coercion patterns, missing stubs) that predate the latest patch and haven't been cleaned up.
- The FINAL_BUILDATHON_REPORT's "quality gate" section previously claimed checks that hadn't actually been run in CI — worth updating that document to reflect the now-verified state rather than the earlier aspirational one.

---

## 5. Competitive / prior-art landscape

This is not a novel problem space, and the report is stronger for saying so plainly:

- **ACP (Agentic Commerce Protocol)** — OpenAI + Stripe (Meta joined later), Apache 2.0, live since Sept 2025, powers ChatGPT's in-chat checkout with real merchants. The 2026-04-17 spec revision added MCP-transport compatibility — meaning "typed checkout tools over MCP," AgentReady's exact architectural bet, is now the direction the biggest reference implementation is also moving.
- **UCP (Universal Commerce Protocol)** — Google/Shopify, protocol-agnostic (REST/MCP/A2A), 20+ retailer endorsements, drives Gemini/AI Mode shopping.
- **AP2** — Google's cross-network bounded-authorization spec; AgentReady's `purchase_intents` table (max amount, category, expiry) is directly modeling the same concept.
- **Razorpay itself** already ships this category commercially: conversational in-chat checkout for Swiggy/Zomato/Zepto with Claude, an agent studio, MCP payment nodes for n8n/Replit/Vercel, native ChatGPT checkout, and voice-first payment pilots — this buildathon track exists because Razorpay is actively building this same thing.

**What this means for the pitch:** leading with "we integrated Gemini + Razorpay for agentic checkout" undersells it — that's table stakes and multiple production systems already do it at scale. The genuine differentiator is the part most demo projects skip: the policy engine, the daily-limit/structuring defense, the immutable audit trail, and the explicit design rule that the LLM never mutates state. That's the part worth spending pitch time on.

---

## 6. Buildathon fit

The Razorpay AI Buildathon is a hiring pipeline, not a scored leaderboard — evaluation is a public GitHub repo, a 5-minute pitch video, and a panel interview where you explain the problem, the architecture, the technical decisions, and what broke and how it got fixed. Given that format:

- **In favor:** a real state machine, real HMAC verification with concurrency handling, a policy engine that goes beyond a single per-order limit, and an audit trail — most entries in this track will have a chatbot that calls a payment API once and stops there.
- **Fixed and verified this session:** daily-limit enforcement (structuring prevention), the unbounded agent tool-call loop, a redundant receipt write, and the Vercel deployment-protection gate that was blocking the live demo link.
- **Still open, and worth having a one-paragraph answer ready for:** why auth/multi-tenancy is out of scope for the demo, and an honest note that the mypy backlog exists and isn't blocking functionality.

---

*Report generated from direct repository inspection (source code, tests, CI output) and current research on ACP/UCP/AP2/x402/UAP and the Razorpay AI Buildathon 2026 program.*
