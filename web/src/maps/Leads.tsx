import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Card, ErrorNote, td, th } from "../ui";
import { STATUSES, pitchFor, whatsapp } from "./util";

export default function Leads() {
  const qc = useQueryClient();
  const [noSite, setNoSite] = useState(true);
  const [status, setStatus] = useState("");
  const [text, setText] = useState("");
  const qs = new URLSearchParams({ page_size: "200" });
  if (noSite) qs.set("no_website", "true");
  if (status) qs.set("status", status);
  if (text) qs.set("q", text);
  const q = useQuery({ queryKey: ["leads", qs.toString()], queryFn: () => api<J>(`/leads?${qs}`) });
  const tpl = useQuery({ queryKey: ["pitch"], queryFn: () => api<J>("/leads/pitch") });
  const set = useMutation({
    mutationFn: ({ id, status }: J) => api(`/leads/${id}`, "PATCH", { status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leads"] }); qc.invalidateQueries({ queryKey: ["lead-stats"] }); },
  });
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <label><input type="checkbox" checked={noSite} onChange={(e) => setNoSite(e.target.checked)} /> No website only</label>
        <select className="border px-2 py-1" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <input className="border px-2 py-1" placeholder="search name, category, area" value={text} onChange={(e) => setText(e.target.value)} />
        <span className="ml-auto text-mist-500">{q.data?.total ?? 0} leads</span>
      </div>
      <ErrorNote error={q.error ?? set.error} />
      <table className="w-full">
        <thead><tr><th className={th}>Score</th><th className={th}>Business</th><th className={th}>Phone</th><th className={th}>Website</th><th className={th}>Status</th><th className={th}>Reach out</th></tr></thead>
        <tbody>
          {q.data?.items.map((l: J) => {
            const wa = whatsapp(l.phone, pitchFor(tpl.data?.template ?? "", l));
            return (
              <tr key={l.id} className="border-t align-top">
                <td className={td}><b>{l.score}</b></td>
                <td className={td}>{l.name}<div className="text-xs text-mist-500">{l.category} · {l.address}</div><div className="text-xs text-mist-500">{l.rating}</div></td>
                <td className={td}>{l.phone || "—"}</td>
                <td className={td}>{l.has_website ? <Badge tone="slate">has site</Badge> : <Badge tone="green">none</Badge>}</td>
                <td className={td}>
                  <select className="border px-1 py-0.5 text-sm" value={l.status} onChange={(e) => set.mutate({ id: l.id, status: e.target.value })}>
                    {STATUSES.map((s) => <option key={s}>{s}</option>)}
                  </select>
                </td>
                <td className={`${td} space-x-2`}>
                  {wa && <a className="text-violet-300 underline" href={wa} target="_blank" rel="noreferrer" onClick={() => l.status === "new" && set.mutate({ id: l.id, status: "contacted" })}>WhatsApp</a>}
                  {l.phone && <a className="text-violet-300 underline" href={`tel:${l.phone}`}>Call</a>}
                  {l.maps_url && <a className="text-violet-300 underline" href={l.maps_url} target="_blank" rel="noreferrer">Maps</a>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Card>
  );
}
