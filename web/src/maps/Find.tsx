import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { Badge, Card, ErrorNote, fmt, td, th } from "../ui";

export default function Find() {
  const q = useQuery({ queryKey: ["lead-stats"], queryFn: () => api<J>("/leads/stats"), refetchInterval: 3000 });
  const s = q.data;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[["Businesses found", s?.total], ["No website", s?.no_website], ["Contacted", s?.by_status?.contacted], ["Won", s?.by_status?.won]].map(([l, v]) => (
          <Card key={String(l)}><div className="text-xs uppercase text-mist-500">{l}</div><div className="font-display text-3xl font-light">{v ?? "—"}</div></Card>
        ))}
      </div>
      <Card title="How data gets here">
        <ol className="list-decimal space-y-1 pl-5 text-sm text-mist-200">
          <li>Load the extension once: chrome://extensions, Developer mode, Load unpacked, pick <code>tools/page-to-csv</code>.</li>
          <li>Open Google Maps, search for example &quot;dentist in Pune&quot; and let the list on the left load.</li>
          <li>Click the extension, then <b>Send Maps results to the app</b>. Rows appear below within seconds, with no file in between.</li>
          <li>Open <Link className="text-violet-300 underline" to="/maps/leads/leads">Leads</Link> to see who has no website, then <Link className="text-violet-300 underline" to="/maps/pitch/pitch">Pitch</Link>.</li>
        </ol>
      </Card>
      <Card title="Live feed (latest 15)">
        <ErrorNote error={q.error} />
        <table className="w-full">
          <thead><tr><th className={th}>Business</th><th className={th}>Category</th><th className={th}>Phone</th><th className={th}>Website</th><th className={th}>Score</th><th className={th}>Found</th></tr></thead>
          <tbody>
            {s?.recent?.map((l: J) => (
              <tr key={l.id} className="border-t"><td className={td}>{l.name}</td><td className={td}>{l.category}<div className="text-xs text-mist-500">{l.address}</div></td>
                <td className={td}>{l.phone || "—"}</td><td className={td}>{l.has_website ? <Badge tone="slate">has site</Badge> : <Badge tone="green">none</Badge>}</td>
                <td className={td}>{l.score}</td><td className={td}>{fmt(l.found_at)}</td></tr>
            ))}
          </tbody>
        </table>
        {s?.total === 0 && <p className="mt-2 text-sm text-mist-500">Nothing yet. Send your first Maps search from the extension.</p>}
      </Card>
    </div>
  );
}
