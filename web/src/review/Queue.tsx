import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote } from "../ui";

function DraftCard({ d }: { d: J }) {
  const qc = useQueryClient();
  const [edit, setEdit] = useState(false);
  const [subject, setSubject] = useState(d.subject);
  const [body, setBody] = useState(d.body);
  const m = useMutation({
    mutationFn: (p: J) => api(`/drafts/${d.id}`, "PATCH", p),
    onSuccess: () => { setEdit(false); qc.invalidateQueries({ queryKey: ["drafts"] }); },
  });
  return (
    <Card className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <strong>{d.person.full_name}</strong><span className="text-slate-500">{d.person.title}</span>
        <span>@ {d.company.name}</span><span className="text-slate-500">&lt;{d.to ?? "no email"}&gt;</span>
        {d.to && (d.to_status === "verified" ? <Badge tone="green">verified</Badge> : <Badge tone="amber">{d.to_confidence >= 80 ? "likely" : "guess, may bounce"}</Badge>)}
        {d.intent && <Badge tone="blue">{d.intent} · score {d.score}</Badge>}
        <Badge>{d.llm_provider}</Badge>
      </div>
      <div className="flex flex-wrap gap-1 text-xs">
        {d.signals_used.map((s: J, i: number) => <span key={i} title={s.url ?? ""} className="rounded bg-blue-50 px-2 py-0.5"><b>{s.type}</b>: {s.value}</span>)}
      </div>
      {edit ? (
        <>
          <input className="w-full rounded border px-2 py-1 text-sm" value={subject} onChange={(e) => setSubject(e.target.value)} />
          <textarea className="h-48 w-full rounded border p-2 text-sm" value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="flex gap-2"><Button tone="primary" onClick={() => m.mutate({ subject, body })}>Save</Button><Button onClick={() => setEdit(false)}>Cancel</Button></div>
        </>
      ) : (
        <>
          <div className="text-sm font-semibold">{d.subject}</div>
          <pre className="whitespace-pre-wrap font-sans text-sm">{d.body}</pre>
          <div className="flex gap-2">
            <Button tone="primary" onClick={() => m.mutate({ action: "approve" })}>Approve</Button>
            <Button onClick={() => setEdit(true)}>Edit</Button>
            <Button tone="danger" onClick={() => m.mutate({ action: "reject" })}>Reject</Button>
            <Button onClick={() => m.mutate({ action: "skip" })}>Skip</Button>
            <span className="self-center text-xs text-slate-400">Approve only marks the draft; nothing is sent.</span>
          </div>
        </>
      )}
      <ErrorNote error={m.error} />
    </Card>
  );
}

export default function Queue() {
  const q = useQuery({ queryKey: ["drafts", "pending"], queryFn: () => api<J[]>("/drafts?status=pending") });
  return (
    <div className="space-y-3">
      <ErrorNote error={q.error} />
      {q.data?.length === 0 && <p className="text-sm text-slate-500">No pending drafts. Run the draft stage from the control panel.</p>}
      {q.data?.map((d) => <DraftCard key={d.id} d={d} />)}
    </div>
  );
}
