import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Button, Card, ErrorNote, fmt, td, th } from "../ui";

const PRESETS: Record<string, string> = { "Every hour": "0 * * * *", "Daily at 06:00": "0 6 * * *", "Weekly on Monday": "0 6 * * 1" };

function Row({ r }: { r: J }) {
  const qc = useQueryClient();
  const [cron, setCron] = useState(r.cron_expr);
  const m = useMutation({ mutationFn: (p: J) => api(`/control/schedules/${r.id}`, "PUT", p), onSuccess: () => qc.invalidateQueries({ queryKey: ["schedules"] }) });
  return (
    <>
      <tr className="border-t">
        <td className={td}>{r.stage}</td>
        <td className={td}>
          <select className="mr-2 rounded border px-1 text-sm" value="" onChange={(e) => e.target.value && setCron(e.target.value)}>
            <option value="">Preset…</option>{Object.entries(PRESETS).map(([k, v]) => <option key={k} value={v}>{k}</option>)}
          </select>
          <input className="w-36 rounded border px-2 py-1 font-mono text-sm" value={cron} onChange={(e) => setCron(e.target.value)} />
          <Button className="ml-2" onClick={() => m.mutate({ cron_expr: cron })} disabled={cron === r.cron_expr}>Save</Button>
        </td>
        <td className={td}><input type="checkbox" checked={r.enabled} onChange={(e) => m.mutate({ enabled: e.target.checked })} /></td>
        <td className={td}>{fmt(r.last_run_at)}</td><td className={td}>{r.enabled ? fmt(r.next_run_at) : "—"}</td>
      </tr>
      {m.error && <tr><td colSpan={5}><ErrorNote error={m.error} /></td></tr>}
    </>
  );
}

export default function Schedules() {
  const q = useQuery({ queryKey: ["schedules"], queryFn: () => api<J[]>("/control/schedules") });
  return (
    <Card>
      <p className="mb-3 text-xs text-slate-500">Cron is UTC. Anything that fires more often than every 15 minutes is rejected. The worker reloads changes within 30 seconds.</p>
      <ErrorNote error={q.error} />
      <table className="w-full">
        <thead><tr><th className={th}>Stage</th><th className={th}>Cron</th><th className={th}>Enabled</th><th className={th}>Last run</th><th className={th}>Next run</th></tr></thead>
        <tbody>{q.data?.map((r) => <Row key={r.id} r={r} />)}</tbody>
      </table>
    </Card>
  );
}
