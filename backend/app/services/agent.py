from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.audit import AuditEventCreate
from app.schemas.checkout import CheckoutItemCreate, CheckoutSessionCreate
from app.services import audit, catalog, checkout, policy

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - depends on runtime package installation
    genai = None
    types = None


def search_products(db: Session, merchant_id: str, query: str):
    products = catalog.search_products_query(db, merchant_id, query)
    return [
        {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "base_price": str(p.base_price),
            "variants": [
                {
                    "id": v.id,
                    "sku": v.sku,
                    "price_override": str(v.price_override) if v.price_override else None,
                    "available_qty": v.inventory.available_qty if v.inventory else 0,
                }
                for v in p.variants
            ],
        }
        for p in products
    ]


def get_product(db: Session, merchant_id: str, sku: str):
    res = catalog.search_products_query(db, merchant_id, sku)
    if res:
        p = res[0]
        return {
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "variants": [
                {
                    "id": v.id,
                    "sku": v.sku,
                    "qty": v.inventory.available_qty if v.inventory else 0,
                }
                for v in p.variants
            ],
        }
    return None


def check_inventory(db: Session, merchant_id: str, variant_id: str):
    from app.models.catalog import ProductVariant

    v = db.query(ProductVariant).filter_by(id=variant_id).first()
    if v and v.inventory:
        return {"variant_id": v.id, "available_qty": v.inventory.available_qty}
    return {"variant_id": variant_id, "available_qty": 0}


def create_checkout(db: Session, merchant_id: str, items: list):
    session_in = CheckoutSessionCreate(
        merchant_id=merchant_id,
        items=[
            CheckoutItemCreate(variant_id=item["variant_id"], quantity=item["quantity"])
            for item in items
        ],
        currency="INR",
    )
    session = checkout.create_checkout(db, merchant_id, session_in)
    return {
        "checkout_id": session.id,
        "status": session.status,
        "total_amount": float(session.total_amount),
    }


def get_checkout(db: Session, merchant_id: str, checkout_id: str):
    session = checkout.get_checkout(db, checkout_id)
    if session:
        return {
            "checkout_id": session.id,
            "status": session.status,
            "total_amount": float(session.total_amount),
        }
    return None


def update_checkout(
    db: Session,
    merchant_id: str,
    checkout_id: str,
    status: str,
    failure_reason: str = None,
):
    try:
        session = checkout.update_checkout_status(db, checkout_id, status, failure_reason)
        return {
            "checkout_id": session.id,
            "status": session.status,
            "failure_reason": session.failure_reason,
        }
    except Exception as e:
        return {"error": str(e)}


def cancel_checkout(db: Session, merchant_id: str, checkout_id: str):
    try:
        session = checkout.update_checkout_status(db, checkout_id, "CANCELLED")
        return {
            "checkout_id": session.id,
            "status": session.status,
        }
    except Exception as e:
        return {"error": str(e)}


def request_payment(db: Session, merchant_id: str, checkout_id: str):
    from app.services import payment

    pay = payment.create_payment_order(db, checkout_id)
    return {
        "payment_id": pay.id,
        "razorpay_order_id": pay.razorpay_order_id,
        "amount": float(pay.amount),
        "status": pay.status,
    }


def get_payment_status(db: Session, merchant_id: str, payment_id: str):
    from app.models.order import Payment

    pay = db.query(Payment).filter_by(id=payment_id).first()
    if pay:
        return {"payment_id": pay.id, "status": pay.status, "amount": float(pay.amount)}
    return None


def get_transaction_audit(db: Session, merchant_id: str, checkout_id: str):
    from app.services import audit

    events = audit.get_checkout_events(db, checkout_id)
    return [
        {
            "event_type": e.event_type,
            "actor": e.actor,
            "timestamp": e.created_at.isoformat(),
            "payload": e.payload,
        }
        for e in events
    ]


def get_shipping_policy(db: Session, merchant_id: str):
    p = policy.get_policy(db, merchant_id)
    return {"max_delivery_days": p.max_delivery_days} if p else None


def get_return_policy(db: Session, merchant_id: str):
    p = policy.get_policy(db, merchant_id)
    return {"min_return_days": p.min_return_days} if p else None


TOOLS = {
    "search_products": search_products,
    "get_product": get_product,
    "check_inventory": check_inventory,
    "get_shipping_policy": get_shipping_policy,
    "get_return_policy": get_return_policy,
    "create_checkout": create_checkout,
    "get_checkout": get_checkout,
    "update_checkout": update_checkout,
    "cancel_checkout": cancel_checkout,
    "request_payment": request_payment,
    "get_payment_status": get_payment_status,
    "get_transaction_audit": get_transaction_audit,
}


