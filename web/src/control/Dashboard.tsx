import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote, Modal, fmt } from "../ui";

function RunDialog({ stage, onClose }: { stage: string; onClose: () => void }) {
  const nav = useNavigate();
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => api<J>("/control/settings") });
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api<J[]>("/control/sources") });
  const [source, setSource] = useState("");
  const [limit, setLimit] = useState("");
  const [dry, setDry] = useState<boolean | null>(null);
  const dryRun = dry ?? settings.data?.dry_run_default ?? true;
  const m = useMutation({
    mutationFn: () => api("/control/jobs", "POST", { stage, source: source || null, limit: limit ? Number(limit) : null, dry_run: dryRun }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["status"] }); onClose(); nav("/control/runs"); },
  });
  return (
    <Modal title={`Run ${stage}`} onClose={onClose}>
      <dl className="space-y-3 text-sm">
        <label className="block">Source
          <select className="mt-1 block w-full border px-2 py-1" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="">All enabled sources</option>
            {sources.data?.filter((s) => !s.is_stub).map((s) => <option key={s.name}>{s.name}</option>)}
          </select>
        </label>
        <label className="block">Limit
          <input className="mt-1 block w-full border px-2 py-1" type="number" min={1} placeholder="no limit" value={limit} onChange={(e) => setLimit(e.target.value)} />
        </label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={dryRun} onChange={(e) => setDry(e.target.checked)} /> Dry run (no database writes)</label>
        <p className="bg-ink-800 p-2 text-xs">Will queue <b>{stage}</b> · source <b>{source || "all enabled"}</b> · limit <b>{limit || "none"}</b> · <b>{dryRun ? "dry run" : "LIVE WRITES"}</b></p>
      </dl>
      <ErrorNote error={m.error} />
      <div className="mt-4 flex justify-end gap-2"><Button onClick={onClose}>Cancel</Button><Button tone="primary" onClick={() => m.mutate()} disabled={m.isPending}>Queue job</Button></div>
    </Modal>
  );
}

export default function Dashboard() {
  const [stage, setStage] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["status"], queryFn: () => api<J>("/control/status"), refetchInterval: 3000 });
  const s = q.data;
  const card = (label: string, value: React.ReactNode) => <Card><div className="text-xs uppercase text-mist-500">{label}</div><div className="font-display text-3xl font-light">{value}</div></Card>;
  return (
    <div className="space-y-4">
      <ErrorNote error={q.error} />
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {card("Workers online", s?.workers_online ?? "unknown")}
        {card("Queue depth", s?.queue_depth ?? "—")}
        {card("Running", s?.running ?? "—")}
        {card("Kill switch", s ? (s.kill_switch ? <Badge tone="red">ON</Badge> : <Badge tone="green">off</Badge>) : "—")}
      </div>
      {s?.workers_online === 0 && <p className="bg-ink-800 p-2 text-sm text-violet-200">No workers online: jobs stay queued until you run <code>make run-worker</code>.</p>}
      <Card title="Stages">
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs uppercase text-mist-500"><th>Stage</th><th>Last run</th><th>Status</th><th /></tr></thead>
          <tbody>
            {s?.stages.map((st: string) => {
              const j = s.last_runs[st];
              return (
                <tr key={st} className="border-t">
                  <td className="py-2 font-medium">{st}</td><td>{fmt(j?.finished_at ?? j?.started_at)}</td>
                  <td>{j ? <Badge>{j.status}</Badge> : "never"} {j?.dry_run && <Badge tone="slate">dry</Badge>}</td>
                  <td className="text-right"><Button onClick={() => setStage(st)} disabled={s.kill_switch}>Run…</Button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      {stage && <RunDialog stage={stage} onClose={() => setStage(null)} />}
    </div>
  );
}
