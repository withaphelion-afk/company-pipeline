import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Companies from "./review/Companies";
import Contacts from "./review/Contacts";
import Queue from "./review/Queue";
import Suppression from "./review/Suppression";
import Dashboard from "./control/Dashboard";
import Runs from "./control/Runs";
import Schedules from "./control/Schedules";
import Sources from "./control/Sources";
import Safety from "./control/Safety";
import History from "./control/History";
import Cache from "./control/Cache";
import { token } from "./api";

const review = [["companies", "Companies"], ["contacts", "Contacts"], ["queue", "Review queue"], ["suppression", "Suppression"]];
const control = [["dashboard", "Dashboard"], ["runs", "Live runs"], ["schedules", "Schedules"], ["sources", "Sources"], ["safety", "Safety"], ["history", "History"], ["cache", "Cache"]];

function Nav({ base, items }: { base: string; items: string[][] }) {
  return (
    <nav className="flex flex-wrap gap-1">
      {items.map(([p, label]) => (
        <NavLink key={p} to={`${base}/${p}`} className={({ isActive }) => `rounded px-3 py-1 text-sm ${isActive ? "bg-slate-900 text-white" : "hover:bg-slate-200"}`}>{label}</NavLink>
      ))}
    </nav>
  );
}

export default function App() {
  const setToken = () => {
    const t = prompt("Control API token (leave empty for localhost-only mode)", token());
    if (t !== null) try { localStorage.setItem("control_token", t); } catch { /* storage unavailable */ }
  };
  return (
    <div className="mx-auto max-w-7xl p-4">
      <header className="mb-4 flex flex-wrap items-center gap-6 border-b border-slate-200 pb-3">
        <h1 className="text-lg font-bold">Pipeline</h1>
        <div className="flex flex-wrap gap-6">
          <div><div className="mb-1 text-xs uppercase text-slate-400">Review</div><Nav base="/review" items={review} /></div>
          <div><div className="mb-1 text-xs uppercase text-slate-400">Control</div><Nav base="/control" items={control} /></div>
        </div>
        <button onClick={setToken} className="ml-auto text-xs text-slate-500 underline">API token</button>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/review/queue" replace />} />
        <Route path="/review/companies" element={<Companies />} />
        <Route path="/review/contacts" element={<Contacts />} />
        <Route path="/review/queue" element={<Queue />} />
        <Route path="/review/suppression" element={<Suppression />} />
        <Route path="/control" element={<Navigate to="/control/dashboard" replace />} />
        <Route path="/control/dashboard" element={<Dashboard />} />
        <Route path="/control/runs" element={<Runs />} />
        <Route path="/control/schedules" element={<Schedules />} />
        <Route path="/control/sources" element={<Sources />} />
        <Route path="/control/safety" element={<Safety />} />
        <Route path="/control/history" element={<History />} />
        <Route path="/control/cache" element={<Cache />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}
