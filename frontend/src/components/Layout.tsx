import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router";
import { useMeta } from "../api/client";

const NAV = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/moneyball", label: "Moneyball" },
  { to: "/players", label: "Players" },
  { to: "/matches", label: "Matches" },
  { to: "/teams", label: "Teams" },
  { to: "/managers", label: "Managers" },
  { to: "/models", label: "Models" },
];

type Theme = "system" | "light" | "dark";

function useTheme(): [Theme, (t: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem("theme") as Theme) || "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch {
      /* storage unavailable */
    }
  }, [theme]);
  return [theme, setTheme];
}

export default function Layout() {
  const meta = useMeta();
  const [theme, setTheme] = useTheme();
  const next: Theme = theme === "system" ? "dark" : theme === "dark" ? "light" : "system";
  const run = meta.data?.latest_run;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-[color-mix(in_oklab,var(--bg)_88%,transparent)] backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3 sm:px-6">
          <NavLink to="/" aria-label="Moneyball Scout home" className="flex shrink-0 items-center gap-2 font-semibold tracking-tight">
            <img src="/favicon.svg" alt="" width={24} height={24} />
            <span className="hidden sm:inline">Moneyball Scout</span>
          </NavLink>
          <nav className="-mb-px flex min-w-0 flex-1 gap-1 overflow-x-auto [scrollbar-width:none]">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}
                className={({ isActive }) =>
                  `whitespace-nowrap rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors ${
                    isActive ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink"
                  }`}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <button onClick={() => setTheme(next)} title={`Theme: ${theme}`} aria-label={`Theme: ${theme}. Switch to ${next}`}
            className="shrink-0 rounded-md border border-line px-2 py-1 text-[12px] text-ink-2 hover:text-ink">
            {theme === "system" ? "Auto" : theme === "dark" ? "Dark" : "Light"}
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-[12px] text-ink-3 sm:px-6">
        Data: API-Football (match stats) and Transfermarkt open dataset (market values).
        {run && <> Model run #{run.id}{run.data_cutoff && <>, data through {new Date(run.data_cutoff).toLocaleDateString()}</>}.</>}
      </footer>
    </div>
  );
}
