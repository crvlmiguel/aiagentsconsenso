import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
  Inbox, Bot, Users, LifeBuoy, BarChart3, UserPlus,
  Settings as SettingsIcon, Shield, LogOut, Database, Wand2,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { Logo } from "./Brand";

const items = [
  { section: "core", to: "/app/caixa", label: "Caixa de entrada", icon: Inbox, tid: "nav-caixa" },
  { section: "core", to: "/app/painel", label: "Painel", icon: BarChart3, tid: "nav-painel" },

  { section: "agents", heading: "Agentes" },
  { section: "agents", to: "/app/construtor", label: "Construtor", icon: Wand2, tid: "nav-construtor", badge: "NOVO" },
  { section: "agents", to: "/app/agentes", label: "Agentes IA", icon: Bot, tid: "nav-agentes" },
  { section: "agents", to: "/app/fontes", label: "Fontes de dados", icon: Database, tid: "nav-fontes" },

  { section: "crm", heading: "CRM" },
  { section: "crm", to: "/app/leads", label: "Leads", icon: Users, tid: "nav-leads" },
  { section: "crm", to: "/app/tickets", label: "Tickets", icon: LifeBuoy, tid: "nav-tickets" },

  { section: "admin", heading: "Conta" },
  { section: "admin", to: "/app/equipa", label: "Equipa", icon: UserPlus, tid: "nav-equipa" },
  { section: "admin", to: "/app/admin", label: "Admin", icon: Shield, tid: "nav-admin" },
  { section: "admin", to: "/app/definicoes", label: "Definições", icon: SettingsIcon, tid: "nav-definicoes" },
];

const Sidebar = () => {
  const { user, tenant, logout } = useAuth();
  const nav = useNavigate();

  return (
    <aside data-testid="sidebar" className="w-64 bg-white border-r border-[#E5EAF2] flex flex-col h-screen">
      <div className="px-5 py-5 border-b border-[#E5EAF2]">
        <button data-testid="sidebar-logo" onClick={() => nav("/app/caixa")} className="flex items-center hover:opacity-80">
          <Logo size={26} />
        </button>
      </div>

      <div className="px-5 py-4 border-b border-[#E5EAF2]">
        <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Organização</div>
        <div className="text-sm font-semibold mt-0.5 truncate">{tenant?.name || "—"}</div>
        <div className="flex items-center gap-1.5 mt-1">
          <span className="w-1.5 h-1.5 rounded-full bg-[#16A34A] live-dot" />
          <span className="text-[11px] text-[#5B6B82] uppercase tracking-wider">{tenant?.plan || "FREE"}</span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2">
        {items.map((it, i) => {
          if (it.heading) {
            return (
              <div key={`h-${i}`} className="text-[10px] font-bold text-[#9AA4B6] uppercase tracking-widest px-3 mt-4 mb-1">
                {it.heading}
              </div>
            );
          }
          return (
            <NavLink key={it.to} to={it.to} data-testid={it.tid}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium mb-0.5 transition-colors ${
                  isActive ? "bg-[#EAF2FF] text-[#0069FE]" : "text-[#2C3A52] hover:bg-[#F7F9FC]"
                }`
              }>
              <it.icon size={16} strokeWidth={2} />
              <span className="flex-1">{it.label}</span>
              {it.badge && <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#0069FE] text-white tracking-wider">{it.badge}</span>}
            </NavLink>
          );
        })}
      </nav>

      <div className="border-t border-[#E5EAF2] p-3">
        <div className="flex items-center gap-2 px-2 py-2 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-[#EAF2FF] text-[#0069FE] font-bold text-xs flex items-center justify-center">
            {(user?.name || "U").slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-semibold truncate text-[#0B1324]">{user?.name}</div>
            <div className="text-[11px] text-[#5B6B82] truncate">{user?.email}</div>
          </div>
        </div>
        <button data-testid="btn-logout" onClick={logout} className="btn-ghost w-full justify-center mt-2 text-[13px]">
          <LogOut size={14} /> Terminar sessão
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
