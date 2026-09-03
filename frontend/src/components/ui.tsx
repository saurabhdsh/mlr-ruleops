import { ReactNode } from "react";
import { pill } from "../utils/format";

export function Page({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-ink-600 bg-ink-950/90 backdrop-blur px-8 py-4 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">{title}</h1>
          {subtitle && <p className="text-sm text-mist-500 mt-0.5">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2">{actions}</div>
      </header>
      <div className="px-8 py-6">{children}</div>
    </div>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`border border-ink-600 bg-ink-900 ${className}`}>
      {title && (
        <div className="px-4 py-2.5 border-b border-ink-600 text-[11px] uppercase tracking-[0.16em] text-mist-500">
          {title}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Badge({ children, status }: { children: ReactNode; status?: string }) {
  return <span className={`inline-flex px-2 py-0.5 text-[11px] uppercase tracking-wide ${pill(status)}`}>{children}</span>;
}

export function Metric({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="border border-ink-600 bg-ink-900 px-4 py-3">
      <div className="text-[11px] uppercase tracking-[0.16em] text-mist-500">{label}</div>
      <div className="text-2xl font-medium mt-1 tabular-nums">{value}</div>
      {hint && <div className="text-[11px] text-mist-500 mt-1">{hint}</div>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  type?: "button" | "submit";
}) {
  const cls =
    variant === "primary"
      ? "bg-brass-500 text-ink-950"
      : variant === "danger"
        ? "border border-fail/40 text-fail"
        : "border border-ink-600 text-mist-300";
  return (
    <button type={type} disabled={disabled} onClick={onClick} className={`px-3 py-1.5 text-sm disabled:opacity-50 ${cls}`}>
      {children}
    </button>
  );
}
