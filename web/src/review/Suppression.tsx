import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { FILL, Pager, useFitRows } from "../fit";
import { Button, Card, ErrorNote, fmt, td, th } from "../ui";

export default function Suppression() {
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [page, setPage] = useState(1);
  const [boxRef, rows] = useFitRows(48, 38);
  useEffect(() => setPage(1), [rows]);
  const q = useQuery({ queryKey: ["suppression"], queryFn: () => api<J[]>("/suppression") });
  const done = () => qc.invalidateQueries({ queryKey: ["suppression"] });
  const add = useMutation({ mutationFn: () => api("/suppression", "POST", { email_or_domain: value, reason }), onSuccess: () => { setValue(""); setReason(""); done(); } });
  const del = useMutation({ mutationFn: (id: number) => api(`/suppression/${id}`, "DELETE"), onSuccess: done });
  const items = q.data ?? [];
  return (
    <Card className={FILL}>
      <form className="mb-3 flex shrink-0 flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
        <input placeholder="email or domain" value={value} onChange={(e) => setValue(e.target.value)} required />
        <input className="w-72" placeholder="reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <Button tone="primary" type="submit">Add</Button>
      </form>
      <ErrorNote error={add.error ?? del.error ?? q.error} />
      <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup><col /><col className="w-80" /><col className="w-48" /><col className="w-28" /></colgroup>
          <thead><tr className="h-[38px]"><th className={th}>Email / domain</th><th className={th}>Reason</th><th className={th}>Added</th><th /></tr></thead>
          <tbody>
            {items.slice((page - 1) * rows, page * rows).map((r) => (
              <tr key={r.id} className="h-12 border-t"><td className={`${td} truncate`}>{r.email_or_domain}</td><td className={`${td} truncate`}>{r.reason}</td><td className={`${td} truncate`}>{fmt(r.created_at)}</td>
                <td className={td}><Button onClick={() => del.mutate(r.id)}>Remove</Button></td></tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <p className="mt-2 text-sm text-mist-500">Nobody is suppressed yet.</p>}
      </div>
      <Pager page={page} total={items.length} size={rows} onPage={setPage} />
    </Card>
  );
}
