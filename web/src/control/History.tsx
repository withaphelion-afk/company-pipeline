import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote, fmt, td, th } from "../ui";

function Detail({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["job", id], queryFn: () => api<J>(`/control/jobs/${id}`) });
  const j = q.data;
  return (
    <Card title={`Job #${id}`}>
      <ErrorNote error={q.error} />
      {j && (
        <div className="space-y-2 text-xs">
          <h4 className="font-semibold">Stats</h4><pre className="overflow-auto rounded bg-slate-100 p-2">{JSON.stringify(j.stats, null, 2)}</pre>
          {j.error && <><h4 className="font-semibold">Error</h4><pre className="overflow-auto rounded bg-red-50 p-2 text-red-800">{j.error}</pre></>}
          <h4 className="font-semibold">Log</h4>
          <div className="max-h-64 overflow-auto rounded bg-slate-900 p-2 font-mono text-slate-100">
            {j.logs.map((l: J) => <div key={l.id}>[{l.level}] {l.message}</div>)}
          </div>
        </div>
      )}
    </Card>
  );
}

export default function History() {
  const [f, setF] = useState({ stage: "", status: "", since: "" });
  const [page, setPage] = useState(1);
  const [sel, setSel] = useState<number | null>(null);
  const qs = new URLSearchParams({ page: String(page), page_size: "20" });
  Object.entries(f).forEach(([k, v]) => v && qs.set(k, k === "since" ? new Date(v).toISOString() : v));
  const q = useQuery({ queryKey: ["jobs", "history", qs.toString()], queryFn: () => api<J>(`/control/jobs?${qs}`) });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<J>("/control/status") });
  const pages = Math.max(1, Math.ceil((q.data?.total ?? 0) / 20));
  const set = (k: string, v: string) => { setF({ ...f, [k]: v }); setPage(1); };
  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card>
        <div className="mb-3 flex flex-wrap gap-2 text-sm">
          <select className="rounded border px-2 py-1" value={f.stage} onChange={(e) => set("stage", e.target.value)}>
            <option value="">Any stage</option>{status.data?.stages.map((s: string) => <option key={s}>{s}</option>)}
          </select>
          <select className="rounded border px-2 py-1" value={f.status} onChange={(e) => set("status", e.target.value)}>
            <option value="">Any status</option>{["queued", "running", "succeeded", "failed", "cancelled"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <label>Since <input type="date" className="rounded border px-2 py-1" value={f.since} onChange={(e) => set("since", e.target.value)} /></label>
        </div>
        <ErrorNote error={q.error} />
        <table className="w-full">
          <thead><tr><th className={th}>#</th><th className={th}>Stage</th><th className={th}>Source</th><th className={th}>Status</th><th className={th}>Started</th><th className={th}>Finished</th></tr></thead>
          <tbody>
            {q.data?.items.map((j: J) => (
              <tr key={j.id} className={`cursor-pointer border-t hover:bg-slate-50 ${sel === j.id ? "bg-blue-50" : ""}`} onClick={() => setSel(j.id)}>
                <td className={td}>{j.id}</td><td className={td}>{j.stage}{j.dry_run && <span className="ml-1 text-xs text-slate-400">dry</span>}</td>
                <td className={td}>{j.source ?? "all"}</td><td className={td}><Badge>{j.status}</Badge></td><td className={td}>{fmt(j.started_at)}</td><td className={td}>{fmt(j.finished_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-3 flex items-center gap-2 text-sm">
          <Button disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button>
          <span>Page {page} of {pages}</span>
          <Button disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
        </div>
      </Card>
      {sel !== null ? <Detail id={sel} /> : <Card><p className="text-sm text-slate-500">Select a run to see stats, error trace and logs.</p></Card>}
    </div>
  );
}
