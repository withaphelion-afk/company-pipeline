import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, Link } from "react-router-dom";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote, Modal } from "../ui";

const GOALS = [["hire", "Get hired"], ["invest", "Investors"], ["advise", "Advice / collaboration"]];

export default function Search() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const search = useQuery({ queryKey: ["search"], queryFn: () => api<J>("/control/search") });
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api<J[]>("/control/sources") });
  const [roles, setRoles] = useState("");
  const [remote, setRemote] = useState(true);
  const [goals, setGoals] = useState<string[]>([]);
  const [dry, setDry] = useState(false);
  const [scale, setScale] = useState("1");
  const [confirm, setConfirm] = useState(false);
  useEffect(() => {
    if (search.data) { setRoles(search.data.roles.join(", ")); setRemote(search.data.remote_only); setGoals(search.data.goals); }
  }, [search.data]);
  const save = useMutation({
    mutationFn: () => api("/control/search", "PUT", { roles: roles.split(",").map((r) => r.trim()).filter(Boolean), remote_only: remote, goals }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["search"] }),
  });
  const recommend = useMutation({ mutationFn: () => api("/control/sources/enable-recommended", "POST"), onSuccess: () => qc.invalidateQueries({ queryKey: ["sources"] }) });
  const run = useMutation({
    mutationFn: async () => { await save.mutateAsync(); return api("/control/pipeline", "POST", { dry_run: dry, scale: Number(scale) }); },
    onSuccess: () => { setConfirm(false); nav("/control/runs"); },
  });
  const enabled = sources.data?.filter((s) => s.enabled).map((s) => s.name) ?? [];
  const toggle = (g: string) => setGoals(goals.includes(g) ? goals.filter((x) => x !== g) : [...goals, g]);
  return (
    <div className="space-y-4">
      <Card title="What are you looking for?">
        <div className="space-y-3 text-sm">
          <label className="block">Role keywords (comma separated)
            <input className="mt-1 block w-full rounded border px-2 py-1" value={roles} onChange={(e) => setRoles(e.target.value)} placeholder="frontend, front-end, react" /></label>
          <label className="flex items-center gap-2"><input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} /> Remote jobs only</label>
          <div className="flex flex-wrap gap-4">{GOALS.map(([k, l]) => <label key={k}><input type="checkbox" checked={goals.includes(k)} onChange={() => toggle(k)} /> {l}</label>)}</div>
          <p className="text-xs text-slate-500">Only jobs whose title has one of these keywords (and is remote, if ticked) count as hiring signals and raise a contact&apos;s score. Drafts are written only for the goals ticked here.</p>
          <Button onClick={() => save.mutate()} disabled={save.isPending}>Save</Button>
          <ErrorNote error={save.error} />
        </div>
      </Card>
      <Card title="Sources">
        <div className="mb-2 flex flex-wrap gap-1">{enabled.length ? enabled.map((n) => <Badge key={n} tone="green">{n}</Badge>) : <span className="text-sm text-slate-500">No sources enabled yet.</span>}</div>
        <div className="flex items-center gap-3"><Button onClick={() => recommend.mutate()} disabled={recommend.isPending}>Enable all recommended free sources</Button>
          <Link className="text-sm text-blue-600 underline" to="/control/sources">fine-tune</Link></div>
        <ErrorNote error={recommend.error} />
      </Card>
      <Card title="Run">
        <p className="mb-3 text-sm text-slate-600">Runs discover → resolve domains → find contacts → verify emails → enrich → rank → draft, one after another. Each click adds the next batch of new companies, so repeat it to keep growing the list.</p>
        <Button tone="primary" onClick={() => setConfirm(true)} disabled={!enabled.length}>Run everything</Button>
        <span className="ml-3 text-sm text-slate-500">then see <Link className="text-blue-600 underline" to="/review/contacts">Contacts</Link> and <Link className="text-blue-600 underline" to="/review/queue">Review queue</Link></span>
      </Card>
      {confirm && (
        <Modal title="Run everything" onClose={() => setConfirm(false)}>
          <div className="space-y-3 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={dry} onChange={(e) => setDry(e.target.checked)} /> Dry run (no database writes)</label>
            <label className="block">Batch size
              <select className="mt-1 block w-full rounded border px-2 py-1" value={scale} onChange={(e) => setScale(e.target.value)}>
                <option value="0.5">Small (about 75 new companies)</option><option value="1">Normal (about 150)</option><option value="2">Large (about 300)</option>
              </select></label>
            <p className="rounded bg-slate-100 p-2 text-xs">Sources: {enabled.join(", ")}. Roles: {roles}. {remote ? "Remote only." : "Any location."} Goals: {goals.join(", ")}. {dry ? "DRY RUN" : "Live writes."}</p>
            <ErrorNote error={run.error} />
            <div className="flex justify-end gap-2"><Button onClick={() => setConfirm(false)}>Cancel</Button><Button tone="primary" onClick={() => run.mutate()} disabled={run.isPending}>Queue all stages</Button></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
