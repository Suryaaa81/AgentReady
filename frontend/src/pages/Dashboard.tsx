import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertCircle,
  ArrowUpRight,
  CircleDollarSign,
  FileUp,
  Inbox,
  PackageSearch,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { api } from "../lib/api";

const MERCHANT_ID = "00000000-0000-4000-a000-000000000000";

type ProductVariant = {
  id: string;
  sku: string;
  available_qty?: number;
  price_override?: number | string | null;
};

type Product = {
  id: string;
  name: string;
  sku: string;
  category?: string;
  base_price?: number | string;
  variants: ProductVariant[];
};

type Policy = Record<string, string | number | null | boolean | undefined> & {
  id?: string;
  merchant_id?: string;
  max_autonomous_amount?: number;
  daily_limit?: number;
  max_delivery_days?: number;
  min_return_days?: number;
};

type TimelineEvent = {
  id: string;
  event_type: string;
  created_at: string;
  actor?: string;
  payload?: Record<string, unknown>;
};

const currencyFormatter = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 0,
});

const formatCurrency = (value: number) => currencyFormatter.format(value);

const formatDate = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

function Dashboard() {
  const [products, setProducts] = useState<Product[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "healthy" | "low">("all");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [prods, tl, pol] = await Promise.all([
        api.getProducts(MERCHANT_ID).catch(() => []),
        api.getMerchantTimeline(MERCHANT_ID).catch(() => []),
        api.getPolicy(MERCHANT_ID).catch(() => null),
      ]);
      setProducts(prods);
      setTimeline(tl);
      setPolicy(pol);
    } catch {
      setError("Unable to load merchant data. Please retry.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const filteredProducts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return products.filter((product) => {
      const matchesQuery =
        query.length === 0 ||
        product.name.toLowerCase().includes(query) ||
        product.sku.toLowerCase().includes(query) ||
        product.category?.toLowerCase().includes(query);

      const hasLowStock = (product.variants ?? []).some(
        (variant) => Number(variant.available_qty ?? 0) <= 5,
      );
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "healthy" && !hasLowStock) ||
        (statusFilter === "low" && hasLowStock);

      return matchesQuery && matchesStatus;
    });
  }, [products, search, statusFilter]);

  const inventoryTotal = useMemo(
    () =>
      products.reduce(
        (sum, product) =>
          sum +
          (product.variants ?? []).reduce(
            (variantSum, variant) => variantSum + Number(variant.available_qty ?? 0),
            0,
          ),
        0,
      ),
    [products],
  );

  const revenueKPI = useMemo(
    () =>
      timeline.reduce((sum, event) => {
        const payloadAmount = Number((event.payload as Record<string, unknown> | undefined)?.amount ?? 0);
        return event.event_type === "PAYMENT_COMPLETED" && payloadAmount > 0
          ? sum + payloadAmount
          : sum;
      }, 0),
    [timeline],
  );

  const ordersKPI = useMemo(
    () => timeline.filter((event) => event.event_type === "PAYMENT_COMPLETED").length,
    [timeline],
  );

  const approvalEvents = useMemo(
    () =>
      timeline.filter(
        (event) =>
          /(policy|authorization|approval)/i.test(event.event_type) ||
          /(approved|authorized)/i.test(event.event_type),
      ),
    [timeline],
  );

  const approvalRate = useMemo(() => {
    if (approvalEvents.length === 0) return 0;
    const approvals = approvalEvents.filter(
      (event) =>
        event.event_type.includes("APPROVED") || event.event_type.includes("AUTHORIZED"),
    ).length;
    return Math.round((approvals / approvalEvents.length) * 100);
  }, [approvalEvents]);

  const analyticsData = useMemo(() => {
    const map = new Map<string, number>();

    timeline
      .filter((event) => event.event_type === "PAYMENT_COMPLETED")
      .forEach((event) => {
        const amount = Number((event.payload as Record<string, unknown> | undefined)?.amount ?? 0);
        if (amount <= 0) return;
        const dateKey = new Date(event.created_at).toLocaleDateString("en-CA", {
          month: "short",
          day: "numeric",
        });
        map.set(dateKey, (map.get(dateKey) ?? 0) + amount);
      });

    return Array.from(map.entries()).map(([date, revenue]) => ({ date, revenue }));
  }, [timeline]);

  const recentTransactions = useMemo(
    () =>
      timeline
        .filter((event) => event.event_type === "PAYMENT_COMPLETED")
        .slice(0, 6)
        .map((event) => ({
          id: event.id,
          date: formatDate(event.created_at),
          amount: Number((event.payload as Record<string, unknown> | undefined)?.amount ?? 0),
          status: "Paid",
        })),
    [timeline],
  );

  const handleFileSelection = (fileList: FileList | null) => {
    const nextFile = fileList?.[0] ?? null;
    setSelectedFile(nextFile);
    setNotice(nextFile ? `Ready to import ${nextFile.name}` : null);
  };

  const handleImport = async () => {
    if (!selectedFile) return;

    try {
      setUploadProgress(10);
      await api.importCatalog(MERCHANT_ID, selectedFile);
      setUploadProgress(65);
      await refresh();
      setUploadProgress(100);
      setNotice(`Imported ${selectedFile.name} successfully.`);
      setSelectedFile(null);
      setTimeout(() => setUploadProgress(0), 1000);
    } catch {
      setError("Catalog import failed. Please check the CSV format and try again.");
      setUploadProgress(0);
    }
  };

  const savePolicy = async () => {
    if (!policy) return;

    try {
      await api.updatePolicy(MERCHANT_ID, policy);
      setNotice("Merchant policy saved successfully.");
      setError(null);
    } catch {
      setError("Failed to save merchant policy.");
    }
  };

  const isEmptyState = !loading && !error && products.length === 0;

  if (loading) {
    return (
      <div className="dashboard-shell">
        <div className="dashboard-grid dashboard-skeletons">
          {[...Array(4)].map((_, index) => (
            <div key={index} className="card skeleton-card" />
          ))}
        </div>
        <div className="content-grid">
          <div className="card skeleton-card tall" />
          <div className="card skeleton-card tall" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard-shell">
        <div className="card empty-state">
          <AlertCircle size={32} className="text-amber-400" />
          <h3>Data unavailable</h3>
          <p>{error}</p>
          <button className="primary-button" onClick={() => void refresh()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-shell">
      <header className="hero-card">
        <div>
          <p className="eyebrow">Merchant command center</p>
          <h1>Operations overview</h1>
        </div>
        <div className="chip-row">
          <span className="status-chip success">Live</span>
          <span className="status-chip neutral">Razorpay Test Mode</span>
        </div>
      </header>

      {notice && <div className="alert-banner success">{notice}</div>}

      <section className="kpi-grid">
        <div className="metric-card accent-blue">
          <div className="metric-header">
            <span>Revenue</span>
            <CircleDollarSign size={18} />
          </div>
          <strong>{formatCurrency(revenueKPI)}</strong>
          <small>Gross volume</small>
        </div>

        <div className="metric-card accent-violet">
          <div className="metric-header">
            <span>Orders</span>
            <ShoppingCart size={18} />
          </div>
          <strong>{ordersKPI}</strong>
          <small>Completed checkout orders</small>
        </div>

        <div className="metric-card accent-emerald">
          <div className="metric-header">
            <span>Inventory</span>
            <PackageSearch size={18} />
          </div>
          <strong>{inventoryTotal}</strong>
          <small>Units currently live</small>
        </div>

        <div className="metric-card accent-amber">
          <div className="metric-header">
            <span>AI Approval Rate</span>
            <ShieldCheck size={18} />
          </div>
          <strong>{approvalRate}%</strong>
          <small>Policy and agent confidence</small>
        </div>
      </section>

      <section className="analytics-grid">
        <div className="card chart-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Revenue</p>
              <h2>Sales trend</h2>
            </div>
            <TrendingUp size={18} className="icon-accent" />
          </div>
          <div className="chart-wrap">
            {analyticsData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analyticsData}>
                  <defs>
                    <linearGradient id="revenueFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#60a5fa" stopOpacity={0.7} />
                      <stop offset="95%" stopColor="#60a5fa" stopOpacity={0.08} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis dataKey="date" stroke="#94a3b8" tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} />
                  <Tooltip
                   formatter={(value) => [formatCurrency(Number(value ?? 0)), "Revenue"]}
                    labelStyle={{ color: "#0f172a" }}
                  />
                  <Area type="monotone" dataKey="revenue" stroke="#60a5fa" fill="url(#revenueFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No transaction data available.</div>
            )}
          </div>
        </div>

        <div className="card chart-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Inventory</p>
              <h2>Stock mix</h2>
            </div>
            <Sparkles size={18} className="icon-accent" />
          </div>
          <div className="chart-wrap">
            {products.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={products.slice(0, 5)}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
                  <XAxis dataKey="sku" stroke="#94a3b8" tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} />
                  <Tooltip formatter={(value) => [Number(value ?? 0), "Units"]} />
                  <Bar
                    dataKey={(product: Product) =>
                      (product.variants ?? []).reduce(
                        (sum: number, variant: ProductVariant) =>
                          sum + Number(variant.available_qty ?? 0),
                        0,
                      )
                    }
                    fill="#34d399"
                    radius={[8, 8, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="chart-empty">No inventory loaded.</div>
            )}
          </div>
        </div>
      </section>

      <section className="content-grid">
        <div className="card inventory-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Catalog</p>
              <h2>Inventory management</h2>
            </div>
            <button className="primary-button small-button" onClick={() => void refresh()}>
              Refresh
            </button>
          </div>

          <div className="toolbar-row">
            <div className="search-input-wrap">
              <PackageSearch size={16} />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search by name, SKU, category"
              />
            </div>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "healthy" | "low")}>
              <option value="all">All inventory</option>
              <option value="healthy">Healthy</option>
              <option value="low">Low stock</option>
            </select>
          </div>

          {filteredProducts.length === 0 ? (
            <div className="empty-list">
              <Inbox size={22} />
              <span>No products match your search.</span>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>SKU</th>
                    <th>Price</th>
                    <th>Inventory</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredProducts.map((product) => {
                    const variantTotal = (product.variants ?? []).reduce(
                      (sum, variant) => sum + Number(variant.available_qty ?? 0),
                      0,
                    );
                    const lowStock = variantTotal <= 5;

                    return (
                      <tr key={product.id}>
                        <td>{product.name}</td>
                        <td>{product.sku}</td>
                        <td>{formatCurrency(Number(product.base_price ?? 0))}</td>
                        <td>{variantTotal}</td>
                        <td>
                          <span className={lowStock ? "pill danger" : "pill success"}>
                            {lowStock ? "Low stock" : "Healthy"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card side-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Import</p>
              <h2>Catalog upload</h2>
            </div>
            <FileUp size={18} className="icon-accent" />
          </div>

          <div
            className={isDragging ? "upload-zone active" : "upload-zone"}
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              handleFileSelection(event.dataTransfer.files);
            }}
          >
            <FileUp size={28} />
            <p>{selectedFile ? selectedFile.name : "Drag and drop a CSV file"}</p>
            <label className="upload-button">
              <input
                type="file"
                accept=".csv"
                onChange={(event) => handleFileSelection(event.target.files)}
              />
              Browse files
            </label>
          </div>

          {uploadProgress > 0 && (
            <div className="progress-block">
              <div className="progress-meta">
                <span>Uploading</span>
                <strong>{uploadProgress}%</strong>
              </div>
              <div className="progress-track">
                <span style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          )}

          <button className="primary-button" onClick={() => void handleImport()} disabled={!selectedFile}>
            Import catalog
          </button>
        </div>
      </section>

      <section className="content-grid bottom-grid">
        <div className="card policy-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Policies</p>
              <h2>Merchant policy editor</h2>
            </div>
            <ShieldCheck size={18} className="icon-accent" />
          </div>

          {policy ? (
            <div className="policy-grid">
              <label>
                <span>Max autonomous amount</span>
                <input
                  type="number"
                  value={policy.max_autonomous_amount ?? ""}
                  onChange={(event) =>
                    setPolicy({
                      ...policy,
                      max_autonomous_amount: Number(event.target.value),
                    })
                  }
                />
              </label>
              <label>
                <span>Daily limit</span>
                <input
                  type="number"
                  value={policy.daily_limit ?? ""}
                  onChange={(event) =>
                    setPolicy({ ...policy, daily_limit: Number(event.target.value) })
                  }
                />
              </label>
              <label>
                <span>Max delivery days</span>
                <input
                  type="number"
                  value={policy.max_delivery_days ?? ""}
                  onChange={(event) =>
                    setPolicy({ ...policy, max_delivery_days: Number(event.target.value) })
                  }
                />
              </label>
              <label>
                <span>Min return days</span>
                <input
                  type="number"
                  value={policy.min_return_days ?? ""}
                  onChange={(event) =>
                    setPolicy({ ...policy, min_return_days: Number(event.target.value) })
                  }
                />
              </label>
              <div className="policy-actions">
                <button className="primary-button" onClick={() => void savePolicy()}>
                  Save policy
                </button>
              </div>
            </div>
          ) : (
            <div className="empty-state compact">
              <ShieldCheck size={28} className="text-sky-400" />
              <p>Policy data is not available yet.</p>
            </div>
          )}
        </div>

        <div className="card transactions-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Activity</p>
              <h2>Recent transactions</h2>
            </div>
            <ArrowUpRight size={18} className="icon-accent" />
          </div>

          {recentTransactions.length === 0 ? (
            <div className="empty-state compact">
              <ShoppingCart size={28} className="text-emerald-400" />
              <p>No recent transactions.</p>
            </div>
          ) : (
            <div className="transactions-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Order</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {recentTransactions.map((transaction) => (
                    <tr key={transaction.id}>
                      <td>{transaction.id.slice(0, 8)}</td>
                      <td>{transaction.date}</td>
                      <td>
                        <span className="pill success">{transaction.status}</span>
                      </td>
                      <td>{formatCurrency(transaction.amount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>

      {isEmptyState && (
        <div className="card empty-state">
          <Inbox size={32} className="text-slate-400" />
          <h3>No catalog data loaded</h3>
          <p>Import your first CSV to populate the merchant dashboard.</p>
        </div>
      )}
    </div>
  );
}

export default Dashboard;
