import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import {
  Inbox, Users, LifeBuoy, MessageSquare, TrendingUp,
  Globe, Phone, Send, Instagram, Activity, CheckCircle2, AlertTriangle, Circle,
} from "lucide-react";
import { toast } from "sonner";

const COLORS = ["#0069FE", "#16A34A", "#D97706", "#8B5CF6", "#EC4899", "#64748B"];

const CHANNEL_META = {
  webchat:   { label: "Web Chat",   Icon: Globe },
  whatsapp:  { label: "WhatsApp",   Icon: Phone },
  telegram:  { label: "Telegram",   Icon: Send },
  instagram: { label: "Instagram",  Icon: Instagram },
  messenger: { label: "Messenger",  Icon: MessageSquare },
};

const formatRelative = (iso) => {
  if (!iso) return "nunca";
  const dt = new Date(iso); const now = new Date();
  const diff = Math.max(0, (now - dt) / 1000);
  if (diff < 60) return "agora mesmo";
  if (diff < 3600) return `há ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `há ${Math.floor(diff / 3600)} h`;
  return `há ${Math.floor(diff / 86400)} dias`;
};

const ChannelHealth = () => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState({});

  const load = () => api.get("/agents/health").then(r => setData(r.data)).catch(() => setData([]));
  useEffect(() => { load(); }, []);

  const refresh = async (agentId, channel) => {
    const k = `${agentId}:${channel}`;
    setBusy(b => ({ ...b, [k]: true }));
    try {
      const r = await api.post(`/agents/${agentId}/test-channel/${channel}`);
      r.data?.ok ? toast.success(`${CHANNEL_META[channel]?.label}: ligado`) : toast.error(r.data?.error || "Falha");
      await load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Erro de ligação");
    } finally {
      setBusy(b => ({ ...b, [k]: false }));
    }
  };

  if (!data) return null;
  if (!data.length) {
    return (
      <div className="card-surface p-5" data-testid="channel-health">
        <div className="flex items-center gap-2 font-display font-semibold">
          <Activity size={16} className="text-[#0069FE]" /> Saúde dos canais
        </div>
        <div className="text-xs text-[#5B6B82] mt-2">Sem agentes ativos.</div>
      </div>
    );
  }

  return (
    <div className="card-surface p-5" data-testid="channel-health">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-2 font-display font-semibold">
            <Activity size={16} className="text-[#0069FE]" /> Saúde dos canais
          </div>
          <p className="text-xs text-[#5B6B82] mt-0.5">
            Estado de cada canal por agente. Clique em <span className="font-medium">Testar</span> para refrescar o handshake com o provider.
          </p>
        </div>
        <button data-testid="btn-health-refresh" onClick={load}
          className="btn-ghost text-[12px]">
          Recarregar
        </button>
      </div>

      <div className="mt-4 space-y-4">
        {data.map(agent => (
          <div key={agent.id} data-testid={`health-agent-${agent.id}`}
            className="border border-[#E5EAF2] rounded-xl p-4">
            <div className="flex items-center gap-3 mb-3">
              {agent.avatar_url
                ? <img src={agent.avatar_url} alt="" className="w-9 h-9 rounded-lg object-cover" />
                : <div className="w-9 h-9 rounded-lg bg-[#EAF2FF] text-[#0069FE] flex items-center justify-center font-semibold text-sm">
                    {(agent.name || "·").slice(0, 2).toUpperCase()}
                  </div>}
              <div className="font-semibold">{agent.name}</div>
              <div className="text-[11px] text-[#5B6B82] ml-auto">
                {agent.channels.filter(c => c.enabled && c.last_test_ok).length} / {agent.channels.filter(c => c.enabled).length} ligados
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
              {agent.channels.map(ch => {
                const meta = CHANNEL_META[ch.channel] || { label: ch.channel, Icon: Circle };
                const k = `${agent.id}:${ch.channel}`;
                const isBusy = !!busy[k];
                let StatusIcon = Circle, statusColor = "#9CA3AF", statusLabel = "Inativo";
                if (ch.enabled) {
                  if (!ch.configured) { StatusIcon = AlertTriangle; statusColor = "#D97706"; statusLabel = "Configuração incompleta"; }
                  else if (ch.last_test_ok === true) { StatusIcon = CheckCircle2; statusColor = "#16A34A"; statusLabel = "Ligado"; }
                  else if (ch.last_test_ok === false) { StatusIcon = AlertTriangle; statusColor = "#DC2626"; statusLabel = "Falha"; }
                  else { StatusIcon = Circle; statusColor = "#0069FE"; statusLabel = "Ativo · sem handshake"; }
                }
                return (
                  <div key={ch.channel} data-testid={`health-${agent.id}-${ch.channel}`}
                    className="border border-[#EEF1F7] rounded-lg p-3 flex items-start gap-3">
                    <div className="w-8 h-8 rounded-lg bg-[#F4F7FB] text-[#5B6B82] flex items-center justify-center flex-shrink-0">
                      <meta.Icon size={14} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-[13px] truncate">{meta.label}</span>
                        <StatusIcon size={13} style={{ color: statusColor }} />
                      </div>
                      <div className="text-[11px] mt-0.5" style={{ color: statusColor }}>{statusLabel}</div>
                      <div className="text-[10px] text-[#5B6B82] mt-1">
                        Último teste: {formatRelative(ch.last_test_at)}
                      </div>
                      {ch.last_test_ok && ch.last_test_info && (
                        <div className="text-[10px] text-[#16A34A] mt-0.5 truncate" title={ch.last_test_info}>
                          {ch.last_test_info}
                        </div>
                      )}
                      {ch.last_test_ok === false && ch.last_test_error && (
                        <div className="text-[10px] text-[#DC2626] mt-0.5 truncate" title={ch.last_test_error}>
                          {ch.last_test_error}
                        </div>
                      )}
                      {ch.enabled && ch.channel !== "webchat" && (
                        <button data-testid={`btn-health-test-${agent.id}-${ch.channel}`}
                          onClick={() => refresh(agent.id, ch.channel)}
                          disabled={isBusy}
                          className="text-[11px] text-[#0069FE] hover:underline mt-1.5 disabled:opacity-50">
                          {isBusy ? "A testar…" : "Testar agora"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const Painel = () => {
  const [stats, setStats] = useState(null);
  useEffect(() => { api.get("/dashboard/stats").then(r => setStats(r.data)); }, []);

  if (!stats) return <div className="p-8 text-sm text-[#5B6B82]">A carregar…</div>;

  const KPI = ({ icon: Icon, label, value, color }) => (
    <div className="card-surface p-4 md:p-5">
      <div className="flex items-center justify-between">
        <div className="w-9 h-9 md:w-10 md:h-10 rounded-lg flex items-center justify-center" style={{ background: color + "18", color: color }}>
          <Icon size={16} />
        </div>
        <TrendingUp size={14} className="text-[#16A34A]" />
      </div>
      <div className="text-2xl md:text-3xl font-display font-bold mt-3 md:mt-4 leading-tight">{value}</div>
      <div className="text-[10px] md:text-xs text-[#5B6B82] mt-1 uppercase tracking-wider font-medium">{label}</div>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-4 md:p-8 space-y-5 md:space-y-6" data-testid="painel-page">
      <div>
        <h1 className="font-display text-xl md:text-2xl font-bold">Painel</h1>
        <p className="text-xs md:text-sm text-[#5B6B82] mt-1">Visão geral do seu sistema operativo de IA.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4">
        <KPI icon={Inbox} label="Conversas" value={stats.conversations} color="#0069FE" />
        <KPI icon={MessageSquare} label="Em aberto" value={stats.open_conversations} color="#D97706" />
        <KPI icon={MessageSquare} label="Mensagens" value={stats.messages} color="#8B5CF6" />
        <KPI icon={Users} label="Leads" value={stats.leads} color="#16A34A" />
        <KPI icon={LifeBuoy} label="Tickets abertos" value={stats.open_tickets} color="#DC2626" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card-surface p-5">
          <div className="font-display font-semibold">Conversas por canal</div>
          <p className="text-xs text-[#5B6B82] mt-0.5">Distribuição ao longo dos canais ligados.</p>
          <div className="mt-4" style={{ width: "100%", height: 260 }}>
            {stats.by_channel && stats.by_channel.length > 0 ? (
              <ResponsiveContainer>
                <BarChart data={stats.by_channel}>
                  <XAxis dataKey="channel" stroke="#5B6B82" fontSize={12} />
                  <YAxis stroke="#5B6B82" fontSize={12} />
                  <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 10 }} />
                  <Bar dataKey="count" fill="#0069FE" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-sm text-[#5B6B82]">Sem conversas ainda.</div>
            )}
          </div>
        </div>

        <div className="card-surface p-5">
          <div className="font-display font-semibold">Leads por estado</div>
          <p className="text-xs text-[#5B6B82] mt-0.5">Funil de qualificação.</p>
          <div className="mt-4" style={{ width: "100%", height: 260, minHeight: 260 }}>
            {stats.by_stage && stats.by_stage.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={stats.by_stage} dataKey="count" nameKey="stage" innerRadius={55} outerRadius={90} paddingAngle={2}>
                    {stats.by_stage.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 10 }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-sm text-[#5B6B82]">Sem leads ainda.</div>
            )}
          </div>
        </div>
      </div>

      <ChannelHealth />
    </div>
  );
};

export default Painel;
