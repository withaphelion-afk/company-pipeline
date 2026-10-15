import { ReactNode } from "react";
import { BANNER_DANGER, BTN_DANGER, BTN_PRIMARY, BTN_QUIET, EYEBROW, H2 } from "./design";

// Aphelion design system (see index.css and ui.ts): square, flat #0D0D0D surfaces with 1px hairlines,
// white primary buttons, violet only as an accent, light display headings.
const tones: Record<string, string> = {
  green: "border-online/40 text-online", red: "border-danger/40 text-danger", amber: "border-violet-500/40 text-violet-200",
  slate: "border-line text-mist-200", blue: "border-violet-500/40 text-violet-300",
};
const statusTone: Record<string, string> = {
  verified: "green", succeeded: "green", approved: "green", valid: "green", running: "blue", queued: "slate", pending: "amber",
  unverified: "amber", catch_all: "amber", failed: "red", bounced: "red", opted_out: "red", rejected: "red", cancelled: "slate",
};

export function Badge({ children, tone }: { children: ReactNode; tone?: string }) {
  const t = tone ?? statusTone[String(children)] ?? "slate";
  return <span className={`inline-block border px-2 py-0.5 text-xs ${tones[t]}`}>{children}</span>;
}

export function ConfBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-online" : value >= 40 ? "bg-violet-500" : "bg-danger";
  return (
    <div className="flex items-center gap-2" title={`confidence ${value}`}>
      <div className="h-1.5 w-20 bg-line"><div className={`h-1.5 ${color}`} style={{ width: `${value}%` }} /></div>
      <span className="text-xs tabular-nums text-mist-500">{value}</span>
    </div>
  );
}

export function Button({ tone = "default", ...p }: React.ButtonHTMLAttributes<HTMLButtonElement> & { tone?: "default" | "danger" | "primary" }) {
  const c = { default: BTN_QUIET, primary: `${BTN_PRIMARY} !px-4 !py-1.5 !text-sm`, danger: BTN_DANGER }[tone];
  return <button {...p} className={`${c} ${p.className ?? ""}`} />;
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`surface p-5 ${className}`}>
      {title && <h3 className={`${EYEBROW} mb-3`}>{title}</h3>}
      {children}
    </section>
  );
}

export function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center bg-black/70" onClick={onClose}>
      <div className="surface-loud w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className={`${H2} mb-4`}>{title}</h2>
        {children}
      </div>
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  return error ? <p className={`${BANNER_DANGER} my-2 text-sm text-danger-soft`}>{String((error as Error).message ?? error)}</p> : null;
}

export const th = "px-3 py-2 text-left text-[12px] font-medium uppercase tracking-[.12em] text-mist-500";
export const td = "px-3 py-2 text-sm";
export const fmt = (d?: string | null) => (d ? new Date(d).toLocaleString() : "—");
