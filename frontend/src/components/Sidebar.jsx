import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Inbox, Bot, Users, LifeBuoy, Plug, BarChart3,
  UserPlus, Settings, Shield, LogOut, CircleDot,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { CPLogo } from "./Brand";

const items = [
  { to: "/app/inbox", label: "Inbox", icon: Inbox, tid: "nav-inbox" },
  { to: "/app/agents", label: "Agents", icon: Bot, tid: "nav-agents" },
  { to: "/app/leads", label: "Leads", icon: Users, tid: "nav-leads" },
  { to: "/app/tickets", label: "Tickets", icon: LifeBuoy, tid: "nav-tickets" },
  { to: "/app/integrations", label: "Channels", icon: Plug, tid: "nav-integrations" },
  { to: "/app/analytics", label: "Analytics", icon: BarChart3, tid: "nav-analytics" },
  { to: "/app/team", label: "Team", icon: UserPlus, tid: "nav-team" },
  { to: "/app/admin", label: "Admin", icon: Shield, tid: "nav-admin" },
  { to: "/app/settings", label: "Settings", icon: Settings, tid: "nav-settings" },
];

const Sidebar = () => {
  const { user, tenant, logout } = useAuth();
  const nav = useNavigate();

  return (
    <aside
      data-testid="sidebar"
      className="w-64 border-r border-zinc-800 flex flex-col h-screen bg-[#09090B]"
    >
      <div className="p-4 border-b border-zinc-800">
        <button
          data-testid="sidebar-logo"
          onClick={() => nav("/app/inbox")}
          className="flex items-center gap-2 hover:opacity-80"
        >
          <CPLogo size={24} />
        </button>
      </div>

      <div className="px-4 py-3 border-b border-zinc-800">
        <div className="label-mono">Tenant</div>
        <div className="text-sm font-bold truncate">{tenant?.name || "—"}</div>
        <div className="mono text-[10px] text-zinc-500 mt-1 flex items-center gap-1">
          <CircleDot size={8} className="text-[#22C55E] dot-live" />
          <span>{tenant?.plan?.toUpperCase() || "FREE"}</span>
          <span className="text-zinc-700">·</span>
          <span className="truncate">{tenant?.slug}</span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            data-testid={it.tid}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors border-l-2 ${
                isActive
                  ? "bg-zinc-900 border-white text-white"
                  : "border-transparent text-zinc-400 hover:bg-zinc-900/50 hover:text-white"
              }`
            }
          >
            <it.icon size={16} strokeWidth={1.75} />
            <span className="flex-1">{it.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-zinc-800 p-3">
        <div className="flex items-center gap-2 mb-2 px-1">
          <div className="w-8 h-8 border border-zinc-700 flex items-center justify-center mono text-xs">
            {(user?.name || "U").slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold truncate">{user?.name}</div>
            <div className="mono text-[10px] text-zinc-500 truncate uppercase">
              {user?.role}
            </div>
          </div>
        </div>
        <button
          data-testid="btn-logout"
          onClick={logout}
          className="w-full flex items-center gap-2 px-3 py-2 text-xs mono uppercase tracking-widest border border-zinc-800 hover:border-zinc-500 hover:bg-zinc-900 transition-colors"
        >
          <LogOut size={14} /> Logout
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
