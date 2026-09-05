import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  ClipboardCheck,
  FileStack,
  GitBranch,
  LayoutDashboard,
  Table2,
  LogOut,
  Scale,
  Settings,
  Shield,
  TestTubes,
  Ticket,
  Workflow,
} from "lucide-react";
import { AuthAPI, setToken } from "../api/client";

const NAV = [
  { to: "/", label: "Command Center", icon: LayoutDashboard },
  { to: "/tickets", label: "Tickets", icon: Ticket },
  { to: "/workspace", label: "Change Workspace", icon: Workflow },
  { to: "/rules", label: "Rule Explorer", icon: GitBranch },
  { to: "/configurations", label: "Configuration Matrix", icon: Table2 },
  { to: "/testing", label: "Testing Lab", icon: TestTubes },
  { to: "/approvals", label: "Approvals", icon: ClipboardCheck },
  { to: "/deployments", label: "Deployments", icon: Activity },
  { to: "/versions", label: "Rule Versions", icon: FileStack },
  { to: "/audit", label: "Audit & Governance", icon: Shield },
  { to: "/analytics", label: "Analytics", icon: Scale },
  { to: "/admin", label: "Administration", icon: Settings },
];

export function AppLayout() {
  const nav = useNavigate();
  const me = useQuery({ queryKey: ["me"], queryFn: AuthAPI.me });
  return (
    <div className="h-screen flex overflow-hidden">
      <aside className="w-[240px] shrink-0 h-full border-r border-ink-600 bg-ink-900 flex flex-col overflow-hidden">
        <div className="px-5 py-5 border-b border-ink-600 shrink-0">
          <div className="text-[11px] uppercase tracking-[0.22em] text-brass-400">Medical Affairs</div>
          <div className="text-lg font-semibold mt-1">MLR RuleOps</div>
          <div className="text-xs text-mist-500 mt-1">Regulatory rule change platform</div>
        </div>
        <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] ${
                  isActive ? "bg-ink-700 text-mist-100" : "text-mist-500 hover:bg-ink-800 hover:text-mist-300"
                }`
              }
            >
              <item.icon size={15} />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-ink-600 text-xs shrink-0">
          <div className="text-mist-300">{me.data?.full_name}</div>
          <div className="text-mist-500 mono">{me.data?.roles?.join(" · ")}</div>
          <button
            className="mt-3 flex items-center gap-2 text-mist-500 hover:text-mist-100"
            onClick={() => {
              setToken(null);
              nav("/login");
            }}
          >
            <LogOut size={13} /> Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 h-full overflow-y-auto bg-ink-950">
        <Outlet />
      </main>
    </div>
  );
}
