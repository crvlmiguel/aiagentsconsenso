import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line,
  CartesianGrid, Legend,
} from "recharts";
import {
  TrendingUp, MessageSquare, Users, Target, Flame, Thermometer, Snowflake,
  ArrowDownRight, RefreshCw,
} from "lucide-react";

const Stat = ({ label, value, sub, color = "#0069FE", Icon }) => (
  <div className="card-surface p-4" data-testid={`analytics-stat-${label.toLowerCase().replace(/\s+/g, "-")}`}>
    <div className="flex items-center gap-2 text-[12px] text-[#5B6B82]">
      {Icon && <Icon size={13} style={{ color }} />} {label}
    </div>
    <div className="text-2xl font-display font-bold mt-1" style={{ color }}>{value}</div>
    {sub && <div className="text-[11px] text-[#5B6B82] mt-0.5">{sub}</div>}
  </div>
);

const Analytics = () => {
  const [agents, setAgents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/agents").then(r => {
      setAgents(r.data || []);
      if (r.data?.length) setSelectedId(r.data[0].id);
    });
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    api.get(`/agents/${selectedId}/analytics?days=${days}`)
      .then(r => setData(r.data))
      .finally(() => setLoading(false));
  }, [selectedId, days]);

  const selectedAgent = agents.find(a => a.id === selectedId);

  return (
    <div className="space-y-6" data-testid="analytics-page">
      <div>
        <h1 className="text-3xl font-display font-bold">Analytics avançada</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Performance por agente — conversões, qualificação, top icebreakers e funil.</p>
      </div>

      {/* Controls */}
      <div className="card-surface p-4 flex flex-wrap items-center gap-3">
        <label className="text-xs text-[#5B6B82] font-medium">Agente:</label>
        <select data-testid="analytics-agent-select"
          value={selectedId || ""}
          onChange={e => setSelectedId(e.target.value)}
          className="form-input text-sm py-1.5 px-3 min-w-[200px]">
          {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>

        <label className="text-xs text-[#5B6B82] font-medium ml-2">Período:</label>
        <select data-testid="analytics-days-select"
          value={days}
          onChange={e => setDays(parseInt(e.target.value, 10))}
          className="form-input text-sm py-1.5 px-3">
          <option value={7}>7 dias</option>
          <option value={30}>30 dias</option>
          <option value={90}>90 dias</option>
        </select>

        <button data-testid="analytics-refresh"
          onClick={() => { setData(null); setSelectedId(selectedId); api.get(`/agents/${selectedId}/analytics?days=${days}`).then(r => setData(r.data)); }}
          className="btn-ghost text-xs flex items-center gap-1 ml-auto">
          <RefreshCw size={12} /> Recarregar
        </button>
      </div>

      {loading && !data && <div className="text-sm text-[#5B6B82]">A carregar…</div>}
      {!loading && data && (
        <>
          {/* KPI row */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Conversas" value={data.totals.conversations} Icon={MessageSquare} />
            <Stat label="Mensagens" value={data.totals.messages} Icon={MessageSquare} color="#16A34A" />
            <Stat label="Leads capturados" value={data.totals.leads} Icon={Users} color="#D97706" />
            <Stat label="Taxa de conversão"
              value={`${data.totals.conversion_rate}%`}
              sub={`${data.totals.leads}/${data.totals.conversions || data.totals.conversations} convos`}
              Icon={Target} color="#8B5CF6" />
          </div>

          {/* Daily trend */}
          <div className="card-surface p-5" data-testid="analytics-daily">
            <div className="flex items-center gap-2 font-display font-semibold">
              <TrendingUp size={16} className="text-[#0069FE]" /> Evolução diária
            </div>
            <p className="text-xs text-[#5B6B82] mt-0.5">Conversas vs leads — últimos {days} dias.</p>
            <div className="mt-4" style={{ width: "100%", height: 240 }}>
              <ResponsiveContainer width="99%" height="100%">
                <LineChart data={data.daily_series}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E5EAF2" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} interval="preserveStartEnd"
                    tickFormatter={(d) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 10 }} />
                  <Legend />
                  <Line type="monotone" dataKey="conversations" stroke="#0069FE" strokeWidth={2} dot={false} name="Conversas" />
                  <Line type="monotone" dataKey="leads" stroke="#D97706" strokeWidth={2} dot={false} name="Leads" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Two-column: qualification + funnel */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <div className="card-surface p-5" data-testid="analytics-qualification">
              <div className="flex items-center gap-2 font-display font-semibold">
                <Flame size={16} className="text-[#DC2626]" /> Qualificação de leads
              </div>
              <p className="text-xs text-[#5B6B82] mt-0.5">Distribuição por temperatura — auto-classificado pela IA.</p>
              <div className="mt-4 space-y-2">
                {[
                  { k: "quente", label: "Quente", color: "#DC2626", Icon: Flame, bg: "#FEE2E2" },
                  { k: "morno", label: "Morno", color: "#D97706", Icon: Thermometer, bg: "#FEF3C7" },
                  { k: "frio", label: "Frio", color: "#0EA5E9", Icon: Snowflake, bg: "#DBEAFE" },
                  { k: "outros", label: "Sem classificação", color: "#5B6B82", Icon: MessageSquare, bg: "#F1F5F9" },
                ].map(t => {
                  const v = data.qualification_breakdown[t.k] || 0;
                  const total = Object.values(data.qualification_breakdown).reduce((a, b) => a + b, 0) || 1;
                  const pct = Math.round((v / total) * 100);
                  return (
                    <div key={t.k} data-testid={`qual-${t.k}`}
                      className="flex items-center gap-3 p-2.5 rounded-lg border border-[#EEF1F7]">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: t.bg, color: t.color }}>
                        <t.Icon size={14} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium" style={{ color: t.color }}>{t.label}</span>
                          <span className="text-sm font-semibold">{v} <span className="text-[#5B6B82] text-xs">({pct}%)</span></span>
                        </div>
                        <div className="mt-1.5 h-1.5 rounded-full bg-[#F1F5F9] overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${pct}%`, background: t.color }} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card-surface p-5" data-testid="analytics-funnel">
              <div className="flex items-center gap-2 font-display font-semibold">
                <ArrowDownRight size={16} className="text-[#0069FE]" /> Funil de conversão
              </div>
              <p className="text-xs text-[#5B6B82] mt-0.5">Visitantes → engaged → qualificados → leads. Identifica o drop-off.</p>
              <div className="mt-4" style={{ width: "100%", height: 240 }}>
                <ResponsiveContainer width="99%" height="100%">
                  <BarChart data={data.funnel} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E5EAF2" />
                    <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
                    <YAxis type="category" dataKey="stage" tick={{ fontSize: 11 }} width={120} />
                    <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 10 }} />
                    <Bar dataKey="value" fill="#0069FE" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {data.funnel.length >= 2 && (
                <div className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
                  {data.funnel.slice(0, -1).map((f, i) => {
                    const next = data.funnel[i + 1];
                    const rate = f.value > 0 ? Math.round((next.value / f.value) * 100) : 0;
                    return (
                      <div key={i} className="text-center p-2 rounded-lg bg-[#F8FAFC]">
                        <div className="text-[#5B6B82] truncate" title={`${f.stage} → ${next.stage}`}>
                          → {next.stage.split(" ")[0]}
                        </div>
                        <div className="font-semibold text-[#0069FE]">{rate}%</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Top icebreakers */}
          <div className="card-surface p-5" data-testid="analytics-icebreakers">
            <div className="flex items-center gap-2 font-display font-semibold">
              <Target size={16} className="text-[#D97706]" /> Top frases de abertura
            </div>
            <p className="text-xs text-[#5B6B82] mt-0.5">Que primeira mensagem dos visitantes converte mais em leads.</p>
            {data.top_icebreakers.length === 0 ? (
              <div className="mt-4 text-sm text-[#5B6B82]">Sem dados de aberturas no período.</div>
            ) : (
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-[11px] uppercase tracking-wide text-[#5B6B82] border-b border-[#E5EAF2]">
                      <th className="py-2">#</th>
                      <th className="py-2">Frase de abertura</th>
                      <th className="py-2 text-right">Aberturas</th>
                      <th className="py-2 text-right">Leads</th>
                      <th className="py-2 text-right">Taxa</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_icebreakers.map((ib, i) => (
                      <tr key={i} data-testid={`icebreaker-row-${i}`}
                        className="border-b border-[#F1F5F9] last:border-0">
                        <td className="py-2.5 text-[#5B6B82]">{i + 1}</td>
                        <td className="py-2.5 max-w-md truncate" title={ib.opener}>{ib.opener}</td>
                        <td className="py-2.5 text-right font-medium">{ib.opens}</td>
                        <td className="py-2.5 text-right font-medium text-[#D97706]">{ib.leads}</td>
                        <td className="py-2.5 text-right">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                            ib.rate >= 30 ? "bg-[#DCFCE7] text-[#16A34A]" :
                            ib.rate >= 10 ? "bg-[#FEF3C7] text-[#D97706]" :
                                            "bg-[#F1F5F9] text-[#5B6B82]"}`}>
                            {ib.rate}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
};

export default Analytics;
