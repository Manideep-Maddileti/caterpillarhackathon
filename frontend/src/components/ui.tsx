import type { ReactNode } from "react";

export function Card({
  children, className = "", onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
}) {
  return (
    <div className={`bg-white rounded-xl border border-stone-200 shadow-sm ${className}`} onClick={onClick}>
      {children}
    </div>
  );
}

export function StatCard({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <Card className="p-4 border-t-2 border-t-brand-500">
      <p className="text-xs font-medium uppercase tracking-wide text-stone-500">{label}</p>
      <p className="text-2xl font-semibold text-stone-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-stone-400 mt-1">{sub}</p>}
    </Card>
  );
}

const STATUS_STYLES: Record<string, string> = {
  available: "bg-emerald-100 text-emerald-700",
  rented: "bg-sky-100 text-sky-700",
  overdue: "bg-red-100 text-red-700",
  maintenance: "bg-orange-100 text-orange-700",
  created: "bg-stone-100 text-stone-700",
  active: "bg-sky-100 text-sky-700",
  completed: "bg-emerald-100 text-emerald-700",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-stone-100 text-stone-700";
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${style}`}>
      {status.replace("_", " ")}
    </span>
  );
}

const SEVERITY_STYLES: Record<string, string> = {
  critical: "bg-red-50 border-red-200 text-red-800",
  warning: "bg-orange-50 border-orange-200 text-orange-800",
  info: "bg-stone-50 border-stone-200 text-stone-800",
};

export function SeverityPill({ severity }: { severity: string }) {
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium border ${SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.info}`}>
      {severity}
    </span>
  );
}

export function Button({
  children, onClick, variant = "primary", disabled, className = "", type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "secondary" | "danger";
  disabled?: boolean;
  className?: string;
  type?: "button" | "submit";
}) {
  const variants = {
    primary: "bg-brand-500 text-stone-900 font-semibold hover:bg-brand-400 shadow-sm shadow-brand-900/10",
    secondary: "bg-stone-100 text-stone-700 hover:bg-stone-200",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
    >
      {children}
    </button>
  );
}
