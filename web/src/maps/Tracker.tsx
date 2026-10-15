import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";
import { Card } from "../ui";
import Leads from "./Leads";
import { STATUSES } from "./util";

export default function Tracker() {
  const s = useQuery({ queryKey: ["lead-stats"], queryFn: () => api<J>("/leads/stats"), refetchInterval: 5000 });
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3 md:grid-cols-6">
        {STATUSES.map((st) => <Card key={st}><div className="text-xs uppercase text-mist-500">{st}</div><div className="font-display text-3xl font-light">{s.data?.by_status?.[st] ?? 0}</div></Card>)}
      </div>
      <Leads />
    </div>
  );
}
