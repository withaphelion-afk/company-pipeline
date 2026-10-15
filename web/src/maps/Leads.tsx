import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Card, ErrorNote, td, th } from "../ui";
import SearchSelect from "./SearchSelect";
import { SITE_LABEL, STATUSES, pitchFor, whatsapp } from "./util";

export default function Leads() {
  const qc = useQueryClient();
  const [site, setSite] = useState("none");
  const [status, setStatus] = useState("");
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const qs = new URLSearchParams({ page_size: "200" });
  qs.set("site", site);
  if (status) qs.set("status", status);
  if (text) qs.set("q", text);
  if (search) qs.set("search", search);
  const q = useQuery({ queryKey: ["leads", qs.toString()], queryFn: () => api<J>(`/leads?${qs}`) });
  const tpl = useQuery({ queryKey: ["pitch"], queryFn: () => api<J>("/leads/pitch") });
  const set = useMutation({
    mutationFn: ({ id, status }: J) => api(`/leads/${id}`, "PATCH", { status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leads"] }); qc.invalidateQueries({ queryKey: ["lead-stats"] }); },
  });
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <SearchSelect value={search} onChange={setSearch} />
        <select value={site} onChange={(e) => setSite(e.target.value)}>
          <option value="none">No website (verified)</option><option value="probable">Probable site</option><option value="unknown">Not checked yet</option><option value="has">Has website</option><option value="any">Any website status</option>
        </select>
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
                <td className={td}><Badge tone={SITE_LABEL[l.website_status]?.[1]}>{SITE_LABEL[l.website_status]?.[0] ?? l.website_status}</Badge>{l.website_evidence && <div className="mt-1 max-w-48 text-xs text-mist-500">{l.website_evidence}</div>}</td>
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
