import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";

const COLORS = ["#FF5500", "#FAFAFA", "#22C55E", "#EAB308", "#A1A1AA", "#3F3F46"];

const Analytics = () => {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.get("/dashboard/stats").then(r => setStats(r.data));
  }, []);

  if (!stats) return <div className="p-8 mono text-xs text-zinc-500">Loading…</div>;

  const KPI = ({ label, value, accent }) => (
    <div className="border border-zinc-800 p-4">
      <div className="label-mono">{label}</div>
      <div className={`text-4xl font-extrabold mt-2 tracking-tight ${accent || ""}`}>{value}</div>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6" data-testid="analytics">
      <div>
        <h1 className="text-xl font-bold uppercase tracking-tight">Analytics</h1>
        <p className="text-sm text-zinc-500 mt-1">Real-time operational metrics.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <KPI label="CONVERSATIONS" value={stats.conversations} />
        <KPI label="OPEN (AI + HUMAN)" value={stats.open_conversations} accent="text-[#FF5500]" />
        <KPI label="MESSAGES" value={stats.messages} />
        <KPI label="LEADS" value={stats.leads} accent="text-[#22C55E]" />
        <KPI label="OPEN TICKETS" value={stats.open_tickets} accent="text-[#EAB308]" />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="border border-zinc-800 p-4">
          <div className="label-mono mb-4">CONVERSATIONS BY CHANNEL</div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={stats.by_channel}>
                <XAxis dataKey="channel" stroke="#A1A1AA" fontSize={10} />
                <YAxis stroke="#A1A1AA" fontSize={10} />
                <Tooltip contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 0 }} />
                <Bar dataKey="count" fill="#FF5500" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-zinc-800 p-4">
          <div className="label-mono mb-4">LEADS BY STAGE</div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={stats.by_stage} dataKey="count" nameKey="stage" outerRadius={90} label>
                  {stats.by_stage.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: "#18181B", border: "1px solid #27272A", borderRadius: 0 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
