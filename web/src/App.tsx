import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import Companies from "./review/Companies";
import Contacts from "./review/Contacts";
import Jobs from "./review/Jobs";
import ImportLinkedin from "./review/Import";
import Queue from "./review/Queue";
import Suppression from "./review/Suppression";
import Dashboard from "./control/Dashboard";
import Search from "./control/Search";
import Runs from "./control/Runs";
import Schedules from "./control/Schedules";
import Sources from "./control/Sources";
import Safety from "./control/Safety";
import History from "./control/History";
import Cache from "./control/Cache";

const review = [["jobs", "Remote jobs"], ["companies", "Companies"], ["contacts", "Contacts"], ["queue", "Review queue"], ["import", "Import LinkedIn"], ["suppression", "Suppression"]];
const control = [["search", "Search & run"], ["dashboard", "Dashboard"], ["runs", "Live runs"], ["schedules", "Schedules"], ["sources", "Sources"], ["safety", "Safety"], ["history", "History"], ["cache", "Cache"]];

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
  return (
    <div className="mx-auto max-w-7xl p-4">
      <header className="mb-4 flex flex-wrap items-center gap-6 border-b border-slate-200 pb-3">
        <h1 className="text-lg font-bold">Pipeline</h1>
        <div className="flex flex-wrap gap-6">
          <div><div className="mb-1 text-xs uppercase text-slate-400">Review</div><Nav base="/review" items={review} /></div>
          <div><div className="mb-1 text-xs uppercase text-slate-400">Control</div><Nav base="/control" items={control} /></div>
        </div>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/review/jobs" replace />} />
        <Route path="/review/jobs" element={<Jobs />} />
        <Route path="/review/import" element={<ImportLinkedin />} />
        <Route path="/review/companies" element={<Companies />} />
        <Route path="/review/contacts" element={<Contacts />} />
        <Route path="/review/queue" element={<Queue />} />
        <Route path="/review/suppression" element={<Suppression />} />
        <Route path="/control" element={<Navigate to="/control/search" replace />} />
        <Route path="/control/search" element={<Search />} />
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
