import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  Bot, Play, Trash2, Plus, Save, Sparkles, Database,
  KeyRound, CheckCircle2, AlertTriangle, MessageSquare, Send, X,
} from "lucide-react";

const defaultAgent = {
  name: "Novo Agente",
  avatar_url: "",
  welcome_message: "Olá! Como posso ajudar?",
  icebreakers: [],
  tone: "profissional", goal: "Ajudar clientes",
  system_prompt: "És um assistente útil. Responde em Português Europeu.",
  rules: "", api_provider: "emergent", api_key: "",
  model_provider: "auto", model_name: "gpt-5.1",
  tools: [
    { key: "create_lead", enabled: true }, { key: "create_ticket", enabled: true },
    { key: "send_email", enabled: false }, { key: "webhook", enabled: false },
  ],
  knowledge: "", data_source_ids: [], default_language: "pt",
  notify_email: "",
  channels: {
    webchat: { enabled: true },
    whatsapp: { enabled: false, access_token: "", phone_number_id: "" },
    instagram: { enabled: false, access_token: "", page_id: "" },
    telegram: { enabled: false, bot_token: "" },
  },
  active: true,
};

const Agentes = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [sources, setSources] = useState([]);
  const [connTest, setConnTest] = useState(null);
  const [showKey, setShowKey] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [chat, setChat] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const chatEndRef = useRef(null);
  const [params] = useSearchParams();

  const load = async () => {
    const [a, s] = await Promise.all([api.get("/agents"), api.get("/data-sources")]);
    setAgents(a.data); setSources(s.data);
    const pre = params.get("selected");
    if (!selected && a.data.length > 0) setSelected(a.data.find(x => x.id === pre) || a.data[0]);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const save = async () => {
    try {
      if (selected.id && agents.find(a => a.id === selected.id)) {
        const { data } = await api.put(`/agents/${selected.id}`, selected);
        setSelected(data); toast.success("Agente guardado.");
      } else {
        const { data } = await api.post("/agents", selected);
        setSelected(data); toast.success("Agente criado.");
      }
      load();
    } catch { toast.error("Falha a guardar"); }
  };
  const del = async () => {
    if (!selected?.id) return;
    await api.delete(`/agents/${selected.id}`); setSelected(null); load(); toast.success("Eliminado.");
  };

  const testConnection = async () => {
    setConnTest({ loading: true });
    try {
      const { data } = selected.id
        ? await api.post(`/agents/${selected.id}/test-connection`)
        : await api.post("/test-connection", { api_provider: selected.api_provider, api_key: selected.api_key, model_name: selected.model_name });
      setConnTest(data);
      data.ok ? toast.success("Ligação à IA OK.") : toast.error(data.error || "Falha");
    } catch (e) {
      const err = e?.response?.data?.detail || "Falha ao testar ligação";
      setConnTest({ ok: false, error: err });
      toast.error(err);
    }
  };

  // Chatbot test panel
  const sendChat = async (overrideText) => {
    const textToSend = (overrideText ?? chatInput).trim();
    if (!textToSend || !selected?.id) return;
    const userMsg = { role: "user", text: textToSend };
    setChat(c => [...c, userMsg]); if (!overrideText) setChatInput(""); setChatBusy(true);
    try {
      const { data } = await api.post(`/agents/${selected.id}/test`, { text: textToSend });
      setChat(c => [...c, { role: "ai", text: data.reply, cards: data.cards, meta: { intent: data.intent, language: data.language } }]);
    } catch (e) {
      const err = e?.response?.data?.detail || "API da IA não configurada ou inválida.";
      const needsConfig = err.includes("configurada") || err.includes("configure") || err.includes("inválida");
      setChat(c => [...c, { role: "ai", text: err, error: true, retryOf: textToSend, needsConfig }]);
    } finally {
      setChatBusy(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  };
  const openChat = () => { setChat([]); setShowChat(true); };

  const update = (k, v) => setSelected({ ...selected, [k]: v });
  const updateChannel = (kind, k, v) => {
    const channels = { ...(selected.channels || {}) };
    channels[kind] = { ...(channels[kind] || {}), [k]: v };
    update("channels", channels);
  };
  const addIce = () => update("icebreakers", [...(selected.icebreakers || []), ""]);
  const updIce = (i, v) => {
    const ices = [...(selected.icebreakers || [])];
    ices[i] = v; update("icebreakers", ices);
  };
  const delIce = (i) => update("icebreakers", (selected.icebreakers || []).filter((_, j) => j !== i));
  const toggleTool = (key) => update("tools", selected.tools.map(t => t.key === key ? { ...t, enabled: !t.enabled } : t));
  const toggleSource = (id) => {
    const has = (selected.data_source_ids || []).includes(id);
    update("data_source_ids", has ? selected.data_source_ids.filter(x => x !== id) : [...(selected.data_source_ids || []), id]);
  };

  const configured = selected && (selected.api_provider === "emergent" || (selected.api_key && selected.api_key.length > 10));

  return (
    <div className="h-full grid grid-cols-[300px_1fr] overflow-hidden">
      <div className="border-r border-[#E5EAF2] bg-white flex flex-col">
        <div className="p-4 border-b border-[#E5EAF2] flex items-center justify-between">
          <h1 className="font-display text-xl font-bold">Agentes IA</h1>
          <button data-testid="btn-new-agent" onClick={() => setSelected({ ...defaultAgent })} className="btn-ghost text-[12px] py-2">
            <Plus size={12} /> Novo
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {agents.map(a => (
            <button key={a.id} data-testid={`agent-item-${a.id}`} onClick={() => setSelected(a)}
              className={`w-full text-left p-3 rounded-lg mb-1 transition-colors ${selected?.id === a.id ? "bg-[#EAF2FF]" : "hover:bg-[#F7F9FC]"}`}>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#0069FE] text-white flex items-center justify-center"><Bot size={14} /></div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-sm truncate">{a.name}</div>
                  <div className="text-[11px] text-[#5B6B82] flex items-center gap-1">
                    {a.api_provider === "emergent" ? "Chave Universal" : (a.api_key ? a.api_provider : "⚠ Sem chave")}
                    · {a.active ? "Ativo" : "Inativo"}
                  </div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-y-auto p-8 bg-[#F7F9FC]">
        {!selected && <div className="text-sm text-[#5B6B82]">Selecione ou crie um agente.</div>}
        {selected && (
          <div className="max-w-3xl space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Agente</div>
                <input data-testid="agent-name" value={selected.name} onChange={(e) => update("name", e.target.value)}
                  className="font-display text-3xl font-bold bg-transparent border-b-2 border-transparent focus:border-[#0069FE] outline-none" />
              </div>
              <div className="flex gap-2">
                <button data-testid="btn-test-chatbot" onClick={openChat} disabled={!selected.id}
                  className="btn-ghost text-[13px]"><MessageSquare size={13} /> Testar chatbot</button>
                {selected.id && <button data-testid="btn-delete-agent" onClick={del} className="btn-ghost text-[13px] hover:text-[#DC2626]"><Trash2 size={13} /> Eliminar</button>}
                <button data-testid="btn-save-agent" onClick={save} className="btn-primary"><Save size={13} /> Guardar</button>
              </div>
            </div>

            {/* API CONFIG */}
            <div className="card-surface p-6" data-testid="api-config-panel">
              <div className="flex items-center gap-2 mb-1">
                <KeyRound size={16} className="text-[#0069FE]" />
                <div className="font-display font-semibold">Configuração da API de IA</div>
              </div>
              <p className="text-xs text-[#5B6B82] mb-4">Use a Chave Universal Emergent (incluída no seu plano) ou indique a sua própria chave.</p>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Provider</label>
                  <select data-testid="agent-api-provider" value={selected.api_provider} onChange={(e) => update("api_provider", e.target.value)} className="input-base">
                    <option value="emergent">Chave Universal Emergent</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic (Claude)</option>
                    <option value="gemini">Google (Gemini)</option>
                  </select>
                </div>
                <div>
                  <label className="label">Modelo</label>
                  <select data-testid="agent-model" value={selected.model_name} onChange={(e) => update("model_name", e.target.value)} className="input-base">
                    <option value="gpt-5.1">gpt-5.1 (OpenAI)</option>
                    <option value="gpt-5-mini">gpt-5-mini (OpenAI)</option>
                    <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
                    <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                    <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                  </select>
                </div>
              </div>

              {selected.api_provider !== "emergent" && (
                <div className="mt-4">
                  <label className="label">Chave API {selected.api_provider}</label>
                  <div className="flex gap-2">
                    <input data-testid="agent-api-key" type={showKey ? "text" : "password"} value={selected.api_key}
                      onChange={(e) => update("api_key", e.target.value)}
                      placeholder={selected.api_provider === "openai" ? "sk-..." : selected.api_provider === "anthropic" ? "sk-ant-..." : "AI..."}
                      className="input-base flex-1" />
                    <button data-testid="btn-toggle-key" onClick={() => setShowKey(!showKey)} className="btn-ghost text-xs">
                      {showKey ? "Ocultar" : "Mostrar"}
                    </button>
                  </div>
                  {!selected.api_key && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-[#D97706]">
                      <AlertTriangle size={12} /> Por favor configure a API da IA para ativar o agente.
                    </div>
                  )}
                </div>
              )}

              <div className="flex items-center gap-2 mt-4">
                <button data-testid="btn-test-connection" onClick={testConnection}
                  disabled={connTest?.loading}
                  className="btn-ghost text-[13px]">
                  {connTest?.loading ? "A testar…" : "Testar ligação"}
                </button>
                {connTest && !connTest.loading && (
                  <span className={`badge ${connTest.ok ? "badge-green" : "badge-red"}`}>
                    {connTest.ok ? <><CheckCircle2 size={11} /> Ligado · {connTest.provider}/{connTest.model}</>
                      : <><AlertTriangle size={11} /> {connTest.error || "Erro"}</>}
                  </span>
                )}
              </div>
            </div>

            {/* IDENTIDADE DO AGENTE */}
            <div className="card-surface p-6" data-testid="identity-panel">
              <div className="font-display font-semibold mb-1">Identidade do agente</div>
              <p className="text-xs text-[#5B6B82] mb-4">Aparece no widget de chat com avatar, nome e mensagem de boas-vindas.</p>
              <div className="flex gap-4 items-start">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-20 h-20 rounded-full bg-[#EAF2FF] text-[#0069FE] font-bold text-2xl flex items-center justify-center overflow-hidden border-2 border-[#C7DDFF]">
                    {selected.avatar_url ? (
                      <img src={selected.avatar_url} alt={selected.name}
                        onError={(e) => { e.target.style.display = "none"; }}
                        className="w-full h-full object-cover" />
                    ) : (
                      <span>{(selected.name || "A").slice(0, 2).toUpperCase()}</span>
                    )}
                  </div>
                  <div className="text-[10px] text-[#5B6B82] uppercase tracking-wider">Pré-visualização</div>
                </div>
                <div className="flex-1 space-y-3">
                  <div>
                    <label className="label">URL da foto do agente</label>
                    <input data-testid="agent-avatar" value={selected.avatar_url || ""}
                      onChange={(e) => update("avatar_url", e.target.value)}
                      placeholder="https://..." className="input-base" />
                  </div>
                  <div>
                    <label className="label">Mensagem de boas-vindas</label>
                    <input data-testid="agent-welcome" value={selected.welcome_message || ""}
                      onChange={(e) => update("welcome_message", e.target.value)}
                      placeholder="Olá! Como posso ajudar?" className="input-base" />
                  </div>
                </div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between">
                  <label className="label">Icebreakers (perguntas sugeridas)</label>
                  <button data-testid="btn-add-ice" onClick={addIce} type="button" className="btn-ghost text-[11px] py-1 px-2">+ Adicionar</button>
                </div>
                <div className="space-y-2">
                  {(selected.icebreakers || []).map((q, i) => (
                    <div key={i} className="flex gap-2" data-testid={`ice-${i}`}>
                      <input value={q} onChange={(e) => updIce(i, e.target.value)}
                        placeholder="Ex: Quais imóveis estão disponíveis?"
                        className="input-base flex-1 text-sm" />
                      <button type="button" onClick={() => delIce(i)} className="btn-ghost text-[#DC2626] px-3"><Trash2 size={12} /></button>
                    </div>
                  ))}
                  {(selected.icebreakers || []).length === 0 && (
                    <div className="text-xs text-[#5B6B82] italic">Nenhum icebreaker. Clique em "+ Adicionar".</div>
                  )}
                </div>
              </div>
            </div>

            {/* CANAIS DO AGENTE */}
            <div className="card-surface p-6" data-testid="channels-panel">
              <div className="font-display font-semibold mb-1">Canais do agente</div>
              <p className="text-xs text-[#5B6B82] mb-4">Cada agente tem a sua própria configuração de canais — não partilhados.</p>

              {[
                { k: "webchat", label: "Web Chat", fields: [] },
                { k: "whatsapp", label: "WhatsApp", fields: [
                  { f: "access_token", l: "API Token", type: "password" },
                  { f: "phone_number_id", l: "Phone Number ID", type: "text" },
                ]},
                { k: "instagram", label: "Instagram", fields: [
                  { f: "access_token", l: "Access Token", type: "password" },
                  { f: "page_id", l: "Page ID", type: "text" },
                ]},
                { k: "telegram", label: "Telegram", fields: [
                  { f: "bot_token", l: "Bot Token", type: "password" },
                ]},
              ].map(ch => {
                const cfg = (selected.channels && selected.channels[ch.k]) || {};
                return (
                  <div key={ch.k} data-testid={`channel-${ch.k}`} className="border border-[#E5EAF2] rounded-xl p-4 mb-3">
                    <label className="flex items-center gap-3">
                      <input type="checkbox" data-testid={`channel-toggle-${ch.k}`}
                        checked={!!cfg.enabled} onChange={(e) => updateChannel(ch.k, "enabled", e.target.checked)}
                        className="accent-[#0069FE]" />
                      <span className="font-semibold">{ch.label}</span>
                      <span className={`badge ${cfg.enabled ? "badge-green" : "badge-ghost"}`}>
                        {cfg.enabled ? "Ativo" : "Inativo"}
                      </span>
                    </label>
                    {cfg.enabled && ch.fields.length > 0 && (
                      <div className="grid grid-cols-2 gap-3 mt-3">
                        {ch.fields.map(f => (
                          <div key={f.f}>
                            <label className="label">{f.l}</label>
                            <input data-testid={`channel-${ch.k}-${f.f}`} type={f.type} value={cfg[f.f] || ""}
                              onChange={(e) => updateChannel(ch.k, f.f, e.target.value)}
                              className="input-base" />
                          </div>
                        ))}
                      </div>
                    )}
                    {ch.k === "webchat" && cfg.enabled && (
                      <div className="mt-3 text-xs text-[#5B6B82]">
                        O widget usa a identidade definida acima.
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="card-surface p-6">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="label">Tom</label>
                  <input data-testid="agent-tone" value={selected.tone} onChange={(e) => update("tone", e.target.value)} className="input-base" /></div>
                <div><label className="label">Objetivo</label>
                  <input data-testid="agent-goal" value={selected.goal} onChange={(e) => update("goal", e.target.value)} className="input-base" /></div>
                <div><label className="label">Idioma predefinido</label>
                  <select data-testid="agent-lang" value={selected.default_language || "pt"} onChange={(e) => update("default_language", e.target.value)} className="input-base">
                    <option value="pt">Português (pt-PT)</option><option value="en">English</option>
                    <option value="es">Español</option><option value="fr">Français</option>
                  </select></div>
                <div><label className="label">Estado</label>
                  <select value={selected.active ? "1" : "0"} onChange={(e) => update("active", e.target.value === "1")} className="input-base">
                    <option value="1">Ativo</option><option value="0">Inativo</option>
                  </select></div>
                <div className="col-span-2"><label className="label">Email para notificações de novos leads (opcional)</label>
                  <input data-testid="agent-notify-email" type="email" value={selected.notify_email || ""}
                    onChange={(e) => update("notify_email", e.target.value)}
                    placeholder="vendas@empresa.pt" className="input-base" />
                  <div className="text-[11px] text-[#5B6B82] mt-1">Requer integração SMTP ligada em Canais & CRM.</div>
                </div>
              </div>

              <label className="label mt-4">Prompt do sistema</label>
              <textarea data-testid="agent-system-prompt" rows={4} value={selected.system_prompt} onChange={(e) => update("system_prompt", e.target.value)} className="input-base" />

              <label className="label mt-4">Regras</label>
              <textarea data-testid="agent-rules" rows={3} value={selected.rules} onChange={(e) => update("rules", e.target.value)} className="input-base" />

              <label className="label mt-4">Conhecimento inline</label>
              <textarea data-testid="agent-knowledge" rows={3} value={selected.knowledge} onChange={(e) => update("knowledge", e.target.value)} className="input-base" />
            </div>

            <div className="card-surface p-6">
              <div className="flex items-center gap-2 mb-3">
                <Database size={16} className="text-[#0069FE]" />
                <div className="font-display font-semibold">Fontes de dados ligadas</div>
              </div>
              {sources.length === 0 && <div className="text-xs text-[#5B6B82]">Nenhuma fonte. Adicione em "Fontes de dados".</div>}
              <div className="space-y-2">
                {sources.map(s => {
                  const on = (selected.data_source_ids || []).includes(s.id);
                  return (
                    <label key={s.id} data-testid={`src-toggle-${s.id}`}
                      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer ${on ? "border-[#0069FE] bg-[#EAF2FF]" : "border-[#E5EAF2]"}`}>
                      <input type="checkbox" checked={on} onChange={() => toggleSource(s.id)} className="accent-[#0069FE]" />
                      <div className="flex-1">
                        <div className="text-sm font-semibold">{s.name}</div>
                        <div className="text-[11px] text-[#5B6B82]">{s.chunks} chunks · {s.items} items · {s.status}</div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="card-surface p-6">
              <div className="font-display font-semibold mb-2">Ferramentas</div>
              <div className="grid grid-cols-2 gap-2">
                {selected.tools?.map(t => (
                  <label key={t.key} data-testid={`tool-${t.key}`}
                    className={`flex items-center gap-2 border rounded-lg px-3 py-2.5 text-sm cursor-pointer ${t.enabled ? "border-[#0069FE] bg-[#EAF2FF]" : "border-[#E5EAF2] text-[#5B6B82]"}`}>
                    <input type="checkbox" checked={t.enabled} onChange={() => toggleTool(t.key)} className="accent-[#0069FE]" />
                    <span className="font-semibold capitalize">{t.key.replace("_", " ")}</span>
                  </label>
                ))}
              </div>
            </div>

            {!configured && selected.api_provider !== "emergent" && (
              <div className="p-4 rounded-lg bg-[#FFF4E1] border border-[#F4DCB0] text-sm text-[#92450C] flex items-center gap-2">
                <AlertTriangle size={14} /> Por favor configure a API da IA para ativar o agente.
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chatbot Test Panel (slide-over) */}
      {showChat && selected && (
        <div className="fixed inset-0 bg-black/30 z-50 flex items-end justify-end" data-testid="chatbot-test-panel">
          <div className="bg-white w-[460px] h-full flex flex-col border-l border-[#E5EAF2]">
            <div className="p-4 border-b border-[#E5EAF2] flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider flex items-center gap-1">
                  <Sparkles size={11} className="text-[#0069FE]" /> Teste em direto
                </div>
                <div className="font-display font-semibold">{selected.name}</div>
              </div>
              <button data-testid="btn-close-chat" onClick={() => setShowChat(false)} className="btn-ghost p-2"><X size={14} /></button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-[#F7F9FC]">
              {chat.length === 0 && (
                <div className="text-center text-xs text-[#5B6B82] mt-8">
                  Escreva uma mensagem como se fosse um cliente real.
                </div>
              )}
              {chat.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className="max-w-[82%]">
                    <div className={`rounded-2xl px-3 py-2 text-sm ${
                      m.role === "user" ? "bg-[#0069FE] text-white rounded-br-sm"
                      : m.error ? "bg-[#FEE2E2] border border-[#FCA5A5] text-[#991B1B] rounded-bl-sm"
                      : "bg-white border border-[#E5EAF2] rounded-bl-sm"
                    }`}>{m.text}</div>
                    {m.error && (
                      <div className="mt-1.5 flex gap-2">
                        <button data-testid="btn-retry-chat" onClick={() => sendChat(m.retryOf)}
                          className="text-[11px] font-semibold text-[#0069FE] hover:underline">↻ Tentar novamente</button>
                        {m.needsConfig && (
                          <button onClick={() => { setShowChat(false); setTimeout(() => document.querySelector("[data-testid='api-config-panel']")?.scrollIntoView({ behavior: "smooth" }), 100); }}
                            className="text-[11px] font-semibold text-[#0069FE] hover:underline">Configurar API →</button>
                        )}
                      </div>
                    )}
                    {m.cards?.length > 0 && (
                      <div className="mt-2 grid gap-2">
                        {m.cards.map((c, j) => (
                          <div key={j} className="card-surface overflow-hidden">
                            {c.image && <img src={c.image} alt={c.title} className="w-full h-24 object-cover" onError={(e) => e.target.style.display = "none"} />}
                            <div className="p-2">
                              <div className="font-semibold text-sm">{c.title}</div>
                              {c.price && <div className="text-[#0069FE] font-bold text-xs">{c.price}</div>}
                              {c.description && <div className="text-[11px] text-[#5B6B82] line-clamp-2">{c.description}</div>}
                              {c.link && <a href={c.link} target="_blank" rel="noreferrer" className="text-[#0069FE] text-[11px] font-semibold">Ver →</a>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    {m.meta?.intent && (
                      <div className="text-[10px] text-[#5B6B82] mt-1">
                        {m.meta.intent.intent} · {m.meta.language}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {chatBusy && <div className="text-xs text-[#5B6B82]">A IA está a escrever…</div>}
              <div ref={chatEndRef} />
            </div>

            <div className="p-3 border-t border-[#E5EAF2] flex gap-2">
              <input data-testid="chat-input" value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && sendChat()}
                placeholder="Escrever como cliente…" className="input-base flex-1" />
              <button data-testid="btn-send-chat" onClick={() => sendChat()} disabled={chatBusy} className="btn-primary"><Send size={12} /></button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Agentes;
