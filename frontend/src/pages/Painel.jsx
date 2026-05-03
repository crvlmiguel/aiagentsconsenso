import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { Inbox, Users, LifeBuoy, MessageSquare, TrendingUp } from "lucide-react";

const COLORS = ["#0069FE", "#16A34A", "#D97706", "#8B5CF6", "#EC4899", "#64748B"];

const Painel = () => {
  const [stats, setStats] = useState(null);
  useEffect(() => { api.get("/dashboard/stats").then(r => setStats(r.data)); }, []);

  if (!stats) return <div className="p-8 text-sm text-[#5B6B82]">A carregar…</div>;

  const KPI = ({ icon: Icon, label, value, color }) => (
    <div className="card-surface p-5">
      <div className="flex items-center justify-between">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: color + "18", color: color }}>
          <Icon size={18} />
        </div>
        <TrendingUp size={14} className="text-[#16A34A]" />
      </div>
      <div className="text-3xl font-display font-bold mt-4">{value}</div>
      <div className="text-xs text-[#5B6B82] mt-1 uppercase tracking-wider font-medium">{label}</div>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-8 space-y-6" data-testid="painel-page">
      <div>
        <h1 className="font-display text-2xl font-bold">Painel</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Visão geral do seu sistema operativo de IA.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KPI icon={Inbox} label="Conversas" value={stats.conversations} color="#0069FE" />
        <KPI icon={MessageSquare} label="Em aberto" value={stats.open_conversations} color="#D97706" />
        <KPI icon={MessageSquare} label="Mensagens" value={stats.messages} color="#8B5CF6" />
        <KPI icon={Users} label="Leads" value={stats.leads} color="#16A34A" />
        <KPI icon={LifeBuoy} label="Tickets abertos" value={stats.open_tickets} color="#DC2626" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card-surface p-5">
          <div className="font-display font-semibold">Conversas por canal</div>
          <p className="text-xs text-[#5B6B82] mt-0.5">Distribuição ao longo dos canais ligados.</p>
          <div className="mt-4" style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={stats.by_channel}>
                <XAxis dataKey="channel" stroke="#5B6B82" fontSize={12} />
                <YAxis stroke="#5B6B82" fontSize={12} />
                <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 10 }} />
                <Bar dataKey="count" fill="#0069FE" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card-surface p-5">
          <div className="font-display font-semibold">Leads por estado</div>
          <p className="text-xs text-[#5B6B82] mt-0.5">Funil de qualificação.</p>
          <div className="mt-4" style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={stats.by_stage} dataKey="count" nameKey="stage" innerRadius={55} outerRadius={90} paddingAngle={2}>
                  {stats.by_stage.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Painel;
