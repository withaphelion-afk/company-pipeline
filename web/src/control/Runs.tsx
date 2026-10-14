import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J, streamSSE } from "../api";
import { Badge, Button, Card, ErrorNote, fmt, td, th } from "../ui";

const elapsed = (j: J, now: number) => {
  const start = j.started_at ?? j.created_at;
  const end = j.finished_at ? new Date(j.finished_at).getTime() : now;
  const s = Math.max(0, Math.round((end - new Date(start).getTime()) / 1000));
  return `${Math.floor(s / 60)}m ${s % 60}s`;
};

function LogPanel({ jobId }: { jobId: number }) {
  const [lines, setLines] = useState<J[]>([]);
  const [progress, setProgress] = useState<J | null>(null);
  const [level, setLevel] = useState("all");
  const [auto, setAuto] = useState(true);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setLines([]); setProgress(null);
    const ac = new AbortController();
    streamSSE(`/control/jobs/${jobId}/logs/stream`, (ev, d) => {
      if (ev === "progress") setProgress(d);
      else if (ev === "log") setLines((l) => [...l, d]);
    }, ac.signal).catch(() => { /* aborted or finished */ });
    return () => ac.abort();
  }, [jobId]);
  useEffect(() => { if (auto) end.current?.scrollIntoView(); }, [lines, auto]);
  const pct = progress && progress.total ? Math.min(100, Math.round((progress.processed / progress.total) * 100)) : 0;
  return (
    <Card title={`Job ${jobId} logs`}>
      {progress && <div className="mb-2 text-xs">{progress.processed}/{progress.total} processed · {progress.errors} errors
        <div className="mt-1 h-2 rounded bg-slate-200"><div className="h-2 rounded bg-blue-500" style={{ width: `${pct}%` }} /></div></div>}
      <div className="mb-2 flex items-center gap-3 text-xs">
        <select className="rounded border px-1" value={level} onChange={(e) => setLevel(e.target.value)}>
          {["all", "info", "warn", "error"].map((l) => <option key={l}>{l}</option>)}
        </select>
        <label><input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} /> auto-scroll</label>
      </div>
      <div className="h-64 overflow-auto rounded bg-slate-900 p-2 font-mono text-xs text-slate-100">
        {lines.filter((l) => level === "all" || l.level === level).map((l, i) => (
          <div key={i} className={l.level === "error" ? "text-red-400" : l.level === "warn" ? "text-amber-300" : ""}>[{l.level}] {l.message}</div>
        ))}
        <div ref={end} />
      </div>
    </Card>
  );
}

export default function Runs() {
  const qc = useQueryClient();
  const [sel, setSel] = useState<number | null>(null);
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  const q = useQuery({ queryKey: ["jobs", "live"], queryFn: () => api<J>("/control/jobs?status=queued,running&page_size=50"), refetchInterval: 2000 });
  const cancel = useMutation({ mutationFn: (id: number) => api(`/control/jobs/${id}/cancel`, "POST"), onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }) });
  return (
    <div className="space-y-4">
      <Card>
        <ErrorNote error={q.error ?? cancel.error} />
        <table className="w-full">
          <thead><tr><th className={th}>Job</th><th className={th}>Stage</th><th className={th}>Source</th><th className={th}>Started</th><th className={th}>Elapsed</th><th className={th}>Progress</th><th className={th}>Status</th><th /></tr></thead>
          <tbody>
            {q.data?.items.map((j: J) => {
              const p = j.progress;
              const pct = p?.total ? Math.min(100, Math.round((p.processed / p.total) * 100)) : 0;
              return (
                <tr key={j.id} className={`cursor-pointer border-t ${sel === j.id ? "bg-blue-50" : ""}`} onClick={() => setSel(j.id)}>
                  <td className={td}>#{j.id}</td><td className={td}>{j.stage}{j.dry_run && <span className="ml-1 text-xs text-slate-400">dry</span>}</td>
                  <td className={td}>{j.source ?? "all"}</td><td className={td}>{fmt(j.started_at)}</td><td className={td}>{elapsed(j, now)}</td>
                  <td className={td}><div className="h-2 w-24 rounded bg-slate-200"><div className="h-2 rounded bg-blue-500" style={{ width: `${pct}%` }} /></div></td>
                  <td className={td}><Badge>{j.status}</Badge></td>
                  <td className={td}><Button tone="danger" onClick={(e) => { e.stopPropagation(); cancel.mutate(j.id); }}>Cancel</Button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {q.data?.items.length === 0 && <p className="mt-2 text-sm text-slate-500">Nothing running or queued.</p>}
      </Card>
      {sel !== null && <LogPanel jobId={sel} />}
    </div>
  );
}
