import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote, Modal } from "../ui";

export const gmail = (d: J, from = "") =>
  `https://mail.google.com/mail/?${from ? `authuser=${encodeURIComponent(from)}&` : ""}view=cm&fs=1&to=${encodeURIComponent(d.to ?? "")}&su=${encodeURIComponent(d.subject)}&body=${encodeURIComponent(d.body)}`;

export default function Send() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["today"], queryFn: () => api<J>("/outreach/today") });
  const cfg = useQuery({ queryKey: ["outreach-settings"], queryFn: () => api<J>("/outreach/settings") });
  const [from, setFrom] = useState<string | null>(null);
  const sendFrom = from ?? cfg.data?.send_from ?? "";
  const saveFrom = useMutation({ mutationFn: () => api("/outreach/settings", "PUT", { send_from: sendFrom }), onSuccess: () => qc.invalidateQueries({ queryKey: ["outreach-settings"] }) });
  const sendStatus = useQuery({ queryKey: ["send-status"], queryFn: () => api<J>("/outreach/send/status"), refetchInterval: (qq) => (qq.state.data?.running ? 1500 : 10000) });
  const [confirmSend, setConfirmSend] = useState(false);
  const startSend = useMutation({
    mutationFn: (dry_run: boolean) => api("/outreach/send", "POST", { dry_run }),
    onSuccess: () => { setConfirmSend(false); qc.invalidateQueries({ queryKey: ["send-status"] }); },
  });
  const ss = sendStatus.data;
  useEffect(() => { if (ss?.done && !ss.running && !ss.dry_run) { qc.invalidateQueries({ queryKey: ["today"] }); qc.invalidateQueries({ queryKey: ["drafts"] }); } }, [ss?.done, ss?.running]);
  const [picked, setPicked] = useState<number[]>([]);
  const [opened, setOpened] = useState<number[]>([]);
  const done = () => { qc.invalidateQueries({ queryKey: ["today"] }); qc.invalidateQueries({ queryKey: ["drafts"] }); };
  const sent = useMutation({ mutationFn: (ids: number[]) => Promise.all(ids.map((id) => api(`/drafts/${id}`, "PATCH", { action: "sent" }))), onSuccess: () => { setOpened([]); setPicked([]); done(); } });
  const d = q.data;
  const items: J[] = d?.items ?? [];
  const remaining: number = d?.remaining ?? 0;
  const open = (list: J[]) => {
    // one separate Gmail compose window per person: the browser may ask you to allow pop-ups for this site
    list.forEach((x) => window.open(gmail(x, sendFrom), "_blank", "noopener"));
    setOpened([...opened, ...list.map((x) => x.id)]);
  };
  const toggle = (id: number) => setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);
  const chosen = items.filter((x) => picked.includes(x.id)).slice(0, remaining);
  return (
    <div className="space-y-3">
      <Card>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <span><b>{d?.sent_24h ?? 0}</b> of <b>{d?.cap ?? 0}</b> sent in the last 24 hours · <b>{remaining}</b> left today</span>
          <Button onClick={() => setPicked(items.slice(0, remaining).map((x) => x.id))} disabled={!remaining}>Select next {Math.min(remaining, items.length)}</Button>
          <Button tone="primary" onClick={() => open(chosen)} disabled={!chosen.length}>Open {chosen.length} in Gmail (one window each)</Button>
          {opened.length > 0 && <Button tone="danger" onClick={() => sent.mutate(opened)}>I sent the {opened.length} I opened</Button>}
        </div>
        <div className="mt-2 flex items-center gap-2 text-sm">Send from
          <input className="w-64 border px-2 py-1" placeholder="you@gmail.com" value={sendFrom} onChange={(e) => setFrom(e.target.value)} />
          <Button onClick={() => saveFrom.mutate()} disabled={saveFrom.isPending}>Save</Button>
          <span className="text-xs text-mist-500">Gmail opens signed in as this account (it must be signed in in this browser).</span>
        </div>
        <p className="mt-2 text-xs text-mist-500">Order: published addresses first, then follow-ups, then best score. Every person gets their own email (no CC or BCC). You press Send in each Gmail window; nothing is sent by this app.</p>
        <ErrorNote error={q.error ?? sent.error} />
      </Card>
      <Card title="Send through the Gmail API (fast, one separate email per person)">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {ss && !ss.authorized && <span className="text-violet-200">Not authorized yet: run <code>python -m pipeline gmail-auth</code> once and click Allow.</span>}
          <Button onClick={() => startSend.mutate(true)} disabled={!items.length || ss?.running}>Preview (dry run)</Button>
          <Button tone="danger" onClick={() => setConfirmSend(true)} disabled={!items.length || !remaining || !ss?.authorized || ss?.running}>Send {Math.min(items.length, remaining)} now</Button>
          {ss?.running && <span>Sending…</span>}
        </div>
        <ErrorNote error={startSend.error} />
        {ss?.error && <p className="mt-2 text-sm text-danger">{ss.error}</p>}
        {(ss?.results?.length ?? 0) > 0 && ss && (
          <table className="mt-3 w-full text-sm"><tbody>
            {ss.results.map((r: J) => (
              <tr key={r.id} className="border-t"><td className="py-1">{r.name}</td><td>{r.to}</td><td>{r.kind}</td>
                <td><Badge tone={r.status === "sent" ? "green" : r.status === "error" ? "red" : "slate"}>{r.status === "preview" ? "would send" : r.status}</Badge> {r.error}</td></tr>
            ))}
          </tbody></table>
        )}
      </Card>
      {confirmSend && (
        <Modal title="Send these emails now?" onClose={() => setConfirmSend(false)}>
          <p className="mb-2 text-sm">{Math.min(items.length, remaining)} separate emails from <b>{sendFrom || "your Gmail account"}</b>, best first, with a short pause between each. This cannot be undone.</p>
          <ul className="mb-3 max-h-48 overflow-auto text-xs">{items.slice(0, remaining).map((x) => <li key={x.id}>{x.person.full_name} &lt;{x.to}&gt;</li>)}</ul>
          <div className="flex justify-end gap-2"><Button onClick={() => setConfirmSend(false)}>Cancel</Button><Button tone="danger" onClick={() => startSend.mutate(false)} disabled={startSend.isPending}>Send now</Button></div>
        </Modal>
      )}
      {!items.length && <p className="text-sm text-mist-500">Nothing ready. Approve drafts in <Link className="text-violet-300 underline" to="/review/queue">Review queue</Link>; follow-ups appear there when due.</p>}
      {items.map((x) => (
        <Card key={x.id} className="space-y-1">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <input type="checkbox" checked={picked.includes(x.id)} onChange={() => toggle(x.id)} />
            <strong>{x.person.full_name}</strong><span className="text-mist-500">{x.company.name}</span><span className="text-mist-500">&lt;{x.to}&gt;</span>
            {x.published ? <Badge tone="green">published</Badge> : <Badge tone="amber">guess, may bounce</Badge>}
            {x.kind !== "initial" && <Badge tone="blue">{x.kind === "final" ? "last note" : "follow-up"}</Badge>}
            <Badge tone="slate">score {x.score}</Badge>
            <span className="ml-auto flex gap-2">
              <a className="border border-mist-50 bg-mist-50 px-3 py-1 text-sm text-ink-950 hover:bg-mist-200" href={gmail(x, sendFrom)} target="_blank" rel="noreferrer" onClick={() => setOpened([...opened, x.id])}>Open in Gmail</a>
              <Button onClick={() => sent.mutate([x.id])} disabled={sent.isPending}>I sent it</Button>
            </span>
          </div>
          <div className="text-sm font-semibold">{x.subject}</div>
          <pre className="whitespace-pre-wrap font-sans text-xs text-mist-200">{x.body}</pre>
        </Card>
      ))}
    </div>
  );
}
