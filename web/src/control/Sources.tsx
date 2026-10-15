import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote, fmt } from "../ui";

const HINTS: Record<string, string> = {
  ycombinator: '{"batch": "W24", "industry": "fintech", "hiring_only": true}',
  greenhouse: '{"slugs": ["stripe", "airbnb"]}', lever: '{"slugs": ["netflix"]}', ashby: '{"slugs": ["ramp"]}',
  sec_edgar: '{"sic_codes": [6199, 6282, 7374], "max_companies": 50}', press_rss: '{"feeds": ["https://techcrunch.com/feed/"]}',
};

function SourceCard({ s }: { s: J }) {
  const qc = useQueryClient();
  const [filters, setFilters] = useState(JSON.stringify(s.query_filters ?? {}, null, 1));
  const [rate, setRate] = useState(String(s.rate_limit_seconds));
  const [localErr, setLocalErr] = useState<string | null>(null);
  const m = useMutation({ mutationFn: (p: J) => api(`/control/sources/${s.name}`, "PUT", p), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }) });
  const save = (extra: J = {}) => {
    try { setLocalErr(null); m.mutate({ query_filters: JSON.parse(filters), rate_limit_seconds: Number(rate), ...extra }); }
    catch { setLocalErr("Filters must be valid JSON"); }
  };
  return (
    <Card>
      <div className="flex items-center gap-2">
        <h3 className="font-semibold">{s.name}</h3>
        {s.is_stub && <Badge tone="amber">stub, no data source</Badge>}
        {s.requires_config.length > 0 && <span className="text-xs text-mist-500">needs: {s.requires_config.join(", ")}</span>}
        <label className="ml-auto flex items-center gap-1 text-sm">
          <input type="checkbox" disabled={s.is_stub} checked={s.enabled} onChange={(e) => save({ enabled: e.target.checked })} /> enabled
        </label>
      </div>
      {!s.is_stub && (
        <div className="mt-2 space-y-2 text-sm">
          <label className="block">Rate limit (seconds between requests, min 1)
            <input className="ml-2 w-20 border px-2 py-1" type="number" min={1} step={0.5} value={rate} onChange={(e) => setRate(e.target.value)} /></label>
          <label className="block">Query filters (JSON)
            <textarea className="mt-1 h-20 w-full border p-2 font-mono text-xs" placeholder={HINTS[s.name]} value={filters} onChange={(e) => setFilters(e.target.value)} /></label>
          <Button onClick={() => save()}>Save</Button>
        </div>
      )}
      <ErrorNote error={m.error ?? (localErr ? new Error(localErr) : null)} />
      <dl className="mt-2 grid grid-cols-3 gap-2 text-xs text-mist-500">
        <div>Last success<br /><b>{fmt(s.last_success)}</b></div><div>Cached items<br /><b>{s.cached_items}</b></div>
        <div>Last error<br /><b className="text-danger">{s.last_error ?? "—"}</b></div>
      </dl>
    </Card>
  );
}

export default function Sources() {
  const q = useQuery({ queryKey: ["sources"], queryFn: () => api<J[]>("/control/sources") });
  return (
    <div className="grid gap-3 md:grid-cols-2">
      <ErrorNote error={q.error} />
      {q.data?.map((s) => <SourceCard key={`${s.name}-${JSON.stringify(s.query_filters)}-${s.enabled}`} s={s} />)}
    </div>
  );
}
