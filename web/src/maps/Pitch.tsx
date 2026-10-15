import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, J } from "../api";
import { Button, Card, ErrorNote } from "../ui";
import SearchSelect from "./SearchSelect";
import { pitchFor, whatsapp } from "./util";

export default function Pitch() {
  const qc = useQueryClient();
  const tpl = useQuery({ queryKey: ["pitch"], queryFn: () => api<J>("/leads/pitch") });
  const [search, setSearch] = useState("");
  const leads = useQuery({ queryKey: ["leads", "pitch", search], queryFn: () => api<J>(`/leads?site=none&status=new&page_size=50${search ? `&search=${encodeURIComponent(search)}` : ""}`) });
  const [text, setText] = useState("");
  useEffect(() => { if (tpl.data) setText(tpl.data.template); }, [tpl.data]);
  const save = useMutation({ mutationFn: () => api("/leads/pitch", "PUT", { template: text }), onSuccess: () => qc.invalidateQueries({ queryKey: ["pitch"] }) });
  const mark = useMutation({
    mutationFn: (id: number) => api(`/leads/${id}`, "PATCH", { status: "contacted" }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["leads"] }); qc.invalidateQueries({ queryKey: ["lead-stats"] }); },
  });
  return (
    <div className="space-y-4">
      <Card title="Pitch message (use {name}, {category}, {area})">
        <textarea className="h-32 w-full border p-2 text-sm" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-2 flex items-center gap-3">
          <Button tone="primary" onClick={() => save.mutate()} disabled={save.isPending}>Save</Button>
          <span className="text-xs text-mist-500">Keep it honest and short, and keep the opt-out line so people can say no. You send each message yourself.</span>
        </div>
        <ErrorNote error={save.error} />
      </Card>
      <div className="flex items-center gap-2 text-sm"><span className="text-mist-500">Show leads from</span><SearchSelect value={search} onChange={setSearch} /></div>
      <Card title={`Next to contact (${leads.data?.total ?? 0} new, verified no website, best first)`}>
        {leads.data?.items.map((l: J) => {
          const msg = pitchFor(text || tpl.data?.template || "", l);
          const wa = whatsapp(l.phone, msg);
          return (
            <div key={l.id} className="border-t py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2"><strong>{l.name}</strong><span className="text-mist-500">{l.category} · {l.address}</span><span className="text-mist-500">{l.phone}</span><span className="ml-auto text-xs">score {l.score}</span></div>
              <p className="my-2 whitespace-pre-wrap bg-ink-800 p-2 text-xs text-mist-200">{msg}</p>
              <div className="flex gap-2">
                {wa ? <a className="border border-online bg-online px-3 py-1 text-ink-950" href={wa} target="_blank" rel="noreferrer" onClick={() => mark.mutate(l.id)}>Open WhatsApp</a> : <span className="text-xs text-mist-500">no usable phone number</span>}
                <Button onClick={() => navigator.clipboard?.writeText(msg)}>Copy</Button>
                <Button onClick={() => mark.mutate(l.id)}>Mark contacted</Button>
              </div>
            </div>
          );
        })}
        {leads.data?.items.length === 0 && <p className="text-sm text-mist-500">No new leads without a website yet. Use Find to bring some in.</p>}
      </Card>
    </div>
  );
}
