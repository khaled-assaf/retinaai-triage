import { Link, NavLink } from "react-router-dom";
import { ScanEye } from "lucide-react";
import { useHealth } from "../../hooks/useHealth";

const NAV = [
  { to: "/", label: "Home", end: true },
  { to: "/screening", label: "Screening" },
  { to: "/queue", label: "Triage Queue" },
  { to: "/followups", label: "Follow-ups" },
];

function HealthDot() {
  const { data, error } = useHealth();
  return (
    <span
      title={error ? "Backend unreachable" : `API ok · ${data?.model_version ?? ""}`}
      className={`size-2 rounded-full ${error ? "bg-red-500" : "animate-pulse bg-green-500"}`}
    />
  );
}

export default function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/70 bg-white/75 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-6">
        <Link to="/" className="flex shrink-0 items-center gap-2.5">
          <span className="grid size-8.5 place-items-center rounded-xl bg-linear-to-br from-teal-500 to-teal-700 text-white shadow-md shadow-teal-500/25">
            <ScanEye className="size-4.5" />
          </span>
          <span className="hidden text-sm font-semibold tracking-tight text-slate-900 sm:block">
            RetinaAI Nexus
          </span>
        </Link>

        {/* Segmented pill nav */}
        <nav className="mx-auto flex items-center gap-0.5 rounded-full bg-slate-100/90 p-1">
          {NAV.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `rounded-full px-3.5 py-1.5 text-[13px] font-medium transition ${
                  isActive
                    ? "bg-white text-slate-900 shadow-xs"
                    : "text-slate-500 hover:text-slate-900"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-3">
          <span className="hidden items-center gap-1.5 text-[11px] text-slate-400 md:flex">
            <HealthDot />
            API
          </span>
          <Link
            to="/screening"
            className="rounded-full bg-teal-700 px-4 py-2 text-xs font-semibold text-white transition hover:bg-teal-800"
          >
            Start screening
          </Link>
        </div>
      </div>
    </header>
  );
}
