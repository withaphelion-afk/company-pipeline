import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { FILL, Pager, SortTh, useFitRows, useSort } from "../fit";
import { Badge, Card, ErrorNote, td, th } from "../ui";

export default function Contacts() {
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [intent, setIntent] = useState("");
  const [page, setPage] = useState(1);
  const [sort, order, onSort] = useSort("score", "desc");
  const [boxRef, rows] = useFitRows(56, 38);
  const qs = new URLSearchParams();
  if (role) qs.set("role_type", role);
  if (status) qs.set("email_status", status);
  if (intent) qs.set("intent", intent);
  const q = useQuery({ queryKey: ["people", qs.toString()], queryFn: () => api<J[]>(`/people?${qs}`) });
  const people = useMemo(() => {
    const key = (p: J) => (sort === "score" ? p.score : sort === "conf" ? Math.max(0, ...p.emails.map((e: J) => e.confidence)) : String(p[sort] ?? "").toLowerCase());
    return [...(q.data ?? [])].sort((a, b) => (key(a) > key(b) ? 1 : key(a) < key(b) ? -1 : 0) * (order === "asc" ? 1 : -1));
  }, [q.data, sort, order]);
  useEffect(() => setPage(1), [role, status, intent, sort, order, rows]);
  const h = (label: string, k: string, first: "asc" | "desc" = "asc") => <SortTh label={label} k={k} sort={sort} order={order} onSort={onSort} className={th} first={first} />;
  return (
    <Card className={FILL}>
      <div className="mb-3 flex shrink-0 flex-wrap items-center gap-2 text-sm">
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">Any role</option>{["founder", "investor", "recruiter", "exec", "other"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <select value={intent} onChange={(e) => setIntent(e.target.value)}>
          <option value="">Any goal</option>{["hire", "invest", "advise"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Any email status</option>{["unverified", "verified", "bounced", "opted_out"].map((r) => <option key={r}>{r}</option>)}
        </select>
        <span className="ml-auto text-mist-500">{people.length} contacts</span>
      </div>
      <ErrorNote error={q.error} />
      <div ref={boxRef} className="min-h-0 flex-1 overflow-hidden">
        <table className="w-full table-fixed">
          <colgroup><col className="w-20" /><col /><col className="w-48" /><col className="w-28" /><col className="w-80" /></colgroup>
          <thead><tr className="h-[38px]">{h("Score", "score", "desc")}{h("Person", "full_name")}{h("Company", "company_name")}{h("Role", "role_type")}{h("Emails", "conf", "desc")}</tr></thead>
          <tbody>
            {people.slice((page - 1) * rows, page * rows).map((p) => (
              <tr key={p.id} className="h-14 border-t">
                <td className={td}><b>{p.score}</b><div>{p.intent && <Badge tone={p.intent === "hire" ? "green" : p.intent === "invest" ? "amber" : "blue"}>{p.intent}</Badge>}</div></td>
                <td className={`${td} overflow-hidden`}><div className="truncate">{p.full_name}</div><div className="truncate text-xs text-mist-500">{p.title}</div><div className="truncate text-xs text-mist-500">{p.reason}</div></td>
                <td className={`${td} truncate`}>{p.company_name}</td><td className={td}><Badge>{p.role_type}</Badge></td>
                <td className={`${td} overflow-hidden`}>
                  {p.emails.slice(0, 2).map((e: J) => <div key={e.id} className="flex items-center gap-2"><span className="truncate text-xs">{e.address}</span><Badge>{e.status}</Badge><span className="text-xs text-mist-500">{e.confidence}</span></div>)}
                  {p.emails.length > 2 && <div className="text-xs text-mist-500">+{p.emails.length - 2} more</div>}
                  {!p.emails.length && <span className="text-xs text-mist-500">none yet</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} total={people.length} size={rows} onPage={setPage} />
    </Card>
  );
}
