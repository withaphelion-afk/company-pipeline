import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { Badge, Card, ErrorNote, fmt, td, th } from "../ui";

export default function Jobs() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const search = useQuery({ queryKey: ["search"], queryFn: () => api<J>("/control/search") });
  const qs = new URLSearchParams({ page: String(page), page_size: "50" });
  if (q) qs.set("q", q);
  const jobs = useQuery({ queryKey: ["jobs", qs.toString()], queryFn: () => api<J>(`/jobs?${qs}`) });
  const pages = Math.max(1, Math.ceil((jobs.data?.total ?? 0) / 50));
  return (
    <Card>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm">
        <input className="border px-2 py-1" placeholder="filter by title or company" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
        <span className="text-mist-500">
          Saved search: <b>{search.data?.roles.join(", ")}</b> · {search.data?.remote_only ? "remote only" : "any location"} ·{" "}
          <Link className="text-violet-300 underline" to="/control/search">change or run</Link>
        </span>
        <span className="ml-auto text-mist-500">{jobs.data?.total ?? 0} jobs</span>
      </div>
      <ErrorNote error={jobs.error} />
      <table className="w-full">
        <thead><tr><th className={th}>Job</th><th className={th}>Company</th><th className={th}>Source</th><th className={th}>Best contact</th><th className={th}>Found</th></tr></thead>
        <tbody>
          {jobs.data?.items.map((j: J) => (
            <tr key={j.id} className="border-t align-top">
              <td className={td}>{j.apply_url ? <a className="text-violet-300 underline" href={j.apply_url} target="_blank" rel="noreferrer">{j.job}</a> : j.job}</td>
              <td className={td}>{j.company.name}<div className="text-xs text-mist-500">{j.company.domain}</div></td>
              <td className={td}><Badge>{j.source}</Badge></td>
              <td className={td}>{j.best_contact ? <>{j.best_contact.name}<div className="text-xs text-mist-500">{j.best_contact.title}</div><div className="text-xs">{j.best_contact.email} <Badge tone={j.best_contact.confidence >= 80 ? "green" : "amber"}>{j.best_contact.confidence >= 80 ? "published" : "guess"}</Badge></div></> : <span className="text-xs text-mist-500">{j.contacts ? "no email yet" : "not looked up yet"}</span>}</td>
              <td className={td}>{fmt(j.observed_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {jobs.data?.items.length === 0 && <p className="mt-3 text-sm text-mist-500">No matching jobs yet. Open Search &amp; run, enable the recommended sources and run.</p>}
      <div className="mt-3 flex items-center gap-2 text-sm">
        <button className="border px-3 py-1 disabled:opacity-50" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</button>
        <span>Page {page} of {pages}</span>
        <button className="border px-3 py-1 disabled:opacity-50" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
      </div>
    </Card>
  );
}
