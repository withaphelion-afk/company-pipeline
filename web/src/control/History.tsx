import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { FILL, Pager, useFitRows } from "../fit";
import { Badge, Card, ErrorNote, fmt, td, th } from "../ui";

function Detail({ id }: { id: number }) {
  const q = useQuery({ queryKey: ["job", id], queryFn: () => api<J>(`/control/jobs/${id}`) });
  const j = q.data;
  return (
    <Card title={`Job #${id}`} className="flex min-h-0 flex-col">
      <ErrorNote error={q.error} />
      {j && (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden text-xs">
          <h4 className="font-semibold">Stats</h4><pre className="max-h-40 overflow-hidden bg-ink-800 p-2">{JSON.stringify(j.stats, null, 1).slice(0, 600)}</pre>
          {j.error && <><h4 className="font-semibold">Error</h4><pre className="max-h-24 overflow-hidden bg-ink-800 p-2 text-danger">{String(j.error).split("\n").slice(-3).join("\n")}</pre></>}
          <h4 className="font-semibold">Last log lines</h4>
          <div className="min-h-0 flex-1 overflow-hidden bg-ink-950 p-2 font-mono text-mist-200">
            {j.logs.slice(-12).map((l: J) => <div key={l.id} className="truncate">[{l.level}] {l.message}</div>)}
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
  const [boxRef, rows] = useFitRows(44, 38);
  useEffect(() => setPage(1), [f, rows]);
  const qs = new URLSearchParams({ page: String(page), page_size: String(rows) });
  Object.entries(f).forEach(([k, v]) => v && qs.set(k, k === "since" ? new Date(v).toISOString() : v));
  const q = useQuery({ queryKey: ["jobs", "history", qs.toString()], queryFn: () => api<J>(`/control/jobs?${qs}`), placeholderData: (p) => p });
  const status = useQuery({ queryKey: ["status"], queryFn: () => api<J>("/control/status") });
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className={FILL}>
        <div className="mb-3 flex shrink-0 flex-wrap gap-2 text-sm">
          <select value={f.stage} onChange={(e) => set("stage", e.target.value)}>
            <option value="">Any stage</option>{status.data?.stages.map((s: string) => <option key={s}>{s}</option>)}
          </select>
          <select value={f.status} onChange={(e) => set("status", e.target.value)}>
            <option value="">Any status</option>{["queued", "running", "succeeded", "failed", "cancelled"].map((s) => <option key={s}>{s}</option>)}
          </select>
          <label>Since <input type="date" value={f.since} onChange={(e) => set("since", e.target.value)} /></label>
        </div>
        <ErrorNote error={q.error} />
        <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
          <table className="w-full table-fixed">
            <colgroup><col className="w-14" /><col /><col className="w-28" /><col className="w-28" /><col className="w-44" /></colgroup>
            <thead><tr className="h-[38px]"><th className={th}>#</th><th className={th}>Stage</th><th className={th}>Source</th><th className={th}>Status</th><th className={th}>Started</th></tr></thead>
            <tbody>
              {q.data?.items.map((j: J) => (
                <tr key={j.id} className={`h-11 cursor-pointer border-t hover:bg-ink-800 ${sel === j.id ? "bg-ink-800" : ""}`} onClick={() => setSel(j.id)}>
                  <td className={td}>{j.id}</td><td className={`${td} truncate`}>{j.stage}{j.dry_run && <span className="ml-1 text-xs text-mist-500">dry</span>}</td>
                  <td className={`${td} truncate`}>{j.source ?? "all"}</td><td className={td}><Badge>{j.status}</Badge></td><td className={`${td} truncate`}>{fmt(j.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager page={page} total={q.data?.total ?? 0} size={rows} onPage={setPage} />
      </Card>
      {sel !== null ? <Detail id={sel} /> : <Card><p className="text-sm text-mist-500">Select a run to see stats, the error and the last log lines.</p></Card>}
    </div>
  );
}
