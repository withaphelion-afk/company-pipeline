import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { Badge, Card, ConfBar, ErrorNote, td, th } from "../ui";

export default function Contacts() {
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [intent, setIntent] = useState("");
  const qs = new URLSearchParams();
  if (role) qs.set("role_type", role);
  if (status) qs.set("email_status", status);
  if (intent) qs.set("intent", intent);
  const q = useQuery({ queryKey: ["people", qs.toString()], queryFn: () => api<J[]>(`/people?${qs}`) });
  return (
    <Card>
      <div className="mb-3 flex gap-2">
        <select className="rounded border px-2 py-1 text-sm" value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Any role</option>{["founder", "investor", "recruiter", "exec", "other"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <select className="rounded border px-2 py-1 text-sm" value={intent} onChange={(e) => setIntent(e.target.value)}>
          <option value="">Any goal</option>{["hire", "invest", "advise"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <select className="rounded border px-2 py-1 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any email status</option>{["unverified", "verified", "bounced", "opted_out"].map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>
      <ErrorNote error={q.error} />
      <table className="w-full">
        <thead><tr><th className={th}>Score</th><th className={th}>Person</th><th className={th}>Company</th><th className={th}>Role</th><th className={th}>Emails</th></tr></thead>
        <tbody>
          {q.data?.map((p) => (
            <tr key={p.id} className="border-t align-top">
              <td className={td}><b>{p.score}</b><div>{p.intent && <Badge tone={p.intent === "hire" ? "green" : p.intent === "invest" ? "amber" : "blue"}>{p.intent}</Badge>}</div></td>
              <td className={td}>{p.full_name}<div className="text-xs text-slate-500">{p.title}</div><div className="text-xs text-slate-400">{p.reason}</div></td>
              <td className={td}>{p.company_name}</td><td className={td}><Badge>{p.role_type}</Badge></td>
              <td className={td}>
                {p.emails.map((e: J) => (
                  <div key={e.id} className="mb-1 flex items-center gap-2"><span className="text-xs">{e.address}</span><ConfBar value={e.confidence} /><Badge>{e.status}</Badge></div>
                ))}
                {!p.emails.length && <span className="text-xs text-slate-400">none yet</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
