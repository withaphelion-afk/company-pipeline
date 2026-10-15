import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Button, Card, ErrorNote, td, th } from "../ui";

const size = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${(b / 1e3).toFixed(1)} KB`);

export default function Cache() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cache"], queryFn: () => api<J[]>("/control/cache") });
  const [source, setSource] = useState("");
  const [days, setDays] = useState("30");
  const [confirming, setConfirming] = useState(false);
  const m = useMutation({
    mutationFn: () => {
      const qs = new URLSearchParams();
      if (source) qs.set("source", source);
      if (days !== "") qs.set("older_than_days", days);
      return api<J>(`/control/cache?${qs}`, "DELETE", { confirm: true });
    },
    onSuccess: () => { setConfirming(false); qc.invalidateQueries({ queryKey: ["cache"] }); },
  });
  const total = q.data?.reduce((a, r) => a + r.bytes, 0) ?? 0;
  return (
    <div className="space-y-4">
      <Card title={`Disk usage under data/raw (${size(total)})`}>
        <ErrorNote error={q.error} />
        <table className="w-full">
          <thead><tr><th className={th}>Source</th><th className={th}>Files</th><th className={th}>Size</th></tr></thead>
          <tbody>{q.data?.map((r) => <tr key={r.source} className="border-t"><td className={td}>{r.source}</td><td className={td}>{r.files}</td><td className={td}>{size(r.bytes)}</td></tr>)}</tbody>
        </table>
      </Card>
      <Card title="Clear cache">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <select className="border px-2 py-1" value={source} onChange={(e) => { setSource(e.target.value); setConfirming(false); }}>
            <option value="">All sources</option>{q.data?.map((r) => <option key={r.source}>{r.source}</option>)}
          </select>
          <label>older than <input className="w-16 border px-2 py-1" type="number" min={0} value={days} onChange={(e) => { setDays(e.target.value); setConfirming(false); }} /> days</label>
          {!confirming ? <Button onClick={() => setConfirming(true)}>Clear…</Button> : (
            <>
              <span className="text-danger">Delete {source || "all"} cache older than {days || 0} days?</span>
              <Button tone="danger" onClick={() => m.mutate()} disabled={m.isPending}>Yes, delete</Button><Button onClick={() => setConfirming(false)}>No</Button>
            </>
          )}
        </div>
        <ErrorNote error={m.error} />
        {m.data && <p className="mt-2 text-sm text-online">Removed {m.data.removed_files} files.</p>}
      </Card>
    </div>
  );
}
