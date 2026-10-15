import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Card, ConfBar, ErrorNote, fmt, td, th } from "../ui";

export default function Companies() {
  const [f, setF] = useState({ country: "", stage: "", is_hiring: "", source: "" });
  const [sort, setSort] = useState("name");
  const [order, setOrder] = useState<"asc" | "desc">("asc");
  const [sel, setSel] = useState<number | null>(null);
  const qs = new URLSearchParams({ sort, order });
  Object.entries(f).forEach(([k, v]) => v && qs.set(k, v));
  const list = useQuery({ queryKey: ["companies", qs.toString()], queryFn: () => api<J>(`/companies?${qs}`) });
  const detail = useQuery({ queryKey: ["company", sel], queryFn: () => api<J>(`/companies/${sel}`), enabled: sel !== null });
  const head = (key: string, label: string) => (
    <th className={`${th} cursor-pointer`} onClick={() => { setOrder(sort === key && order === "asc" ? "desc" : "asc"); setSort(key); }}>
      {label}{sort === key ? (order === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );
  const input = (k: keyof typeof f, ph: string) => (
    <input className="border px-2 py-1 text-sm" placeholder={ph} value={f[k]} onChange={(e) => setF({ ...f, [k]: e.target.value })} />
  );
  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card>
        <div className="mb-3 flex flex-wrap gap-2">
          {input("country", "Country")}{input("stage", "Stage")}{input("source", "Source")}
          <select className="border px-2 py-1 text-sm" value={f.is_hiring} onChange={(e) => setF({ ...f, is_hiring: e.target.value })}>
            <option value="">Hiring: any</option><option value="true">Hiring</option><option value="false">Not hiring</option>
          </select>
        </div>
        <ErrorNote error={list.error} />
        <table className="w-full">
          <thead><tr>{head("name", "Name")}{head("country", "Country")}{head("stage", "Stage")}{head("is_hiring", "Hiring")}<th className={th}>Source</th></tr></thead>
          <tbody>
            {list.data?.items.map((c: J) => (
              <tr key={c.id} onClick={() => setSel(c.id)} className={`cursor-pointer border-t hover:bg-ink-800 ${sel === c.id ? "bg-ink-800" : ""}`}>
                <td className={td}>{c.name}<div className="text-xs text-mist-500">{c.domain}</div></td>
                <td className={td}>{c.country ?? "—"}</td><td className={td}>{c.stage ?? "—"}</td>
                <td className={td}>{c.is_hiring ? <Badge tone="green">hiring</Badge> : "—"}</td><td className={td}>{c.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-mist-500">{list.data?.total ?? 0} companies</p>
      </Card>
      <Card title={detail.data?.name ?? "Select a company"}>
        <ErrorNote error={detail.error} />
        {detail.data && (
          <div className="space-y-3 text-sm">
            <p className="text-mist-200">{detail.data.description}</p>
            <div><h4 className="font-semibold">People</h4>
              {detail.data.people.map((p: J) => (
                <div key={p.id} className="mt-2 border-t pt-2">
                  <div>{p.full_name} <Badge>{p.role_type}</Badge></div><div className="text-xs text-mist-500">{p.title}</div>
                  {p.emails.map((e: J) => (
                    <div key={e.id} className="mt-1 flex items-center gap-2"><span className="text-xs">{e.address}</span><ConfBar value={e.confidence} /><Badge>{e.status}</Badge></div>
                  ))}
                </div>
              ))}
            </div>
            <div><h4 className="font-semibold">Signals</h4>
              {detail.data.signals.map((s: J) => (
                <div key={s.id} className="mt-1"><Badge tone="blue">{s.type}</Badge> {s.value}
                  {s.url && <a className="ml-1 text-violet-300 underline" href={s.url} target="_blank" rel="noreferrer">source</a>}
                  <span className="ml-1 text-xs text-mist-500">{fmt(s.observed_at)}</span></div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
