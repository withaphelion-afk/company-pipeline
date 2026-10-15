import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { FILL, Pager, SortTh, useFitRows, useSort } from "../fit";
import { Badge, Button, Card, ErrorNote, fmt, td, th } from "../ui";

const split = (s: string) => s.split(/[\n,;]+/).map((x) => x.trim()).filter(Boolean);
const tone: Record<string, string> = { pending: "slate", running: "blue", done: "green", error: "red" };

export default function Queue() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["maps-queue"], queryFn: () => api<J>("/leads/queue"), refetchInterval: 5000 });
  const [kw, setKw] = useState("skin clinic");
  const [areas, setAreas] = useState("Saket, Delhi\nGreater Kailash, Delhi\nDefence Colony, Delhi");
  const [page, setPage] = useState(1);
  const [sort, order, onSort] = useSort("status", "asc");
  const [boxRef, rows] = useFitRows(48, 38);
  const refresh = () => qc.invalidateQueries({ queryKey: ["maps-queue"] });
  const add = useMutation({ mutationFn: (b: J) => api("/leads/queue", "POST", b), onSuccess: refresh });
  const del = useMutation({ mutationFn: (id: number) => api(`/leads/queue/${id}`, "DELETE"), onSuccess: refresh });
  const reset = useMutation({ mutationFn: (id: number) => api(`/leads/queue/${id}/reset`, "POST"), onSuccess: refresh });
  const starter = q.data?.starter;
  const items: J[] = useMemo(() => {
    const rank: Record<string, number> = { running: 0, pending: 1, error: 2, done: 3 };
    const key = (i: J) => (sort === "status" ? rank[i.status] ?? 9 : sort === "found" ? i.found : sort === "last" ? i.last_run_at ?? "" : i.query);
    return [...(q.data?.items ?? [])].sort((a, b) => (key(a) > key(b) ? 1 : key(a) < key(b) ? -1 : 0) * (order === "asc" ? 1 : -1));
  }, [q.data, sort, order]);
  useEffect(() => setPage(1), [sort, order, rows]);
  const h = (label: string, k: string) => <SortTh label={label} k={k} sort={sort} order={order} onSort={onSort} className={th} />;
  return (
    <Card title="Search queue (what the crawler works through)" className={FILL}>
      <div className="grid shrink-0 gap-3 md:grid-cols-2">
        <label className="block text-sm text-mist-200">Keywords (one per line)
          <textarea className="mt-1 h-16 w-full" value={kw} onChange={(e) => setKw(e.target.value)} /></label>
        <label className="block text-sm text-mist-200">Areas (one per line, include the city)
          <textarea className="mt-1 h-16 w-full" value={areas} onChange={(e) => setAreas(e.target.value)} /></label>
      </div>
      <div className="mt-2 flex shrink-0 flex-wrap items-center gap-2">
        <Button tone="primary" onClick={() => add.mutate({ keywords: split(kw), areas: split(areas) })} disabled={add.isPending}>Add to queue</Button>
        {starter && <Button onClick={() => add.mutate({ keywords: starter.keywords, areas: starter.areas.map((a: string) => `${a}, Delhi`) })}>Add the Delhi high-ticket starter pack</Button>}
        {add.data && <span className="text-sm text-mist-500">added {add.data.added}, {add.data.total} in the queue</span>}
        <span className="ml-auto text-xs text-mist-500">Runs on GitHub Actions every 6 hours or on demand. A CAPTCHA stops the run and shows an error here.</span>
      </div>
      <ErrorNote error={q.error ?? add.error ?? del.error ?? reset.error} />
      <div ref={boxRef} className="mt-2 min-h-0 flex-1 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup><col /><col className="w-28" /><col className="w-28" /><col className="w-44" /><col className="w-48" /></colgroup>
          <thead><tr className="h-[38px]">{h("Search", "query")}{h("Status", "status")}{h("Read / new", "found")}{h("Last run", "last")}<th className={th} /></tr></thead>
          <tbody>
            {items.slice((page - 1) * rows, page * rows).map((i) => (
              <tr key={i.id} className="h-12 border-t">
                <td className={`${td} overflow-hidden`}><div className="truncate">{i.query}</div>{i.error && <div className="truncate text-xs text-danger" title={i.error}>{i.error}</div>}</td>
                <td className={td}><Badge tone={tone[i.status]}>{i.status}</Badge></td>
                <td className={td}>{i.found} / {i.new}</td><td className={`${td} truncate`}>{fmt(i.last_run_at)}</td>
                <td className={`${td} space-x-2 whitespace-nowrap`}><Button onClick={() => reset.mutate(i.id)}>Run again</Button><Button tone="danger" onClick={() => del.mutate(i.id)}>Remove</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <p className="mt-2 text-sm text-mist-500">The queue is empty. Add a keyword and areas above.</p>}
      </div>
      <Pager page={page} total={items.length} size={rows} onPage={setPage} />
    </Card>
  );
}
