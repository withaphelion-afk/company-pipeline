import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppDef, Shell } from "./shell";
import Companies from "./review/Companies";
import Contacts from "./review/Contacts";
import Jobs from "./review/Jobs";
import ImportLinkedin from "./review/Import";
import Send from "./review/Send";
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
import Find from "./maps/Find";
import Leads from "./maps/Leads";
import Pitch from "./maps/Pitch";
import Tracker from "./maps/Tracker";

// Five modules instead of fifteen links; each module groups related pages as tabs.
const pipeline: AppDef = {
  key: "pipeline", name: "Outreach Pipeline",
  modules: [
    { key: "run", label: "Run", icon: "▶", tabs: [
      { key: "search", label: "Search & run", el: <Search /> }, { key: "runs", label: "Live runs", el: <Runs /> },
      { key: "dashboard", label: "Dashboard", el: <Dashboard /> }, { key: "history", label: "History", el: <History /> }] },
    { key: "opportunities", label: "Opportunities", icon: "◆", tabs: [
      { key: "jobs", label: "Jobs", el: <Jobs /> }, { key: "companies", label: "Companies", el: <Companies /> }, { key: "contacts", label: "Contacts", el: <Contacts /> }] },
    { key: "outreach", label: "Outreach", icon: "✉", tabs: [
      { key: "queue", label: "Review drafts", el: <Queue /> }, { key: "send", label: "Bulk send", el: <Send /> },
      { key: "import", label: "Import LinkedIn", el: <ImportLinkedin /> }, { key: "suppression", label: "Suppression", el: <Suppression /> }] },
    { key: "automation", label: "Automation", icon: "⚙", tabs: [
      { key: "sources", label: "Sources", el: <Sources /> }, { key: "schedules", label: "Schedules", el: <Schedules /> }, { key: "cache", label: "Cache", el: <Cache /> }] },
    { key: "settings", label: "Settings & Safety", icon: "⚑", tabs: [{ key: "safety", label: "Safety", el: <Safety /> }] },
  ],
};
const maps: AppDef = {
  key: "maps", name: "Maps Leads",
  modules: [
    { key: "find", label: "Find", icon: "⌕", tabs: [{ key: "find", label: "Find", el: <Find /> }] },
    { key: "leads", label: "Leads", icon: "◆", tabs: [{ key: "leads", label: "Leads", el: <Leads /> }] },
    { key: "pitch", label: "Pitch", icon: "✉", tabs: [{ key: "pitch", label: "Pitch", el: <Pitch /> }] },
    { key: "tracker", label: "Tracker", icon: "▤", tabs: [{ key: "tracker", label: "Tracker", el: <Tracker /> }] },
  ],
};
const APPS = [pipeline, maps];

// Old links (/review/..., /control/...) keep working.
const LEGACY: Record<string, string> = {
  "review/jobs": "opportunities/jobs", "review/companies": "opportunities/companies", "review/contacts": "opportunities/contacts",
  "review/queue": "outreach/queue", "review/send": "outreach/send", "review/import": "outreach/import", "review/suppression": "outreach/suppression",
  "control/search": "run/search", "control/runs": "run/runs", "control/dashboard": "run/dashboard", "control/history": "run/history",
  "control/sources": "automation/sources", "control/schedules": "automation/schedules", "control/cache": "automation/cache", "control/safety": "settings/safety",
};

function Legacy() {
  const p = useLocation().pathname.replace(/^\/|\/$/g, "");
  return <Navigate to={`/pipeline/${LEGACY[p] ?? "run/search"}`} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/pipeline/opportunities/jobs" replace />} />
      <Route path="/pipeline/:module?/:tab?" element={<Shell app={pipeline} apps={APPS} />} />
      <Route path="/maps/:module?/:tab?" element={<Shell app={maps} apps={APPS} />} />
      <Route path="/review/*" element={<Legacy />} />
      <Route path="/control/*" element={<Legacy />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
