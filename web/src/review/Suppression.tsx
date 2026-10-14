import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Button, Card, ErrorNote, fmt, td, th } from "../ui";

export default function Suppression() {
  const qc = useQueryClient();
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const q = useQuery({ queryKey: ["suppression"], queryFn: () => api<J[]>("/suppression") });
  const done = () => qc.invalidateQueries({ queryKey: ["suppression"] });
  const add = useMutation({ mutationFn: () => api("/suppression", "POST", { email_or_domain: value, reason }), onSuccess: () => { setValue(""); setReason(""); done(); } });
  const del = useMutation({ mutationFn: (id: number) => api(`/suppression/${id}`, "DELETE"), onSuccess: done });
  return (
    <Card>
      <form className="mb-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
        <input className="rounded border px-2 py-1 text-sm" placeholder="email or domain" value={value} onChange={(e) => setValue(e.target.value)} required />
        <input className="w-72 rounded border px-2 py-1 text-sm" placeholder="reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        <Button tone="primary" type="submit">Add</Button>
      </form>
      <ErrorNote error={add.error ?? del.error ?? q.error} />
      <table className="w-full">
        <thead><tr><th className={th}>Email / domain</th><th className={th}>Reason</th><th className={th}>Added</th><th /></tr></thead>
        <tbody>
          {q.data?.map((r) => (
            <tr key={r.id} className="border-t"><td className={td}>{r.email_or_domain}</td><td className={td}>{r.reason}</td><td className={td}>{fmt(r.created_at)}</td>
              <td className={td}><Button onClick={() => del.mutate(r.id)}>Remove</Button></td></tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
