import { useState, useEffect } from "react";
import { api } from "../lib/api";

const MERCHANT_ID = "00000000-0000-4000-a000-000000000000"; // Mock merchant

export default function Dashboard() {
  const [products, setProducts] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [policy, setPolicy] = useState<any>(null);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    const prods = await api.getProducts(MERCHANT_ID).catch(() => []);
    setProducts(prods);
    const tl = await api.getMerchantTimeline(MERCHANT_ID).catch(() => []);
    setTimeline(tl);
    const pol = await api.getPolicy(MERCHANT_ID).catch(() => null);
    setPolicy(pol);
  }

  const handleUpload = async () => {
    if (!file) return;
    try {
      setUploadProgress(10);
      await api.importCatalog(MERCHANT_ID, file);
      setUploadProgress(70);
      const updated = await api.getProducts(MERCHANT_ID);
      setProducts(updated);
      setUploadProgress(100);
      setTimeout(()=>setUploadProgress(0), 1200);
      alert("Catalog imported successfully");
    } catch (e) {
      console.error(e);
      setUploadProgress(0);
      alert("Import failed");
    }
  };

  const savePolicy = async () => {
    if (!policy) return;
    try {
      await api.updatePolicy(MERCHANT_ID, policy);
      alert("Policy updated");
    } catch (e) {
      console.error(e);
      alert("Failed to update policy");
    }
  };

  const revenueKPI = timeline.reduce((acc, e) => e.event_type === "PAYMENT_COMPLETED" && e.payload?.amount ? acc + Number(e.payload.amount) : acc, 0);
  const ordersKPI = timeline.filter(e => e.event_type === "PAYMENT_COMPLETED").length;
  const inventoryKPI = products.reduce((acc, p) => acc + p.variants.reduce((s:any, v:any)=> s + (v.available_qty||0),0), 0);
  const policyApprovalKPI = policy ? (policy.approval_threshold ? 1 : 0) : 0;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      <h1 className="text-3xl font-bold">Merchant Dashboard</h1>

      <section className="grid grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded shadow">
          <div className="text-sm text-gray-500">Revenue (since inception)</div>
          <div className="text-2xl font-semibold">₹{revenueKPI.toFixed(2)}</div>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <div className="text-sm text-gray-500">Orders</div>
          <div className="text-2xl font-semibold">{ordersKPI}</div>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <div className="text-sm text-gray-500">Inventory</div>
          <div className="text-2xl font-semibold">{inventoryKPI}</div>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <div className="text-sm text-gray-500">Policy Approvals Needed</div>
          <div className="text-2xl font-semibold">{policyApprovalKPI}</div>
        </div>
      </section>

      <section className="bg-white p-6 rounded-lg shadow space-y-4">
        <h2 className="text-xl font-semibold">Catalog Import</h2>
        <div className="flex gap-4 items-center">
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} className="border p-2" />
          <button onClick={handleUpload} className="bg-blue-600 text-white px-4 py-2 rounded">Import CSV</button>
          {uploadProgress > 0 && (
            <div className="w-48 bg-gray-100 rounded overflow-hidden">
              <div className="h-2 bg-green-500" style={{ width: `${uploadProgress}%` }} />
            </div>
          )}
        </div>
      </section>

      <div className="grid grid-cols-2 gap-8">
        <section className="bg-white p-6 rounded-lg shadow space-y-4">
          <h2 className="text-xl font-semibold">Products ({products.length})</h2>
          <ul className="space-y-2">
            {products.map(p => (
              <li key={p.id} className="border p-3 rounded">
                <div className="font-medium">{p.name} ({p.sku})</div>
                <div className="text-sm text-gray-500">{p.variants.length} variants • Base Price: ₹{p.base_price}</div>
                <div className="mt-2">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-600"><th>Variant SKU</th><th>Price</th><th>Available</th></tr>
                    </thead>
                    <tbody>
                      {p.variants.map((v:any)=> (
                        <tr key={v.id}><td>{v.sku}</td><td>₹{v.price_override || p.base_price}</td><td>{v.available_qty}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <section className="bg-white p-6 rounded-lg shadow space-y-4">
          <h2 className="text-xl font-semibold">Audit Timeline</h2>
          <div className="max-h-96 overflow-y-auto space-y-2">
            {timeline.map(e => {
              const icon = e.event_type.includes("PAYMENT") ? "💳" : e.event_type.includes("CHECKOUT") ? "🧾" : "🔔";
              const explanation = e.event_type === "PAYMENT_COMPLETED" ? `Payment captured: ₹${e.payload?.amount || ''}` : e.event_type === "CHECKOUT_CREATED" ? `Checkout created (${e.payload?.checkout_id || ''})` : e.event_type;
              return (
                <div key={e.id} className="flex gap-3 items-start border-l-4 border-blue-500 pl-3 py-1">
                  <div className="text-2xl">{icon}</div>
                  <div>
                    <div className="text-sm font-semibold">{e.event_type}</div>
                    <div className="text-xs text-gray-500">{new Date(e.created_at).toLocaleString()}</div>
                    <div className="text-sm">{explanation}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      </div>

      <section className="bg-white p-6 rounded-lg shadow space-y-4">
        <h2 className="text-xl font-semibold">Policy Editor</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="block text-sm text-gray-600">Max Autonomous Amount</label>
            <input type="number" value={policy?.max_autonomous_amount || ""} onChange={(e)=> setPolicy({...policy, max_autonomous_amount: Number(e.target.value)})} className="border p-2 w-full" />
          </div>
          <div>
            <label className="block text-sm text-gray-600">Daily Limit</label>
            <input type="number" value={policy?.daily_limit || ""} onChange={(e)=> setPolicy({...policy, daily_limit: Number(e.target.value)})} className="border p-2 w-full" />
          </div>
          <div className="flex items-end">
            <button onClick={savePolicy} className="bg-green-600 text-white px-4 py-2 rounded">Save Policy</button>
          </div>
        </div>
      </section>
    </div>
  );
}
                <div className="text-sm font-semibold">{e.event_type}</div>
                <div className="text-xs text-gray-500">{new Date(e.created_at).toLocaleString()}</div>
                <pre className="text-xs bg-gray-50 p-1 mt-1 rounded overflow-x-auto">
                  {JSON.stringify(e.payload, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