def _gemini_tool_declarations():
    if types is None:
        return []

    def string_field(name: str):
        return (name, types.Schema(type=types.Type.STRING))

    def object_field(name: str):
        return (name, types.Schema(type=types.Type.OBJECT))

    return [
        types.FunctionDeclaration(
            name="search_products",
            description="Search the merchant catalog for products by keyword.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"query": types.Schema(type=types.Type.STRING)},
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_product",
            description="Fetch the details of a single product by SKU.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"sku": types.Schema(type=types.Type.STRING)},
                required=["sku"],
            ),
        ),
        types.FunctionDeclaration(
            name="check_inventory",
            description="Check current available inventory for a product variant.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"variant_id": types.Schema(type=types.Type.STRING)},
                required=["variant_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_shipping_policy",
            description="Get the merchant's shipping policy.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
        types.FunctionDeclaration(
            name="get_return_policy",
            description="Get the merchant's return policy.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
        types.FunctionDeclaration(
            name="create_checkout",
            description="Create a checkout session for the provided cart items.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "items": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.OBJECT),
                    )
                },
                required=["items"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_checkout",
            description="Fetch the current state of a checkout session.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"checkout_id": types.Schema(type=types.Type.STRING)},
                required=["checkout_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_checkout",
            description="Update the state of a checkout session (e.g. READY to AUTHORIZED).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "checkout_id": types.Schema(type=types.Type.STRING),
                    "status": types.Schema(type=types.Type.STRING),
                    "failure_reason": types.Schema(type=types.Type.STRING),
                },
                required=["checkout_id", "status"],
            ),
        ),
        types.FunctionDeclaration(
            name="cancel_checkout",
            description="Cancel an existing checkout session.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"checkout_id": types.Schema(type=types.Type.STRING)},
                required=["checkout_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="request_payment",
            description="Create a payment order for an authorized checkout.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"checkout_id": types.Schema(type=types.Type.STRING)},
                required=["checkout_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_payment_status",
            description="Lookup the status of a payment by payment ID.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"payment_id": types.Schema(type=types.Type.STRING)},
                required=["payment_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_transaction_audit",
            description="Fetch the audit timeline for a checkout transaction.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={"checkout_id": types.Schema(type=types.Type.STRING)},
                required=["checkout_id"],
            ),
        ),
    ]


def _to_gemini_contents(messages: list):
    contents: list[types.Content] = []
    for message in messages:
        role = getattr(message, "role", None)
        if isinstance(message, dict):
            role = message.get("role")

        content = getattr(message, "content", None)
        if isinstance(message, dict):
            content = message.get("content")

        if content is None:
            continue

        normalized_role = str(role or "user").lower()
        if normalized_role == "assistant":
            normalized_role = "model"
        elif normalized_role not in {"user", "model"}:
            normalized_role = "user"

        contents.append(
            types.Content(
                role=normalized_role,
                parts=[types.Part.from_text(str(content))],
            )
        )
    return contents


def _extract_function_calls(response):
    calls: list[dict[str, Any]] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", []) or []:
            function_call = getattr(part, "function_call", None)
            if function_call is None:
                continue
            call_name = getattr(function_call, "name", None)
            if not call_name:
                continue
            call_args = getattr(function_call, "args", {}) or {}
            if not isinstance(call_args, dict):
                call_args = dict(call_args)
            calls.append({"name": call_name, "arguments": call_args})
    return calls


def _extract_text(response) -> str:
    reply_parts: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                reply_parts.append(text)
    return "".join(reply_parts).strip()


def handle_chat(db: Session, merchant_id: str, messages: list):
    if not settings.GEMINI_API_KEY:
        return "Gemini API key not set. Please configure GEMINI_API_KEY.", []

    if genai is None or types is None:
        return (
            "google-genai SDK is not installed. "
            "Install google-genai to enable native Gemini function calling.",
            [],
        )

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    tools_config = types.GenerateContentConfig(
        tools=[types.Tool(function_declarations=_gemini_tool_declarations())]
    )

    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        contents = _to_gemini_contents(messages)
        
        audit.log_event(
            db,
            merchant_id,
            AuditEventCreate(
                event_type="AGENT_CONVERSATION",
                actor="user",
                payload={"messages_count": len(messages)},
            )
        )

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=tools_config,
        )
    except Exception as exc:  # pragma: no cover - runtime external call
        return f"Gemini API call failed: {exc}", []

    executed: list[dict[str, Any]] = []
    max_tool_rounds = getattr(settings, "MAX_AGENT_TOOL_ROUNDS", 8)
    for _round in range(max_tool_rounds):
        calls = _extract_function_calls(response)
        if not calls:
            break

        for call in calls:
            call_name = call["name"]
            call_args = call["arguments"]
            result = None
            if call_name in TOOLS:
                try:
                    result = TOOLS[call_name](db, merchant_id, **call_args)
                except TypeError:
                    result = TOOLS[call_name](db, merchant_id, call_args)
                except Exception as exc:  # pragma: no cover - runtime error
                    result = {"error": str(exc)}
            executed.append({"name": call_name, "arguments": call_args, "result": result})

            function_response_part = types.Part.from_function_response(
                name=call_name,
                response={"result": result},
            )
            function_call_part = types.Part.from_function_call(
                name=call_name,
                args=call_args,
            )
            contents = contents + [
                types.Content(role="model", parts=[function_call_part]),
                types.Content(role="user", parts=[function_response_part]),
            ]

        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=tools_config,
            )
        except Exception as exc:  # pragma: no cover - runtime external call
            return f"Gemini API call failed: {exc}", executed

    final_reply = _extract_text(response)
    if not final_reply:
        if _extract_function_calls(response):
            final_reply = (
                "I wasn't able to finish this request within the allowed number of "
                "tool calls. Please narrow your request or try again."
            )
        else:
            final_reply = "I couldn’t determine a response from Gemini."
    return final_reply, executed
