import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { FILL, Pager, SortTh, useFitRows, useSort } from "../fit";
import { Badge, Card, ConfBar, ErrorNote, fmt, td, th } from "../ui";

export default function Companies() {
  const [f, setF] = useState({ country: "", stage: "", is_hiring: "", source: "" });
  const [page, setPage] = useState(1);
  const [sel, setSel] = useState<number | null>(null);
  const [sort, order, onSort] = useSort("name", "asc");
  const [boxRef, rows] = useFitRows(52, 38);
  useEffect(() => setPage(1), [f, sort, order, rows]);
  const qs = new URLSearchParams({ sort, order, page: String(page), page_size: String(rows) });
  Object.entries(f).forEach(([k, v]) => v && qs.set(k, v));
  const list = useQuery({ queryKey: ["companies", qs.toString()], queryFn: () => api<J>(`/companies?${qs}`), placeholderData: (p) => p });
  const detail = useQuery({ queryKey: ["company", sel], queryFn: () => api<J>(`/companies/${sel}`), enabled: sel !== null });
  const h = (label: string, k: string) => <SortTh label={label} k={k} sort={sort} order={order} onSort={onSort} className={th} />;
  const input = (k: keyof typeof f, ph: string) => <input className="w-32" placeholder={ph} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />;
  const d = detail.data;
  return (
    <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className={FILL}>
        <div className="mb-3 flex shrink-0 flex-wrap gap-2 text-sm">
          {input("country", "Country")}{input("stage", "Stage")}{input("source", "Source")}
          <select value={f.is_hiring} onChange={(e) => setF({ ...f, is_hiring: e.target.value })}>
            <option value="">Hiring: any</option><option value="true">Hiring</option><option value="false">Not hiring</option>
          </select>
          <span className="ml-auto text-mist-500">{list.data?.total ?? 0} companies</span>
        </div>
        <ErrorNote error={list.error} />
        <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
          <table className="w-full table-fixed">
            <colgroup><col /><col className="w-36" /><col className="w-32" /><col className="w-24" /><col className="w-28" /></colgroup>
            <thead><tr className="h-[38px]">{h("Name", "name")}{h("Country", "country")}{h("Stage", "stage")}{h("Hiring", "is_hiring")}<th className={th}>Source</th></tr></thead>
            <tbody>
              {list.data?.items.map((c: J) => (
                <tr key={c.id} onClick={() => setSel(c.id)} className={`h-[52px] cursor-pointer border-t hover:bg-ink-800 ${sel === c.id ? "bg-ink-800" : ""}`}>
                  <td className={`${td} overflow-hidden`}><div className="truncate">{c.name}</div><div className="truncate text-xs text-mist-500">{c.domain}</div></td>
                  <td className={`${td} truncate`}>{c.country ?? "—"}</td><td className={`${td} truncate`}>{c.stage ?? "—"}</td>
                  <td className={td}>{c.is_hiring ? <Badge tone="green">hiring</Badge> : "—"}</td><td className={`${td} truncate`}>{c.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pager page={page} total={list.data?.total ?? 0} size={rows} onPage={setPage} />
      </Card>
      <Card title={d?.name ?? "Select a company"} className="flex min-h-0 flex-col">
        <ErrorNote error={detail.error} />
        {d && (
          <div className="min-h-0 flex-1 space-y-3 overflow-hidden text-sm">
            <p className="line-clamp-2 text-mist-200">{d.description}</p>
            <div><h4 className="font-semibold">People ({d.people.length})</h4>
              {d.people.slice(0, 3).map((p: J) => (
                <div key={p.id} className="mt-1 border-t pt-1">
                  <div className="truncate">{p.full_name} <Badge>{p.role_type}</Badge></div>
                  {p.emails.slice(0, 1).map((e: J) => <div key={e.id} className="flex items-center gap-2"><span className="truncate text-xs">{e.address}</span><ConfBar value={e.confidence} /></div>)}
                </div>
              ))}
              {d.people.length > 3 && <div className="text-xs text-mist-500">+{d.people.length - 3} more (see Contacts)</div>}
            </div>
            <div><h4 className="font-semibold">Signals ({d.signals.length})</h4>
              {d.signals.slice(0, 3).map((s: J) => <div key={s.id} className="mt-1 truncate"><Badge tone="blue">{s.type}</Badge> {s.value} <span className="text-xs text-mist-500">{fmt(s.observed_at)}</span></div>)}
              {d.signals.length > 3 && <div className="text-xs text-mist-500">+{d.signals.length - 3} more</div>}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
