import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote, fmt, td, th } from "../ui";

const split = (s: string) => s.split(/[\n,;]+/).map((x) => x.trim()).filter(Boolean);
const tone: Record<string, string> = { pending: "slate", running: "blue", done: "green", error: "red" };

export default function Queue() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["maps-queue"], queryFn: () => api<J>("/leads/queue"), refetchInterval: 5000 });
  const [kw, setKw] = useState("skin clinic");
  const [areas, setAreas] = useState("Saket, Delhi\nGreater Kailash, Delhi\nDefence Colony, Delhi");
  const refresh = () => qc.invalidateQueries({ queryKey: ["maps-queue"] });
  const add = useMutation({ mutationFn: (b: J) => api("/leads/queue", "POST", b), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: number) => api(`/leads/queue/${id}`, "DELETE"), onSuccess: refresh });
  const reset = useMutation({ mutationFn: (id: number) => api(`/leads/queue/${id}/reset`, "POST"), onSuccess: refresh });
  const starter = q.data?.starter;
  const items: J[] = q.data?.items ?? [];
  return (
    <Card title="Search queue (what the crawler works through)">
      <div className="grid gap-3 md:grid-cols-2">
        <label className="block text-sm text-mist-200">Keywords (one per line)
          <textarea className="mt-1 h-24 w-full" value={kw} onChange={(e) => setKw(e.target.value)} /></label>
        <label className="block text-sm text-mist-200">Areas (one per line, include the city)
          <textarea className="mt-1 h-24 w-full" value={areas} onChange={(e) => setAreas(e.target.value)} /></label>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button tone="primary" onClick={() => add.mutate({ keywords: split(kw), areas: split(areas) })} disabled={add.isPending}>Add to queue</Button>
        {starter && <Button onClick={() => add.mutate({ keywords: starter.keywords, areas: starter.areas.map((a: string) => `${a}, Delhi`) })}>Add the Delhi high-ticket starter pack</Button>}
        {add.data && <span className="text-sm text-mist-500">added {add.data.added}, {add.data.total} in the queue</span>}
      </div>
      <ErrorNote error={q.error ?? add.error ?? del.error ?? reset.error} />
      <p className="mt-3 text-xs text-mist-500">The crawler runs on GitHub Actions every 6 hours and takes the next pending search, or you can start it from the repo&apos;s Actions tab. If Google shows a CAPTCHA the crawler stops and the search shows an error here.</p>
      <table className="mt-3 w-full">
        <thead><tr><th className={th}>Search</th><th className={th}>Status</th><th className={th}>Read / new</th><th className={th}>Last run</th><th className={th} /></tr></thead>
        <tbody>
          {items.map((i) => (
            <tr key={i.id} className="border-t align-top">
              <td className={td}>{i.query}{i.error && <div className="text-xs text-danger">{i.error}</div>}</td>
              <td className={td}><Badge tone={tone[i.status]}>{i.status}</Badge></td>
              <td className={td}>{i.found} / {i.new}</td><td className={td}>{fmt(i.last_run_at)}</td>
              <td className={`${td} space-x-2`}><Button onClick={() => reset.mutate(i.id)}>Run again</Button><Button tone="danger" onClick={() => del.mutate(i.id)}>Remove</Button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && <p className="mt-2 text-sm text-mist-500">The queue is empty. Add a keyword and areas above.</p>}
    </Card>
  );
}
