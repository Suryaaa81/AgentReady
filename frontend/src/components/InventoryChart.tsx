import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

type Variant = { available_qty?: number };
type Product = { sku: string; variants?: Variant[] };

export default function InventoryChart({ products }: { products: Product[] }) {
  const data = products.slice(0, 5).map((p) => ({
    sku: p.sku,
    units: (p.variants ?? []).reduce((sum, v) => sum + Number(v.available_qty ?? 0), 0),
  }));

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
          <XAxis dataKey="sku" stroke="#94a3b8" tickLine={false} axisLine={false} />
          <YAxis stroke="#94a3b8" tickLine={false} axisLine={false} />
          <Tooltip formatter={(value) => [Number(value ?? 0), 'Units']} />
          <Bar dataKey="units" fill="#34d399" radius={[8, 8, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
