import { useHealth } from "../hooks/useHealth";

const STATUS_CONFIG = {
  loading: {
    dot: "bg-yellow-400 animate-pulse",
    badge: "bg-yellow-500/10 text-yellow-400 border-yellow-500/30",
    label: "Connecting…",
  },
  ok: {
    dot: "bg-emerald-400",
    badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
    label: "Backend Online",
  },
  error: {
    dot: "bg-red-500",
    badge: "bg-red-500/10 text-red-400 border-red-500/30",
    label: "Backend Offline",
  },
} as const;

export function HealthBadge() {
  const health = useHealth();

  const cfg = STATUS_CONFIG[health.status];

  return (
    <div
      id="health-badge"
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${cfg.badge}`}
      aria-live="polite"
    >
      <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
      <span>{cfg.label}</span>

      {health.status === "ok" && (
        <span className="text-[10px] opacity-60">
          v{health.data.version} · DB {health.data.services.database}
        </span>
      )}
      {health.status === "error" && (
        <span className="text-[10px] opacity-60" title={health.message}>
          {health.message.slice(0, 40)}
        </span>
      )}
    </div>
  );
}
