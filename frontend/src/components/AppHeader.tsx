import { NavLink } from "react-router-dom";

interface Props {
  title: string;
}

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/simulator", label: "Simulator" },
  { to: "/cyp450", label: "CYP450" },
  { to: "/analysis", label: "Analysis" },
  { to: "/scenarios", label: "Scenarios" },
  { to: "/report", label: "Report" },
];

export default function AppHeader({ title }: Props) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between py-4">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-widest text-indigo-500">
              NeuroTrace
            </p>
            <h1 className="text-xl font-bold text-slate-800">{title}</h1>
          </div>

          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm font-medium transition ${
                    isActive
                      ? "text-indigo-700 underline underline-offset-4 decoration-2 decoration-indigo-500"
                      : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
}
