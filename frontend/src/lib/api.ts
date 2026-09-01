/**
 * Typed API client for the AgentReady backend.
 *
 * Base URL:  VITE_API_URL      (default http://localhost:8000)
 * Auth key:  VITE_MERCHANT_API_KEY — obtained once from POST /merchant/register
 *            (see scripts/seed_demo.py, or the backend README).
 *
 * The API key identifies the merchant server-side; it is never derived
 * from anything the client claims. Every authenticated call sends it as
 * the `X-API-Key` header.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const API_KEY = import.meta.env.VITE_MERCHANT_API_KEY ?? "";

export interface HealthResponse {
  status: "ok" | "degraded";
  timestamp: string;
  version: string;
  phase: number;
  services: {
    database: "ok" | "error";
    database_error?: string;
  };
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { ...headers, ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: (): Promise<HealthResponse> => apiFetch<HealthResponse>("/health"),

  // Merchant
  register: (name: string, email: string): Promise<any> =>
    apiFetch("/merchant/register", { method: "POST", body: JSON.stringify({ name, email }) }),

  // Catalog
  getProducts: (): Promise<any[]> => apiFetch("/catalog/products"),
  importCatalog: (file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("file", file);
    return apiFetch("/catalog/import", { method: "POST", body: formData });
  },

  // Policy
  getPolicy: (): Promise<any> => apiFetch("/merchant/policies"),
  updatePolicy: (policy: any): Promise<any> =>
    apiFetch("/merchant/policies", { method: "PUT", body: JSON.stringify(policy) }),

  // Checkout — no auth needed for get/authorize: checkout_id itself is the
  // bearer capability an AI buyer polls with (see backend/app/routers/checkout.py)
  createCheckout: (items: any[]): Promise<any> =>
    apiFetch("/checkout/sessions", { method: "POST", body: JSON.stringify({ items, currency: "INR" }) }),
  getCheckout: (checkoutId: string): Promise<any> => apiFetch(`/checkout/sessions/${checkoutId}`),
  authorizeCheckout: (checkoutId: string): Promise<any> =>
    apiFetch(`/checkout/sessions/${checkoutId}/authorize`, { method: "POST" }),

  // Agent
  chat: (messages: any[]): Promise<any> =>
    apiFetch("/agent/chat", { method: "POST", body: JSON.stringify({ messages }) }),

  // Payment
  createPayment: (checkoutId: string): Promise<any> =>
    apiFetch("/payment/order", { method: "POST", body: JSON.stringify({ checkout_id: checkoutId }) }),
  verifyPayment: (data: any): Promise<any> =>
    apiFetch("/payment/verify", { method: "POST", body: JSON.stringify(data) }),

  // Audit
  getMerchantTimeline: (): Promise<any[]> => apiFetch("/audit/merchant"),
  getMetrics: (): Promise<any> => apiFetch("/audit/metrics"),
};
