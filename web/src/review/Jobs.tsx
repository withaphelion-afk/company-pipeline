import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { FILL, Pager, useFitRows } from "../fit";
import { Badge, Card, ErrorNote, fmt, td, th } from "../ui";

export default function Jobs() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [boxRef, rows] = useFitRows(56, 38);
  useEffect(() => setPage(1), [q, rows]);
  const search = useQuery({ queryKey: ["search"], queryFn: () => api<J>("/control/search") });
  const qs = new URLSearchParams({ page: String(page), page_size: String(rows) });
  if (q) qs.set("q", q);
  const jobs = useQuery({ queryKey: ["jobs", qs.toString()], queryFn: () => api<J>(`/jobs?${qs}`), placeholderData: (p) => p });
  return (
    <Card className={FILL}>
      <div className="mb-3 flex shrink-0 flex-wrap items-center gap-3 text-sm">
        <input placeholder="filter by title or company" value={q} onChange={(e) => setQ(e.target.value)} />
        <span className="text-mist-500">
          Saved search: <b>{search.data?.roles.join(", ")}</b> · {search.data?.remote_only ? "remote only" : "any location"} ·{" "}
          <Link className="text-violet-300 underline" to="/pipeline/run/search">change or run</Link>
        </span>
        <span className="ml-auto text-mist-500">{jobs.data?.total ?? 0} jobs</span>
      </div>
      <ErrorNote error={jobs.error} />
      <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup><col /><col className="w-56" /><col className="w-32" /><col className="w-72" /><col className="w-44" /></colgroup>
          <thead><tr className="h-[38px]"><th className={th}>Job</th><th className={th}>Company</th><th className={th}>Source</th><th className={th}>Best contact</th><th className={th}>Found</th></tr></thead>
          <tbody>
            {jobs.data?.items.map((j: J) => (
              <tr key={j.id} className="h-14 border-t">
                <td className={`${td} overflow-hidden`}><div className="line-clamp-2">{j.apply_url ? <a className="text-violet-300 underline" href={j.apply_url} target="_blank" rel="noreferrer">{j.job}</a> : j.job}</div></td>
                <td className={`${td} overflow-hidden`}><div className="truncate">{j.company.name}</div><div className="truncate text-xs text-mist-500">{j.company.domain}</div></td>
                <td className={td}><Badge>{j.source}</Badge></td>
                <td className={`${td} overflow-hidden`}>
                  {j.best_contact ? <><div className="truncate">{j.best_contact.name}</div><div className="truncate text-xs text-mist-500">{j.best_contact.email} · {j.best_contact.confidence >= 80 ? "published" : "guess"}</div></>
                    : <span className="text-xs text-mist-500">{j.contacts ? "no email yet" : "not looked up yet"}</span>}
                </td>
                <td className={`${td} truncate`}>{fmt(j.observed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.data?.items.length === 0 && <p className="mt-3 text-sm text-mist-500">No matching jobs yet. Open Run, enable the recommended sources and run.</p>}
      </div>
      <Pager page={page} total={jobs.data?.total ?? 0} size={rows} onPage={setPage} />
    </Card>
  );
}
