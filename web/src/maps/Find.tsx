import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { FILL, Pager, useFitRows } from "../fit";
import { Badge, Card, ErrorNote, fmt, td, th } from "../ui";
import Queue from "./Queue";
import { SITE_LABEL } from "./util";

function Stats() {
  const q = useQuery({ queryKey: ["lead-stats"], queryFn: () => api<J>("/leads/stats"), refetchInterval: 5000 });
  const s = q.data;
  return (
    <div className="mb-3 grid shrink-0 grid-cols-2 gap-3 md:grid-cols-4">
      {[["Businesses found", s?.total], ["Verified no website", s?.no_website], ["Not checked yet", s?.unverified], ["Contacted", s?.by_status?.contacted]].map(([l, v]) => (
        <Card key={String(l)} className="!p-3"><div className="text-xs uppercase text-mist-500">{l}</div><div className="font-display text-2xl font-light">{v ?? "—"}</div></Card>
      ))}
    </div>
  );
}

export function FindQueue() {
  return <div className="flex min-h-0 flex-1 flex-col"><Stats /><Queue /></div>;
}

export function Feed() {
  const q = useQuery({ queryKey: ["lead-stats"], queryFn: () => api<J>("/leads/stats"), refetchInterval: 3000 });
  const [page, setPage] = useState(1);
  const [boxRef, rows] = useFitRows(48, 38);
  useEffect(() => setPage(1), [rows]);
  const recent: J[] = q.data?.recent ?? [];
  return (
    <Card title="Live feed (newest businesses)" className={FILL}>
      <ErrorNote error={q.error} />
      <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup><col /><col className="w-64" /><col className="w-36" /><col className="w-36" /><col className="w-20" /><col className="w-44" /></colgroup>
          <thead><tr className="h-[38px]"><th className={th}>Business</th><th className={th}>Category</th><th className={th}>Phone</th><th className={th}>Website</th><th className={th}>Score</th><th className={th}>Found</th></tr></thead>
          <tbody>
            {recent.slice((page - 1) * rows, page * rows).map((l) => (
              <tr key={l.id} className="h-12 border-t">
                <td className={`${td} truncate`}>{l.name}</td>
                <td className={`${td} overflow-hidden`}><div className="truncate">{l.category}</div><div className="truncate text-xs text-mist-500">{l.address}</div></td>
                <td className={`${td} truncate`}>{l.phone || "—"}</td>
                <td className={td}><Badge tone={SITE_LABEL[l.website_status]?.[1]}>{SITE_LABEL[l.website_status]?.[0] ?? l.website_status}</Badge></td>
                <td className={td}>{l.score}</td><td className={`${td} truncate`}>{fmt(l.found_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {q.data?.total === 0 && <p className="mt-2 text-sm text-mist-500">Nothing yet. Add searches to the queue and start the crawler.</p>}
      </div>
      <Pager page={page} total={recent.length} size={rows} onPage={setPage} />
    </Card>
  );
}

export function Help() {
  return (
    <Card title="How data gets here">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-mist-200">
        <li>Automatic: add searches to the queue; the crawler on GitHub Actions works through them (every 6 hours, or start it from the repo&apos;s Actions tab).</li>
        <li>Manual: load the extension (chrome://extensions, Developer mode, Load unpacked, <code>tools/page-to-csv</code>), open a Google Maps search, click <b>Send Maps results to the app</b>.</li>
        <li>A business is shown as <b>no website</b> only after the strict check; open <Link className="text-violet-300 underline" to="/maps/leads/leads">Leads</Link> and use the Website filter.</li>
      </ol>
    </Card>
  );
}

export default FindQueue;
