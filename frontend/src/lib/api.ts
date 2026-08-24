/**
 * Typed API client for the AgentReady backend.
 * Base URL is set via VITE_API_URL environment variable.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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
  
  // Catalog
  getProducts: (merchantId: string): Promise<any[]> => apiFetch(`/catalog/products?merchant_id=${merchantId}`),
  importCatalog: (merchantId: string, file: File): Promise<any> => {
    const formData = new FormData();
    formData.append("merchant_id", merchantId);
    formData.append("file", file);
    return apiFetch("/catalog/import", { method: "POST", body: formData });
  },

  // Policy
  getPolicy: (merchantId: string): Promise<any> => apiFetch(`/merchant/policies?merchant_id=${merchantId}`),
  updatePolicy: (merchantId: string, policy: any): Promise<any> => 
    apiFetch(`/merchant/policies?merchant_id=${merchantId}`, { method: "PUT", body: JSON.stringify(policy) }),

  // Checkout
  createCheckout: (merchantId: string, items: any[]): Promise<any> =>
    apiFetch(`/checkout/sessions?merchant_id=${merchantId}`, { method: "POST", body: JSON.stringify({ merchant_id: merchantId, items, currency: "INR" }) }),
  getCheckout: (checkoutId: string): Promise<any> => apiFetch(`/checkout/sessions/${checkoutId}`),
  authorizeCheckout: (checkoutId: string): Promise<any> => apiFetch(`/checkout/sessions/${checkoutId}/authorize`, { method: "POST" }),
  
  // Agent
  chat: (merchantId: string, messages: any[]): Promise<any> => 
    apiFetch(`/agent/chat`, { method: "POST", body: JSON.stringify({ merchant_id: merchantId, messages }) }),
    
  // Payment
  createPayment: (checkoutId: string): Promise<any> => 
    apiFetch(`/payment/order`, { method: "POST", body: JSON.stringify({ checkout_id: checkoutId }) }),
  verifyPayment: (data: any): Promise<any> => 
    apiFetch(`/payment/verify`, { method: "POST", body: JSON.stringify(data) }),
    
  // Audit
  getMerchantTimeline: (merchantId: string): Promise<any[]> => apiFetch(`/audit/merchant?merchant_id=${merchantId}`),
};
