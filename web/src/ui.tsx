import { ReactNode } from "react";

const tones: Record<string, string> = {
  green: "bg-green-100 text-green-800", red: "bg-red-100 text-red-800", amber: "bg-amber-100 text-amber-800",
  slate: "bg-slate-100 text-slate-700", blue: "bg-blue-100 text-blue-800",
};
const statusTone: Record<string, string> = {
  verified: "green", succeeded: "green", approved: "green", valid: "green", running: "blue", queued: "slate", pending: "amber",
  unverified: "amber", catch_all: "amber", failed: "red", bounced: "red", opted_out: "red", rejected: "red", cancelled: "slate",
};

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const t = tone ?? statusTone[String(children)] ?? "slate";
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${tones[t]}`}>{children}</span>;
}

export function ConfBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-green-500" : value >= 40 ? "bg-amber-500" : "bg-red-400";
  return (
    <div className="flex items-center gap-2" title={`confidence ${value}`}>
      <div className="h-2 w-20 rounded bg-slate-200"><div className={`h-2 rounded ${color}`} style={{ width: `${value}%` }} /></div>
      <span className="text-xs tabular-nums">{value}</span>
    </div>
  );
}

export function Button({ tone = "default", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "default" | "danger" | "primary" }) {
  const c = { default: "bg-white border-slate-300 hover:bg-slate-100", primary: "bg-blue-600 text-white border-blue-600 hover:bg-blue-700", danger: "bg-red-600 text-white border-red-600 hover:bg-red-700" }[tone];
  return <button {...p} className={`rounded border px-3 py-1 text-sm disabled:opacity-50 ${c} ${p.className ?? ""}`} />;
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded border border-slate-200 bg-white p-4 ${className}`}>
      {title && <h3 className="mb-2 text-sm font-semibold text-slate-600">{title}</h3>}
      {children}
    </section>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md rounded bg-white p-5 shadow-lg" onClick={(e) => e.stopPropagation()}>
        <h2 className="mb-3 text-lg font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return error ? <p className="my-2 rounded bg-red-50 p-2 text-sm text-red-700">{String((error as Error).message ?? error)}</p> : null;
}

export const th = "px-3 py-2 text-left text-xs font-semibold uppercase text-slate-500";
export const td = "px-3 py-2 text-sm";
export const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString() : "—");
