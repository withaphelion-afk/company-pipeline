import { useQuery } from "@tanstack/react-query";
import { api, J } from "../api";

/** Dropdown of the Google Maps searches that have been imported (for example "skin clinic in delhi"), with counts. */
export default function SearchSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const q = useQuery({ queryKey: ["lead-stats"], queryFn: () => api<J>("/leads/stats"), refetchInterval: 5000 });
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">All searches</option>
      {q.data?.searches?.map((s: J) => <option key={s.query} value={s.query}>{s.query} ({s.no_website} no site / {s.total})</option>)}
    </select>
  );
}
