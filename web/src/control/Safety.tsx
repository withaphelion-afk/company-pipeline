import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, J } from "../api";
import { Badge, Button, Card, ErrorNote } from "../ui";

const RULES = [
  "Nothing is ever sent: the sender module is a stub and approving a draft only marks it approved.",
  "robots.txt is checked (cached per host, crawl-delay honoured) before every HTML fetch.",
  "No LinkedIn scraping, logins, CAPTCHA, paywall or rate-limit bypassing.",
  "Per-domain rate limit; per-source minimum 1 second between requests.",
  "SMTP RCPT probing is off unless SMTP_PROBE_ENABLED=true AND the domain is allowlisted; it never sends mail.",
  "Catch-all addresses are never marked verified.",
  "The suppression list is honoured in verify_email, draft and approval.",
  "Every external request is logged (source, URL, status, timestamp) to data/requests.log.",
  "Use `python -m pipeline purge --person <id>` to delete a person and all their emails and drafts.",
];

export default function Safety() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api<J>("/control/settings"), refetchInterval: 5000 });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["settings"] }); qc.invalidateQueries({ queryKey: ["status"] }); };
  const kill = useMutation({ mutationFn: (enabled: boolean) => api("/control/kill-switch", "POST", { enabled }), onSuccess: refresh });
  const set = useMutation({ mutationFn: (p: J) => api("/control/settings", "PUT", p), onSuccess: refresh });
  const s = q.data;
  return (
    <div className="space-y-4">
      <ErrorNote error={q.error ?? kill.error ?? set.error} />
      <Card className={s?.kill_switch ? "border-danger/50 bg-ink-800" : ""}>
        <div className="flex items-center gap-4">
          <Button tone={s?.kill_switch ? "default" : "danger"} className="px-8 py-4 text-lg font-bold" disabled={!s || kill.isPending} onClick={() => kill.mutate(!s?.kill_switch)}>
            {s?.kill_switch ? "RELEASE KILL SWITCH" : "KILL SWITCH"}
          </Button>
          <p className="text-sm">{s?.kill_switch ? <Badge tone="red">ON</Badge> : <Badge tone="green">off</Badge>}{" "}
            When on, new jobs are rejected (423), workers skip queued jobs, and running jobs stop at the next item.</p>
        </div>
      </Card>
      <Card title="Defaults">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!s?.dry_run_default} onChange={(e) => set.mutate({ dry_run_default: e.target.checked })} /> Dry run by default</label>
        <p className="mt-2 text-sm">Daily send cap: <b>{s?.daily_send_cap}</b> <span className="text-xs text-mist-500">(display only; sending is not implemented)</span></p>
        <p className="mt-1 text-sm">SMTP probing: <Badge tone={s?.smtp_probe_enabled ? "amber" : "green"}>{s?.smtp_probe_enabled ? "enabled via env" : "disabled"}</Badge></p>
        <p className="mt-1 text-sm">Suppression entries: <b>{s?.suppression_count}</b> · <Link className="text-violet-300 underline" to="/review/suppression">manage</Link></p>
      </Card>
      <Card title="Enforced compliance rules (read-only)"><ul className="list-disc space-y-1 pl-5 text-sm">{RULES.map((r) => <li key={r}>{r}</li>)}</ul></Card>
    </div>
  );
}
