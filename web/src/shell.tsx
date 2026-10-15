import { ReactNode, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

export type Tab = { key: string; label: string; el: ReactNode };
export type Mod = { key: string; label: string; icon: string; tabs: Tab[] };
export type AppDef = { key: string; name: string; modules: Mod[] };

export function Shell({ app, apps }: { app: AppDef; apps: AppDef[] }) {
  const { module, tab } = useParams();
  const nav = useNavigate();
  const [menu, setMenu] = useState(false);
  const [switcher, setSwitcher] = useState(false);
  const mod = app.modules.find((m) => m.key === module) ?? app.modules[0];
  const cur = mod.tabs.find((t) => t.key === tab) ?? mod.tabs[0];
  const first = (a: AppDef) => `/${a.key}/${a.modules[0].key}/${a.modules[0].tabs[0].key}`;
  return (
    <div className="flex min-h-screen">
      <aside className={`${menu ? "block" : "hidden"} w-56 shrink-0 border-r border-line bg-ink-900 p-3 md:block`}>
        <div className="mb-4 px-2 text-sm font-bold">{app.name}</div>
        <nav className="space-y-1">
          {app.modules.map((m) => (
            <Link key={m.key} to={`/${app.key}/${m.key}/${m.tabs[0].key}`} onClick={() => setMenu(false)}
              className={`flex items-center gap-2 px-3 py-2 text-sm ${m.key === mod.key ? "bg-mist-50 text-ink-950" : "hover:bg-ink-800"}`}>
              <span className="w-4 text-center">{m.icon}</span>{m.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="flex items-center gap-3 border-b border-line bg-ink-900 px-4 py-2">
          <button className="border px-2 py-1 text-sm md:hidden" onClick={() => setMenu(!menu)}>Menu</button>
          <h1 className="text-base font-semibold">{mod.label}</h1>
          <div className="relative ml-auto">
            <button className="border px-3 py-1 text-sm hover:bg-ink-800" onClick={() => setSwitcher(!switcher)}>Apps ▾</button>
            {switcher && (
              <div className="absolute right-0 z-20 mt-1 w-56 border border-line bg-ink-900 p-1 ">
                {apps.map((a) => (
                  <button key={a.key} onClick={() => { setSwitcher(false); nav(first(a)); }}
                    className={`block w-full px-3 py-2 text-left text-sm hover:bg-ink-800 ${a.key === app.key ? "font-semibold" : ""}`}>
                    {a.key === app.key ? "✓ " : ""}{a.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </header>
        <main className="p-4">
          {mod.tabs.length > 1 && (
            <div className="mb-4 flex flex-wrap gap-1 border-b border-line pb-2">
              {mod.tabs.map((t) => (
                <Link key={t.key} to={`/${app.key}/${mod.key}/${t.key}`}
                  className={`px-3 py-1 text-sm ${t.key === cur.key ? "bg-mist-50 text-ink-950" : "hover:bg-ink-800"}`}>{t.label}</Link>
              ))}
            </div>
          )}
          {cur.el}
        </main>
      </div>
    </div>
  );
}
