import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { FILL, Pager, SortTh, useFitRows, useSort } from "../fit";
import { Badge, Card, ErrorNote, td, th } from "../ui";
import SearchSelect from "./SearchSelect";
import { SITE_LABEL, STATUSES, pitchFor, whatsapp } from "./util";

export default function Leads() {
  const qc = useQueryClient();
  const [site, setSite] = useState("any");
  const [status, setStatus] = useState("");
  const [text, setText] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [sort, order, onSort] = useSort("score", "desc");
  const [boxRef, rows] = useFitRows(56, 38);
  useEffect(() => setPage(1), [site, status, text, search, sort, order, rows]);
  const qs = new URLSearchParams({ page_size: String(rows), page: String(page), sort, order, site });
  if (status) qs.set("status", status);
  if (text) qs.set("q", text);
  if (search) qs.set("search", search);
  const q = useQuery({ queryKey: ["leads", qs.toString()], queryFn: () => api<J>(`/leads?${qs}`), placeholderData: (p) => p });
  const tpl = useQuery({ queryKey: ["pitch"], queryFn: () => api<J>("/leads/pitch") });
  const set = useMutation({
    mutationFn: ({ id, status }: J) => api(`/leads/${id}`, "PATCH", { status }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leads"] }); qc.invalidateQueries({ queryKey: ["lead-stats"] }); },
  });
  const h = (label: string, k: string, first: "asc" | "desc" = "asc") => <SortTh label={label} k={k} sort={sort} order={order} onSort={onSort} className={th} first={first} />;
  return (
    <Card className={FILL}>
      <div className="mb-3 flex shrink-0 flex-wrap items-center gap-3 text-sm">
        <SearchSelect value={search} onChange={setSearch} />
        <select value={site} onChange={(e) => setSite(e.target.value)} aria-label="Website filter">
          <option value="any">All businesses</option><option value="none">Without a website (verified)</option><option value="has">With a website</option>
          <option value="probable">Probable website</option><option value="unknown">Not checked yet</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any status</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <input placeholder="search name, category, area" value={text} onChange={(e) => setText(e.target.value)} />
        <span className="ml-auto text-mist-500">{q.data?.total ?? 0} leads</span>
      </div>
      <ErrorNote error={q.error ?? set.error} />
      <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup><col className="w-16" /><col /><col className="w-36" /><col className="w-44" /><col className="w-32" /><col className="w-48" /></colgroup>
          <thead><tr className="h-[38px]">{h("Score", "score", "desc")}{h("Business", "name")}{h("Phone", "phone")}{h("Website", "website")}{h("Status", "status")}<th className={th}>Reach out</th></tr></thead>
          <tbody>
            {q.data?.items.map((l: J) => {
              const wa = whatsapp(l.phone, pitchFor(tpl.data?.template ?? "", l));
              return (
                <tr key={l.id} className="h-14 border-t">
                  <td className={td}><b>{l.score}</b></td>
                  <td className={`${td} overflow-hidden`}>
                    <div className="truncate">{l.name}</div>
                    <div className="truncate text-xs text-mist-500">{l.category} · {l.address}</div>
                    <div className="truncate text-xs text-mist-500">{l.rating}</div>
                  </td>
                  <td className={`${td} truncate`}>{l.phone || "—"}</td>
                  <td className={`${td} overflow-hidden`}>
                    <Badge tone={SITE_LABEL[l.website_status]?.[1]}>{SITE_LABEL[l.website_status]?.[0] ?? l.website_status}</Badge>
                    {l.website_evidence && <div className="truncate text-xs text-mist-500" title={l.website_evidence}>{l.website_evidence}</div>}
                  </td>
                  <td className={td}>
                    <select className="w-full" value={l.status} onChange={(e) => set.mutate({ id: l.id, status: e.target.value })}>
                      {STATUSES.map((s) => <option key={s}>{s}</option>)}
                    </select>
                  </td>
                  <td className={`${td} space-x-2 whitespace-nowrap`}>
                    {wa && <a className="text-violet-300 underline" href={wa} target="_blank" rel="noreferrer" onClick={() => l.status === "new" && set.mutate({ id: l.id, status: "contacted" })}>WhatsApp</a>}
                    {l.phone && <a className="text-violet-300 underline" href={`tel:${l.phone}`}>Call</a>}
                    {l.maps_url && <a className="text-violet-300 underline" href={l.maps_url} target="_blank" rel="noreferrer">Maps</a>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <Pager page={page} total={q.data?.total ?? 0} size={rows} onPage={setPage} />
    </Card>
  );
}
