import React, { useEffect, useState, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { toast } from "sonner";
import AgentAutomation from "../components/AgentAutomation";
import {
  Bot, Trash2, Plus, Save, Sparkles, Database,
  KeyRound, CheckCircle2, AlertTriangle, MessageSquare, Send, X,
  Mail, Copy, Globe, Phone, Code2, Eye, Zap, Instagram, Palette, RotateCcw,
  Languages, Loader2,
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
    telegram: { enabled: false, bot_token: "" },
  },
  email: {
    enabled: false, host: "", port: 587, secure: "tls",
    username: "", password: "", from_email: "", notify_email: "",
  },
  theme: {
    primary: "#4591CE",
    primary_dark: "#2C6FA8",
    primary_soft: "#E8F1F9",
    primary_border: "#C7DDF0",
    bot: "#E4AC1E",
  },
  active: true,
};

const DEFAULT_THEME = {
  primary: "#4591CE",
  primary_dark: "#2C6FA8",
  primary_soft: "#E8F1F9",
  primary_border: "#C7DDF0",
  bot: "#E4AC1E",
};

const TABS = [
  { k: "identity", label: "Identidade", icon: Bot },
  { k: "ai", label: "IA & Instruções", icon: Sparkles },
  { k: "visual", label: "Visual & Cores", icon: Palette },
  { k: "channels", label: "Canais", icon: Zap },
  { k: "email", label: "Email", icon: Mail },
  { k: "install", label: "Instalação", icon: Code2 },
  { k: "data", label: "Fontes & Ferramentas", icon: Database },
  { k: "automation", label: "Automação", icon: Zap },
  { k: "preview", label: "Pré-visualizar", icon: Eye },
];

const Agentes = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [sources, setSources] = useState([]);
  const [connTest, setConnTest] = useState(null);
  const [showKey, setShowKey] = useState(false);
  const [tab, setTab] = useState("identity");
  const [channelTests, setChannelTests] = useState({}); // { whatsapp: {ok, info/error, loading} }
  const [emailTest, setEmailTest] = useState(null);
  const [emailTo, setEmailTo] = useState("");
  const [copied, setCopied] = useState("");
  const [params] = useSearchParams();

  // Live preview chat state
  const [chat, setChat] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const chatEndRef = useRef(null);

  const load = async () => {
    const [a, s] = await Promise.all([api.get("/agents"), api.get("/data-sources")]);
    setAgents(a.data); setSources(s.data);
    const pre = params.get("selected");
    if (!selected && a.data.length > 0) setSelected(a.data.find(x => x.id === pre) || a.data[0]);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  // Reset per-agent ephemeral state when switching
  useEffect(() => {
    setChannelTests({}); setEmailTest(null); setConnTest(null);
    setChat([]); setChatInput("");
  }, [selected?.id]);

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

  const testChannel = async (channelKey) => {
    if (!selected?.id) { toast.error("Guarde o agente antes de testar."); return; }
    setChannelTests(t => ({ ...t, [channelKey]: { loading: true } }));
    try {
      // Save current config first to ensure server has latest
      await api.put(`/agents/${selected.id}`, selected);
      const { data } = await api.post(`/agents/${selected.id}/test-channel/${channelKey}`);
      setChannelTests(t => ({ ...t, [channelKey]: data }));
      data.ok ? toast.success(`${channelKey}: ligado`) : toast.error(data.error || "Falha");
    } catch (e) {
      const err = e?.response?.data?.detail || "Falha ao testar";
      setChannelTests(t => ({ ...t, [channelKey]: { ok: false, error: err } }));
      toast.error(err);
    }
  };

  const testEmail = async () => {
    if (!selected?.id) { toast.error("Guarde o agente antes de testar."); return; }
    setEmailTest({ loading: true });
    try {
      await api.put(`/agents/${selected.id}`, selected);
      const { data } = await api.post(`/agents/${selected.id}/test-email`,
        { to: emailTo || selected.email?.notify_email || selected.email?.from_email });
      setEmailTest(data);
      data.ok ? toast.success("Email de teste enviado!") : toast.error(data.error || "Falha");
    } catch (e) {
      const err = e?.response?.data?.detail || "Falha a enviar";
      setEmailTest({ ok: false, error: err });
      toast.error(err);
    }
  };

  const sendPreview = async (overrideText) => {
    const textToSend = (overrideText ?? chatInput).trim();
    if (!textToSend || !selected?.id) return;
    setChat(c => [...c, { role: "user", text: textToSend }]);
    if (!overrideText) { setChatInput(""); }
    setChatBusy(true);
    try {
      const { data } = await api.post(`/agents/${selected.id}/test`, { text: textToSend });
      setChat(c => [...c, { role: "ai", text: data.reply }]);
      if (data.follow_up || (data.cards && data.cards.length > 0)) {
        // Small delay then append the follow-up (two-bubble style)
        await new Promise(r => setTimeout(r, 800));
        setChat(c => [...c, { role: "ai", text: data.follow_up || "", cards: data.cards, isFollowUp: true }]);
      }
    } catch (e) {
      const err = e?.response?.data?.detail || "API da IA não configurada ou inválida.";
      setChat(c => [...c, { role: "ai", text: err, error: true }]);
    } finally {
      setChatBusy(false);
      setTimeout(() => chatEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  };

  const update = (k, v) => setSelected({ ...selected, [k]: v });
  const updateChannel = (kind, k, v) => {
    const channels = { ...(selected.channels || {}) };
    channels[kind] = { ...(channels[kind] || {}), [k]: v };
    update("channels", channels);
  };
  const updateEmail = (k, v) => update("email", { ...(selected.email || {}), [k]: v });
  const updateTheme = (k, v) => update("theme", { ...(selected.theme || {}), [k]: v });
  const resetTheme = () => update("theme", { ...DEFAULT_THEME });

  const resetDefaults = async () => {
    if (!selected?.id) { toast.error("Guarde o agente antes de repor."); return; }
    if (!window.confirm("Repor o prompt, icebreakers, mensagem de boas-vindas e tema para os valores predefinidos? As tuas customizações deste agente serão perdidas.")) return;
    try {
      const { data } = await api.post(`/agents/${selected.id}/reset-defaults`);
      setSelected(data);
      toast.success("Predefinições repostas.");
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falha a repor predefinições");
    }
  };

  // ===== Duplicate + Translate =====
  const [translateOpen, setTranslateOpen] = useState(false);
  const [translateTarget, setTranslateTarget] = useState("en");
  const [translateBusy, setTranslateBusy] = useState(false);
  const [translateElapsed, setTranslateElapsed] = useState(0);  // seconds elapsed
  const [duplicateBusy, setDuplicateBusy] = useState(false);

  // Timer for progress bar while translation is running
  useEffect(() => {
    if (!translateBusy) { setTranslateElapsed(0); return; }
    const start = Date.now();
    const iv = setInterval(() => {
      setTranslateElapsed(Math.floor((Date.now() - start) / 1000));
    }, 500);
    return () => clearInterval(iv);
  }, [translateBusy]);

  const duplicatePlain = async () => {
    if (!selected?.id) { toast.error("Guarde o agente antes de duplicar."); return; }
    setDuplicateBusy(true);
    try {
      const { data } = await api.post(`/agents/${selected.id}/duplicate`);
      toast.success(`Agente duplicado: ${data.name}`);
      await load();
      setSelected(data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falha a duplicar");
    } finally {
      setDuplicateBusy(false);
    }
  };

  const duplicateTranslate = async () => {
    if (!selected?.id) { toast.error("Guarde o agente antes de traduzir."); return; }
    if (!translateTarget) { toast.error("Escolha o idioma de destino."); return; }
    setTranslateBusy(true);
    try {
      // Tradução pode demorar 20-90s (depende do tamanho do prompt do agente).
      // Aumentamos o timeout do axios apenas para esta chamada — 180s.
      const { data } = await api.post(
        `/agents/${selected.id}/duplicate-translate`,
        { target_language: translateTarget },
        { timeout: 180000 },
      );
      toast.success(`Agente criado: ${data.name}`, { duration: 5000 });
      setTranslateOpen(false);
      await load();
      setSelected(data);
    } catch (e) {
      // Mensagem clara para timeout
      let msg = e?.response?.data?.detail || e?.message || "Falha na tradução";
      if (e?.code === "ECONNABORTED" || /timeout/i.test(msg)) {
        msg = "A tradução demorou mais do que o esperado. A tarefa pode ter sido concluída — verifica a lista de agentes daqui a uns segundos. Se não apareceu, tenta de novo.";
      }
      toast.error(msg, { duration: 8000 });
    } finally {
      setTranslateBusy(false);
    }
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

  const copy = (k, text) => {
    navigator.clipboard.writeText(text);
    setCopied(k); toast.success("Copiado");
    setTimeout(() => setCopied(""), 1500);
  };

  // Use window.location.origin so the snippets always reflect the domain where the user
  // is currently authenticated (e.g. consenso-agents.com) — not the build-time
  // REACT_APP_BACKEND_URL which can be the platform-internal host.
  const backendUrl = (typeof window !== "undefined" && window.location?.origin)
    ? window.location.origin
    : process.env.REACT_APP_BACKEND_URL;
  const scriptSnippet = selected?.id
    ? `<!-- Consenso+ Chatbot -->\n<script src="${backendUrl}/api/widget.js"\n  data-tenant-id="${selected.tenant_id}"\n  data-agent-id="${selected.id}"\n  defer></script>`
    : "";
  const shortcode = selected?.id ? `[consenso_chat agent_id="${selected.id}"]` : "";
  const phpSnippet = selected?.id
    ? `// Cole em functions.php do seu tema WordPress (se não usa o plugin oficial):\nadd_shortcode('consenso_chat', function($atts) {\n  $a = shortcode_atts(['agent_id' => '${selected.id}', 'tenant_id' => '${selected.tenant_id}'], $atts);\n  return '<script src="${backendUrl}/api/widget.js" data-tenant-id="' . esc_attr($a['tenant_id']) . '" data-agent-id="' . esc_attr($a['agent_id']) . '" defer></script>';\n});`
    : "";
  const iframeSrc = selected?.id
    ? `${backendUrl}/api/widget/${selected.tenant_id}?api=${encodeURIComponent(backendUrl + "/api")}&tenant=${selected.tenant_id}&agent=${selected.id}`
    : "";
  const iframeSnippet = selected?.id
    ? `<!-- Consenso+ Chatbot · iFrame -->\n<iframe\n  src="${iframeSrc}"\n  title="${(selected.name || "Chat").replace(/"/g, "&quot;")}"\n  width="100%"\n  height="640"\n  style="border:0;border-radius:12px;max-width:480px;box-shadow:0 4px 24px rgba(0,0,0,.08)"\n  allow="clipboard-write"\n  loading="lazy">\n</iframe>`
    : "";
  const testPageUrl = selected?.id
    ? `${backendUrl}/api/widget-test/${selected.tenant_id}/${selected.id}`
    : "";

  const configured = selected && (selected.api_provider === "emergent" || (selected.api_key && selected.api_key.length > 10));

  return (
    <div className="h-full grid grid-cols-[300px_1fr] overflow-hidden">
      {/* LEFT: agent list */}
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
                <div className="w-8 h-8 rounded-lg bg-[#0069FE] text-white flex items-center justify-center overflow-hidden">
                  {a.avatar_url
                    ? <img src={a.avatar_url} alt="" className="w-full h-full object-cover" onError={(e) => { e.target.style.display = "none"; }} />
                    : <Bot size={14} />}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-sm truncate">{a.name}</div>
                  <div className="text-[11px] text-[#5B6B82] flex items-center gap-1 truncate">
                    {a.api_provider === "emergent" ? "Chave Universal" : (a.api_key ? a.api_provider : "⚠ Sem chave")}
                    · {a.active ? "Ativo" : "Inativo"}
                  </div>
                </div>
              </div>
            </button>
          ))}
          {agents.length === 0 && (
            <div className="text-xs text-[#5B6B82] p-4 text-center">Nenhum agente. Clique em "Novo".</div>
          )}
        </div>
      </div>

      {/* RIGHT: editor */}
      <div className="overflow-y-auto bg-[#F7F9FC]">
        {!selected && <div className="p-8 text-sm text-[#5B6B82]">Selecione ou crie um agente.</div>}
        {selected && (
          <div className="max-w-5xl mx-auto p-8 pb-24">
            {/* HEADER */}
            <div className="flex items-center justify-between mb-6">
              <div>
                <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Agente</div>
                <input data-testid="agent-name" value={selected.name} onChange={(e) => update("name", e.target.value)}
                  className="font-display text-3xl font-bold bg-transparent border-b-2 border-transparent focus:border-[#0069FE] outline-none" />
              </div>
              <div className="flex gap-2 flex-wrap">
                {selected.id && (
                  <button data-testid="btn-duplicate-agent" onClick={duplicatePlain} disabled={duplicateBusy}
                    className="btn-ghost text-[13px]" title="Duplicar este agente (mesmo conteúdo, novo ID)">
                    {duplicateBusy ? <Loader2 size={13} className="animate-spin" /> : <Copy size={13} />}
                    Duplicar
                  </button>
                )}
                {selected.id && (
                  <button data-testid="btn-translate-agent" onClick={() => setTranslateOpen(true)}
                    className="btn-ghost text-[13px] text-[#0069FE] border border-[#C7DDF0] hover:bg-[#E8F1F9]"
                    title="Duplica e traduz automaticamente todos os textos para outro idioma">
                    <Languages size={13} /> Duplicar e Traduzir
                  </button>
                )}
                {selected.id && <button data-testid="btn-delete-agent" onClick={del} className="btn-ghost text-[13px] hover:text-[#DC2626]"><Trash2 size={13} /> Eliminar</button>}
                <button data-testid="btn-save-agent" onClick={save} className="btn-primary"><Save size={13} /> Guardar</button>
              </div>
            </div>

            {/* TABS */}
            <div className="flex gap-1 mb-6 border-b border-[#E5EAF2] overflow-x-auto" data-testid="agent-tabs">
              {TABS.map(t => {
                const Icon = t.icon; const active = tab === t.k;
                return (
                  <button key={t.k} data-testid={`tab-${t.k}`} onClick={() => setTab(t.k)}
                    className={`flex items-center gap-2 px-4 py-2.5 text-sm font-semibold border-b-2 transition-colors whitespace-nowrap ${
                      active ? "border-[#0069FE] text-[#0069FE]" : "border-transparent text-[#5B6B82] hover:text-[#0B1324]"
                    }`}>
                    <Icon size={14} />{t.label}
                  </button>
                );
              })}
            </div>

            {/* ======= IDENTITY ======= */}
            {tab === "identity" && (
              <div className="card-surface p-6 space-y-4" data-testid="identity-panel">
                <div className="font-display font-semibold mb-1">Identidade do agente</div>
                <p className="text-xs text-[#5B6B82]">Aparece no widget com avatar, nome e mensagem de boas-vindas.</p>
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
                      <label className="label">Foto do agente</label>
                      <div className="flex gap-2 items-center">
                        <label className="btn-ghost text-[13px] cursor-pointer" data-testid="btn-upload-avatar">
                          <input type="file" accept="image/png,image/jpeg,image/webp"
                            className="hidden"
                            onChange={async (e) => {
                              const f = e.target.files?.[0]; if (!f) return;
                              if (f.size > 2 * 1024 * 1024) { toast.error("Imagem demasiado grande (máx 2MB)"); return; }
                              if (!selected.id) {
                                // Agent not saved yet — store as local data URL
                                const reader = new FileReader();
                                reader.onload = (ev) => update("avatar_url", ev.target.result);
                                reader.readAsDataURL(f);
                                toast.success("Imagem carregada. Guarde o agente para a persistir.");
                                return;
                              }
                              const fd = new FormData();
                              fd.append("file", f);
                              try {
                                const { data } = await api.post(`/agents/${selected.id}/avatar`, fd,
                                  { headers: { "Content-Type": "multipart/form-data" } });
                                update("avatar_url", data.avatar_url);
                                toast.success("Foto atualizada.");
                              } catch { toast.error("Falha no upload"); }
                              e.target.value = "";
                            }}
                          />
                          📁 Carregar imagem
                        </label>
                        {selected.avatar_url && (
                          <button type="button" onClick={() => update("avatar_url", "")}
                            data-testid="btn-remove-avatar"
                            className="btn-ghost text-[12px] text-[#DC2626]">Remover</button>
                        )}
                      </div>
                      <details className="mt-2">
                        <summary className="text-[11px] text-[#5B6B82] cursor-pointer hover:text-[#0069FE]">
                          Ou usar URL externo
                        </summary>
                        <input data-testid="agent-avatar" value={selected.avatar_url?.startsWith("data:") ? "" : (selected.avatar_url || "")}
                          onChange={(e) => update("avatar_url", e.target.value)}
                          placeholder="https://..." className="input-base mt-2 text-sm" />
                      </details>
                    </div>
                    <div>
                      <label className="label">Mensagem de boas-vindas</label>
                      <input data-testid="agent-welcome" value={selected.welcome_message || ""}
                        onChange={(e) => update("welcome_message", e.target.value)}
                        placeholder="Olá! Como posso ajudar?" className="input-base" />
                    </div>
                  </div>
                </div>

                <div>
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

                <div className="grid grid-cols-2 gap-4 pt-4 border-t border-[#E5EAF2]">
                  <div><label className="label">Idioma predefinido</label>
                    <select data-testid="agent-lang" value={selected.default_language || "pt"} onChange={(e) => update("default_language", e.target.value)} className="input-base">
                      <option value="pt">Português (pt-PT)</option>
                      <option value="en">English</option>
                      <option value="es">Español</option>
                      <option value="fr">Français</option>
                      <option value="de">Deutsch</option>
                      <option value="ca">Català</option>
                    </select>
                    <p className="text-[11px] text-[#5B6B82] mt-1">
                      Define o idioma da UI do widget (placeholder, modal de visita, botões). A IA detecta e responde automaticamente no idioma do utilizador.
                    </p>
                  </div>
                  <div><label className="label">Estado</label>
                    <select data-testid="agent-active" value={selected.active ? "1" : "0"} onChange={(e) => update("active", e.target.value === "1")} className="input-base">
                      <option value="1">Ativo</option><option value="0">Inativo</option>
                    </select></div>
                </div>
              </div>
            )}

            {/* ======= AI ======= */}
            {tab === "ai" && (
              <div className="space-y-5">
                <div className="card-surface p-6" data-testid="api-config-panel">
                  <div className="flex items-center gap-2 mb-1">
                    <KeyRound size={16} className="text-[#0069FE]" />
                    <div className="font-display font-semibold">Configuração da API de IA</div>
                  </div>
                  <p className="text-xs text-[#5B6B82] mb-4">Use a Chave Universal Emergent (incluída) ou indique a sua própria chave.</p>

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
                      disabled={connTest?.loading} className="btn-ghost text-[13px]">
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

                <div className="card-surface p-6">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="font-display font-semibold">Comportamento do agente</div>
                      <p className="text-xs text-[#5B6B82] mt-0.5">
                        Edita tom, objetivo, prompt do sistema, regras e conhecimento inline. As <b>regras globais Consenso Plus</b> (tom PT-PT, 1 mensagem por turno, sem repetir perguntas) são aplicadas automaticamente <i>por cima</i> destas.
                      </p>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div><label className="label">Tom</label>
                      <input data-testid="agent-tone" value={selected.tone} onChange={(e) => update("tone", e.target.value)} className="input-base" /></div>
                    <div><label className="label">Objetivo</label>
                      <input data-testid="agent-goal" value={selected.goal} onChange={(e) => update("goal", e.target.value)} className="input-base" /></div>
                  </div>
                  <label className="label mt-4">Prompt do sistema <span className="text-[10px] font-normal text-[#5B6B82]">(modo avançado — edita com cuidado)</span></label>
                  <textarea data-testid="agent-system-prompt" rows={10} value={selected.system_prompt} onChange={(e) => update("system_prompt", e.target.value)} className="input-base font-mono text-xs" />
                  <label className="label mt-4">Regras adicionais</label>
                  <textarea data-testid="agent-rules" rows={4} value={selected.rules} onChange={(e) => update("rules", e.target.value)} className="input-base text-sm" />
                  <label className="label mt-4">Conhecimento inline</label>
                  <textarea data-testid="agent-knowledge" rows={4} value={selected.knowledge} onChange={(e) => update("knowledge", e.target.value)} className="input-base text-sm" />
                </div>

                {!configured && selected.api_provider !== "emergent" && (
                  <div className="p-4 rounded-lg bg-[#FFF4E1] border border-[#F4DCB0] text-sm text-[#92450C] flex items-center gap-2">
                    <AlertTriangle size={14} /> Por favor configure a API da IA para ativar o agente.
                  </div>
                )}

                {selected.id && (
                  <div className="card-surface p-6 border-dashed border-2 border-[#FCD9B6] bg-[#FFF9F0]">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2 font-display font-semibold text-[#92450C]">
                          <RotateCcw size={14} /> Repor predefinições do seed
                        </div>
                        <p className="text-xs text-[#92450C]/80 mt-1">
                          Repõe o <b>prompt</b>, <b>regras</b>, <b>icebreakers</b>, <b>mensagem de boas-vindas</b> e <b>tema</b> deste agente para a versão oficial da Consenso Plus. As tuas customizações deste agente serão substituídas.
                        </p>
                        {selected.is_customized && (
                          <div className="mt-2 inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-[#FEF3C7] text-[#92400E] border border-[#FCD34D]">
                            <Sparkles size={10} /> Modo Customizado · bootstrap não substitui
                          </div>
                        )}
                      </div>
                      <button data-testid="btn-reset-defaults" onClick={resetDefaults}
                        className="btn-ghost text-[12px] whitespace-nowrap border border-[#FCD9B6] text-[#92450C] hover:bg-[#FCD9B6]/30">
                        <RotateCcw size={11} /> Repor predefinições
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* ======= VISUAL & CORES ======= */}
            {tab === "visual" && (
              <div className="space-y-5" data-testid="visual-panel">
                <div className="card-surface p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <div className="flex items-center gap-2 font-display font-semibold">
                        <Palette size={16} className="text-[#0069FE]" />
                        Cores do widget
                      </div>
                      <p className="text-xs text-[#5B6B82] mt-1">
                        Personaliza as cores do chat para combinar com a tua marca. O widget no website do cliente reflete estas cores automaticamente.
                      </p>
                    </div>
                    <button type="button" data-testid="btn-reset-theme" onClick={resetTheme}
                      className="btn-ghost text-[12px]"><RotateCcw size={11} /> Repor cores</button>
                  </div>

                  <div className="grid grid-cols-2 gap-5">
                    {[
                      { k: "primary", label: "Cor principal (header + botão enviar)", desc: "Usada no header do chat e no botão de envio." },
                      { k: "primary_dark", label: "Cor principal escura", desc: "Usada como gradiente no header e em hover states." },
                      { k: "primary_soft", label: "Cor suave (fundos)", desc: "Fundos de avatar, focus ring e superfícies suaves." },
                      { k: "primary_border", label: "Cor da borda dos icebreakers", desc: "Borda dos botões de sugestão (icebreakers)." },
                      { k: "bot", label: "Cor de acento (bot · preços · destaques)", desc: "Realce de preços, badges e elementos do bot." },
                    ].map(({ k, label, desc }) => {
                      const value = selected.theme?.[k] || DEFAULT_THEME[k];
                      return (
                        <div key={k} data-testid={`theme-row-${k}`} className="border border-[#E5EAF2] rounded-xl p-3">
                          <label className="label">{label}</label>
                          <div className="flex items-center gap-2 mt-1">
                            <input type="color" data-testid={`theme-color-${k}`}
                              value={value}
                              onChange={(e) => updateTheme(k, e.target.value)}
                              className="w-12 h-10 rounded-lg border border-[#E5EAF2] cursor-pointer bg-white p-0.5" />
                            <input type="text" data-testid={`theme-hex-${k}`}
                              value={value}
                              onChange={(e) => updateTheme(k, e.target.value)}
                              placeholder="#4591CE"
                              className="input-base flex-1 font-mono text-sm uppercase" />
                          </div>
                          <p className="text-[11px] text-[#5B6B82] mt-1">{desc}</p>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Live preview of theme */}
                <div className="card-surface p-0 overflow-hidden" data-testid="theme-preview">
                  <div className="p-4 flex items-center gap-3 text-white"
                    style={{ background: `linear-gradient(135deg, ${selected.theme?.primary || DEFAULT_THEME.primary} 0%, ${selected.theme?.primary_dark || DEFAULT_THEME.primary_dark} 100%)` }}>
                    <div className="w-11 h-11 rounded-full bg-white/20 border-2 border-white/30 flex items-center justify-center overflow-hidden">
                      {selected.avatar_url
                        ? <img src={selected.avatar_url} alt={selected.name} className="w-full h-full object-cover" onError={(e) => { e.target.style.display = "none"; }} />
                        : <span className="font-bold">{(selected.name || "A").slice(0, 2).toUpperCase()}</span>}
                    </div>
                    <div>
                      <div className="font-semibold">{selected.name || "Agente"}</div>
                      <div className="text-[11px] opacity-90">Pré-visualização ao vivo</div>
                    </div>
                  </div>
                  <div className="p-4 space-y-3" style={{ background: "#F7F9FC" }}>
                    {/* bot bubble */}
                    <div className="flex gap-2 items-start">
                      <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
                        style={{ background: selected.theme?.primary_soft || DEFAULT_THEME.primary_soft, color: selected.theme?.primary || DEFAULT_THEME.primary }}>
                        <Bot size={12} />
                      </div>
                      <div className="max-w-[78%] rounded-2xl rounded-bl-sm px-3 py-2 bg-white border text-sm"
                        style={{ borderColor: selected.theme?.primary_border || DEFAULT_THEME.primary_border }}>
                        {selected.welcome_message || "Olá! Como posso ajudar?"}
                      </div>
                    </div>
                    {/* icebreakers */}
                    {(selected.icebreakers || []).filter(Boolean).slice(0, 3).length > 0 && (
                      <div className="flex flex-wrap gap-2 pl-9">
                        {(selected.icebreakers || []).filter(Boolean).slice(0, 3).map((q, i) => (
                          <span key={i} className="text-xs px-3 py-1.5 rounded-full bg-white border"
                            style={{
                              borderColor: selected.theme?.primary_border || DEFAULT_THEME.primary_border,
                              color: selected.theme?.primary || DEFAULT_THEME.primary,
                            }}>
                            {q}
                          </span>
                        ))}
                      </div>
                    )}
                    {/* example bot with price highlight */}
                    <div className="flex gap-2 items-start">
                      <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center"
                        style={{ background: selected.theme?.primary_soft || DEFAULT_THEME.primary_soft, color: selected.theme?.primary || DEFAULT_THEME.primary }}>
                        <Bot size={12} />
                      </div>
                      <div className="max-w-[78%] rounded-2xl rounded-bl-sm px-3 py-2 bg-white border text-sm space-y-1"
                        style={{ borderColor: selected.theme?.primary_border || DEFAULT_THEME.primary_border }}>
                        <div>O plano <b style={{ color: selected.theme?.bot || DEFAULT_THEME.bot }}>PRO</b> tem mensagens ilimitadas e CRM.</div>
                        <div className="text-xs font-bold" style={{ color: selected.theme?.bot || DEFAULT_THEME.bot }}>€74,90/mês</div>
                      </div>
                    </div>
                    {/* user bubble */}
                    <div className="flex justify-end">
                      <div className="max-w-[78%] rounded-2xl rounded-br-sm px-3 py-2 text-white text-sm"
                        style={{ background: selected.theme?.primary || DEFAULT_THEME.primary }}>
                        Quero saber mais sobre o plano PRO.
                      </div>
                    </div>
                  </div>
                  <div className="p-3 border-t flex gap-2 bg-white"
                    style={{ borderColor: selected.theme?.primary_border || DEFAULT_THEME.primary_border }}>
                    <input disabled placeholder="Escrever mensagem…"
                      className="input-base flex-1 text-sm bg-[#F7F9FC]" />
                    <button type="button" disabled
                      className="px-3 py-2 rounded-lg text-white text-sm"
                      style={{ background: selected.theme?.primary || DEFAULT_THEME.primary }}>
                      <Send size={12} />
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ======= CHANNELS ======= */}
            {tab === "channels" && (
              <div className="card-surface p-6 space-y-4" data-testid="channels-panel">
                <div>
                  <div className="font-display font-semibold">Canais do agente</div>
                  <p className="text-xs text-[#5B6B82]">Cada agente tem a sua própria configuração. Sem configuração, o canal não ativa.</p>
                </div>

                {[
                  { k: "webchat", label: "Web Chat", Icon: Globe, fields: [] },
                  { k: "whatsapp", label: "WhatsApp", Icon: Phone, fields: [
                    { f: "access_token", l: "API Token (WhatsApp Cloud)", type: "password", ph: "EAA..." },
                    { f: "phone_number_id", l: "Phone Number ID", type: "text", ph: "123456789012345" },
                    { f: "verify_token", l: "Verify Token (webhook)", type: "text", ph: "escolha-um-segredo" },
                  ]},
                  { k: "telegram", label: "Telegram", Icon: Send, fields: [
                    { f: "bot_token", l: "Bot Token", type: "password", ph: "1234:ABC-DEF_abc..." },
                  ]},
                  { k: "instagram", label: "Instagram Direct", Icon: Instagram, fields: [
                    { f: "page_access_token", l: "Page Access Token (Meta)", type: "password", ph: "EAA..." },
                    { f: "ig_user_id", l: "Instagram Business Account ID", type: "text", ph: "17841400000000000" },
                    { f: "verify_token", l: "Verify Token (webhook)", type: "text", ph: "escolha-um-segredo" },
                  ]},
                  { k: "messenger", label: "Facebook Messenger", Icon: MessageSquare, fields: [
                    { f: "page_access_token", l: "Page Access Token (Meta)", type: "password", ph: "EAA..." },
                    { f: "page_id", l: "Page ID", type: "text", ph: "1234567890" },
                    { f: "verify_token", l: "Verify Token (webhook)", type: "text", ph: "escolha-um-segredo" },
                  ]},
                ].map(ch => {
                  const cfg = (selected.channels && selected.channels[ch.k]) || {};
                  const test = channelTests[ch.k];
                  const webhookUrl = ch.k === "whatsapp"
                    ? `${backendUrl}/api/webhooks/whatsapp/${selected.tenant_id || ""}/${selected.id || "<agent_id>"}`
                    : ch.k === "telegram"
                      ? `${backendUrl}/api/webhooks/telegram/${selected.tenant_id || ""}/${selected.id || "<agent_id>"}`
                      : ch.k === "messenger"
                        ? `${backendUrl}/api/webhooks/messenger/${selected.tenant_id || ""}/${selected.id || "<agent_id>"}`
                        : ch.k === "instagram"
                          ? `${backendUrl}/api/webhooks/instagram/${selected.tenant_id || ""}/${selected.id || "<agent_id>"}`
                          : null;
                  return (
                    <div key={ch.k} data-testid={`channel-${ch.k}`} className="border border-[#E5EAF2] rounded-xl p-4">
                      <div className="flex items-center justify-between">
                        <label className="flex items-center gap-3">
                          <input type="checkbox" data-testid={`channel-toggle-${ch.k}`}
                            checked={!!cfg.enabled} onChange={(e) => updateChannel(ch.k, "enabled", e.target.checked)}
                            className="accent-[#0069FE]" />
                          <div className="w-9 h-9 rounded-lg bg-[#EAF2FF] text-[#0069FE] flex items-center justify-center">
                            <ch.Icon size={15} />
                          </div>
                          <span className="font-semibold">{ch.label}</span>
                          <span className={`badge ${cfg.enabled ? (test?.ok ? "badge-green" : "badge-blue") : "badge-ghost"}`}>
                            {!cfg.enabled ? "Inativo"
                              : test?.loading ? "A testar…"
                              : test?.ok ? "Ligado"
                              : test?.error ? "Erro"
                              : "Ativo"}
                          </span>
                        </label>
                        {cfg.enabled && ch.k !== "webchat" && (
                          <button data-testid={`btn-test-${ch.k}`} onClick={() => testChannel(ch.k)}
                            disabled={test?.loading}
                            className="btn-ghost text-[12px]">
                            <CheckCircle2 size={11} /> {test?.loading ? "A testar…" : "Testar ligação"}
                          </button>
                        )}
                      </div>

                      {cfg.enabled && ch.fields.length > 0 && (
                        <div className="grid grid-cols-2 gap-3 mt-4">
                          {ch.fields.map(f => (
                            <div key={f.f}>
                              <label className="label">{f.l}</label>
                              <input data-testid={`channel-${ch.k}-${f.f}`} type={f.type} value={cfg[f.f] || ""}
                                onChange={(e) => updateChannel(ch.k, f.f, e.target.value)}
                                placeholder={f.ph || ""}
                                className="input-base" />
                            </div>
                          ))}
                        </div>
                      )}

                      {cfg.enabled && webhookUrl && (
                        <div className="mt-3 bg-[#EAF2FF] border border-[#C7DDFF] rounded-lg p-3 text-xs">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-[#0069FE]">Webhook URL</span>
                            <button data-testid={`btn-copy-webhook-${ch.k}`}
                              onClick={() => copy(`wh-${ch.k}`, webhookUrl)}
                              className="btn-ghost text-[10px] py-1 px-2">
                              <Copy size={9} /> {copied === `wh-${ch.k}` ? "Copiado" : "Copiar"}
                            </button>
                          </div>
                          <code className="block break-all text-[11px]">{webhookUrl}</code>
                          <div className="text-[#5B6B82] mt-1">
                            {ch.k === "whatsapp" && "Configure este URL no Meta Business Manager."}
                            {ch.k === "telegram" && "Chame setWebhook na Bot API com este URL."}
                            {ch.k === "messenger" && "Adicione este URL nas Webhook Subscriptions da App Meta (objeto: page · campos: messages)."}
                            {ch.k === "instagram" && "Adicione este URL nas Webhook Subscriptions da App Meta (objeto: instagram · campos: messages)."}
                          </div>
                        </div>
                      )}

                      {test && !test.loading && (
                        <div className={`mt-2 text-xs flex items-center gap-2 ${test.ok ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                          {test.ok ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                          {test.ok ? (test.info || "Ligação válida") : test.error}
                        </div>
                      )}

                      {ch.k === "webchat" && cfg.enabled && (
                        <div className="mt-3 text-xs text-[#5B6B82]">
                          O widget usa a identidade do agente. Veja o separador <b>Instalação</b> para o código.
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ======= EMAIL ======= */}
            {tab === "email" && (
              <div className="card-surface p-6 space-y-4" data-testid="email-panel">
                <div className="flex items-center gap-2">
                  <Mail size={16} className="text-[#0069FE]" />
                  <div className="font-display font-semibold">Email do agente (SMTP)</div>
                </div>
                <p className="text-xs text-[#5B6B82]">Configurado por agente. Usado para enviar automaticamente notificações de novos leads.</p>

                <label className="flex items-center gap-2">
                  <input type="checkbox" data-testid="email-enabled"
                    checked={!!selected.email?.enabled}
                    onChange={(e) => updateEmail("enabled", e.target.checked)}
                    className="accent-[#0069FE]" />
                  <span className="text-sm font-semibold">Ativar envio de email deste agente</span>
                </label>

                <div className="grid grid-cols-2 gap-3">
                  <div><label className="label">Servidor SMTP</label>
                    <input data-testid="email-host" value={selected.email?.host || ""}
                      onChange={(e) => updateEmail("host", e.target.value)}
                      placeholder="smtp.gmail.com" className="input-base" /></div>
                  <div><label className="label">Porta</label>
                    <input data-testid="email-port" type="number" value={selected.email?.port || 587}
                      onChange={(e) => updateEmail("port", parseInt(e.target.value) || 587)}
                      className="input-base" /></div>
                  <div><label className="label">Segurança</label>
                    <select data-testid="email-secure" value={selected.email?.secure || "tls"}
                      onChange={(e) => updateEmail("secure", e.target.value)}
                      className="input-base">
                      <option value="tls">STARTTLS (587)</option>
                      <option value="ssl">SSL/TLS (465)</option>
                      <option value="none">Nenhuma</option>
                    </select></div>
                  <div><label className="label">Utilizador</label>
                    <input data-testid="email-username" value={selected.email?.username || ""}
                      onChange={(e) => updateEmail("username", e.target.value)}
                      className="input-base" /></div>
                  <div className="col-span-2"><label className="label">Palavra-passe</label>
                    <input data-testid="email-password" type="password"
                      value={selected.email?.password || ""}
                      onChange={(e) => updateEmail("password", e.target.value)}
                      className="input-base" /></div>
                  <div><label className="label">Email remetente</label>
                    <input data-testid="email-from" type="email" value={selected.email?.from_email || ""}
                      onChange={(e) => updateEmail("from_email", e.target.value)}
                      placeholder="naoresponder@empresa.pt" className="input-base" /></div>
                  <div><label className="label">Email destino dos leads</label>
                    <input data-testid="email-notify" type="email" value={selected.email?.notify_email || ""}
                      onChange={(e) => updateEmail("notify_email", e.target.value)}
                      placeholder="vendas@empresa.pt" className="input-base" /></div>
                </div>

                <div className="pt-4 border-t border-[#E5EAF2]">
                  <label className="label">Enviar email de teste para</label>
                  <div className="flex gap-2">
                    <input data-testid="email-test-to" value={emailTo} onChange={(e) => setEmailTo(e.target.value)}
                      placeholder={selected.email?.notify_email || selected.email?.from_email || "destino@empresa.pt"}
                      className="input-base flex-1" />
                    <button data-testid="btn-test-email" onClick={testEmail} disabled={emailTest?.loading}
                      className="btn-primary">
                      {emailTest?.loading ? "A enviar…" : "Enviar teste"}
                    </button>
                  </div>
                  {emailTest && !emailTest.loading && (
                    <div className={`mt-2 text-xs flex items-center gap-2 ${emailTest.ok ? "text-[#16A34A]" : "text-[#DC2626]"}`}>
                      {emailTest.ok ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                      {emailTest.ok ? "Email enviado com sucesso!" : (emailTest.error || "Falha")}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ======= INSTALL ======= */}
            {tab === "install" && (
              <div className="space-y-5" data-testid="install-panel">
                <div className="card-surface p-6">
                  <div className="flex items-center gap-2 mb-1">
                    <Code2 size={16} className="text-[#0069FE]" />
                    <div className="font-display font-semibold">Opção 1 — Script (recomendado)</div>
                    <span className="ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#DBEAFE] text-[#0049B5] uppercase tracking-wider">Bolha flutuante</span>
                  </div>
                  <p className="text-xs text-[#5B6B82] mb-3">Cole este código antes de <code>&lt;/body&gt;</code>. Cria automaticamente um ícone flutuante no canto da página.</p>
                  <div className="relative">
                    <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 pr-24 text-xs overflow-x-auto whitespace-pre-wrap">{scriptSnippet || "Guarde o agente para gerar o código."}</pre>
                    {selected.id && (
                      <button data-testid="btn-copy-script" onClick={() => copy("script", scriptSnippet)}
                        className="absolute top-2 right-2 btn-ghost text-[11px] py-1">
                        <Copy size={10} /> {copied === "script" ? "Copiado" : "Copiar"}
                      </button>
                    )}
                  </div>
                </div>

                <div className="card-surface p-6">
                  <div className="flex items-center gap-2 mb-1">
                    <Code2 size={16} className="text-[#0069FE]" />
                    <div className="font-display font-semibold">Opção 2 — iFrame</div>
                    <span className="ml-auto text-[10px] font-bold px-2 py-0.5 rounded-full bg-[#EDE9FE] text-[#5B21B6] uppercase tracking-wider">Embutido</span>
                  </div>
                  <p className="text-xs text-[#5B6B82] mb-3">
                    Cole este código <b>onde quiser que o chat apareça embutido na página</b> (ex.: secção de contacto, página de produto). Reflete sempre as últimas configurações deste agente.
                  </p>
                  <div className="relative">
                    <pre data-testid="iframe-snippet" className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 pr-24 text-xs overflow-x-auto whitespace-pre-wrap">{iframeSnippet || "Guarde o agente para gerar o código."}</pre>
                    {selected.id && (
                      <button data-testid="btn-copy-iframe" onClick={() => copy("iframe", iframeSnippet)}
                        className="absolute top-2 right-2 btn-ghost text-[11px] py-1">
                        <Copy size={10} /> {copied === "iframe" ? "Copiado" : "Copiar"}
                      </button>
                    )}
                  </div>
                  <p className="mt-3 text-[11px] text-[#5B6B82]">
                    💡 Ajuste <code>height</code> e <code>max-width</code> ao seu layout. O chat é responsivo e funciona em qualquer site, sem CORS.
                  </p>
                </div>

                <div className="card-surface p-6">
                  <div className="flex items-center gap-2 mb-1">
                    <Code2 size={16} className="text-[#0069FE]" />
                    <div className="font-display font-semibold">Opção 3 — Shortcode (WordPress)</div>
                  </div>
                  <p className="text-xs text-[#5B6B82] mb-3">Requer o plugin oficial Consenso+ ou a função PHP abaixo em <code>functions.php</code>.</p>
                  <div className="relative">
                    <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 pr-24 text-xs overflow-x-auto">{shortcode || "Guarde o agente primeiro."}</pre>
                    {selected.id && (
                      <button data-testid="btn-copy-shortcode" onClick={() => copy("sc", shortcode)}
                        className="absolute top-2 right-2 btn-ghost text-[11px] py-1">
                        <Copy size={10} /> {copied === "sc" ? "Copiado" : "Copiar"}
                      </button>
                    )}
                  </div>

                  <div className="mt-4 text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Alternativa: functions.php</div>
                  <div className="relative mt-1">
                    <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 pr-24 text-[11px] overflow-x-auto whitespace-pre-wrap">{phpSnippet || "Guarde o agente primeiro."}</pre>
                    {selected.id && (
                      <button data-testid="btn-copy-php" onClick={() => copy("php", phpSnippet)}
                        className="absolute top-2 right-2 btn-ghost text-[11px] py-1">
                        <Copy size={10} /> {copied === "php" ? "Copiado" : "Copiar"}
                      </button>
                    )}
                  </div>
                </div>

                <div className="card-surface p-6">
                  <div className="font-display font-semibold mb-3">Passos de instalação</div>
                  <ol className="space-y-2 text-sm text-[#2C3A52]">
                    <li>1. Escolha a opção que melhor encaixa: <b>Script</b> (bolha flutuante) ou <b>iFrame</b> (embutido na página).</li>
                    <li>2. Copie o código respetivo.</li>
                    <li>3. Cole no HTML do seu site (antes de <code>&lt;/body&gt;</code> para o Script; em qualquer secção para o iFrame).</li>
                    <li>4. Publique. O agente <b>{selected.name}</b> fica disponível imediatamente.</li>
                  </ol>
                </div>

                {selected.id && (
                  <div className="card-surface p-6">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <div className="font-display font-semibold">Demonstração ao vivo</div>
                        <p className="text-xs text-[#5B6B82] mt-0.5">Página profissional pronta a partilhar com clientes — mostra o agente em ação.</p>
                      </div>
                      <a data-testid="btn-test-real-page" href={testPageUrl} target="_blank" rel="noreferrer" className="btn-primary text-[12px]">
                        <Zap size={11} /> Abrir demonstração
                      </a>
                    </div>
                  </div>
                )}

                {selected.id && (
                  <div className="card-surface p-6">
                    <div className="flex items-center justify-between mb-3">
                      <div className="font-display font-semibold">Pré-visualização (iFrame em direto)</div>
                      <a data-testid="btn-open-widget" href={iframeSrc} target="_blank" rel="noreferrer" className="btn-ghost text-[12px]">
                        <Eye size={11} /> Abrir em separador
                      </a>
                    </div>
                    <iframe data-testid="widget-preview" src={iframeSrc} title="Pré-visualização"
                      className="w-full h-[600px] border border-[#E5EAF2] rounded-xl bg-white" />
                  </div>
                )}
              </div>
            )}

            {/* ======= DATA SOURCES + TOOLS ======= */}
            {tab === "data" && (
              <div className="space-y-5">
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
              </div>
            )}

            {/* ======= AUTOMATION: Feeds + Follow-up ======= */}
            {tab === "automation" && (
              <AgentAutomation agentId={selected.id} />
            )}

            {/* ======= PREVIEW (simulated) ======= */}
            {tab === "preview" && (
              <div className="card-surface p-0 overflow-hidden" data-testid="preview-panel">
                <div className="p-4 border-b border-[#E5EAF2] bg-gradient-to-r from-[#0069FE] to-[#003F99] text-white flex items-center gap-3">
                  <div className="w-11 h-11 rounded-full bg-white/20 border-2 border-white/30 flex items-center justify-center overflow-hidden">
                    {selected.avatar_url
                      ? <img src={selected.avatar_url} alt={selected.name} className="w-full h-full object-cover" onError={(e) => { e.target.style.display = "none"; }} />
                      : <span className="font-bold">{(selected.name || "A").slice(0, 2).toUpperCase()}</span>}
                  </div>
                  <div>
                    <div className="font-semibold">{selected.name}</div>
                    <div className="text-[11px] opacity-90 flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#7CFFA3] live-dot" /> Online · simulação
                    </div>
                  </div>
                </div>

                <div className="h-[420px] overflow-y-auto p-4 space-y-3 bg-[#F7F9FC]">
                  {chat.length === 0 && (
                    <>
                      <div className="flex gap-2">
                        <div className="max-w-[78%] rounded-2xl rounded-bl-sm px-3 py-2 bg-white border border-[#E5EAF2] text-sm">
                          {selected.welcome_message || "Olá! Como posso ajudar?"}
                        </div>
                      </div>
                      {(selected.icebreakers || []).filter(Boolean).length > 0 && (
                        <div className="flex flex-wrap gap-2">
                          {selected.icebreakers.filter(Boolean).map((q, i) => (
                            <button key={i} data-testid={`preview-ice-${i}`} onClick={() => sendPreview(q)}
                              className="text-xs px-3 py-1.5 rounded-full bg-white border border-[#C7DDFF] text-[#0069FE] hover:bg-[#EAF2FF]">
                              {q}
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                  {chat.map((m, i) => (
                    <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                      <div className="max-w-[82%]">
                        <div className={`rounded-2xl px-3 py-2 text-sm ${
                          m.role === "user" ? "bg-[#0069FE] text-white rounded-br-sm"
                          : m.error ? "bg-[#FEE2E2] border border-[#FCA5A5] text-[#991B1B] rounded-bl-sm"
                          : "bg-white border border-[#E5EAF2] rounded-bl-sm"
                        }`}>{m.text}</div>
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
                      </div>
                    </div>
                  ))}
                  {chatBusy && <div className="text-xs text-[#5B6B82]">A IA está a escrever…</div>}
                  <div ref={chatEndRef} />
                </div>

                <div className="p-3 border-t border-[#E5EAF2] flex gap-2 bg-white">
                  <input data-testid="preview-input" value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && sendPreview()}
                    placeholder="Escrever como cliente…" className="input-base flex-1" />
                  <button data-testid="btn-send-preview" onClick={() => sendPreview()} disabled={chatBusy} className="btn-primary"><Send size={12} /></button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ============ TRANSLATE MODAL ============ */}
      {translateOpen && (
        <div
          data-testid="translate-modal"
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget && !translateBusy) setTranslateOpen(false); }}
        >
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-full bg-[#E8F1F9] flex items-center justify-center text-[#0069FE]">
                  <Languages size={18} />
                </div>
                <div>
                  <div className="font-display font-bold text-lg leading-tight">Duplicar e Traduzir</div>
                  <div className="text-xs text-[#5B6B82]">Cria uma cópia traduzida com OpenAI</div>
                </div>
              </div>
              {!translateBusy && (
                <button onClick={() => setTranslateOpen(false)} className="text-[#5B6B82] hover:text-[#0F172A]">
                  <X size={18} />
                </button>
              )}
            </div>

            {!translateBusy ? (
              <>
                <p className="text-sm text-[#5B6B82] mb-4">
                  Vai duplicar <b>{selected?.name}</b> e traduzir automaticamente todos os textos (nome, prompt, regras, knowledge, icebreakers, welcome). IDs, chaves API e webhooks <u>não são copiados</u>.
                </p>

                <label className="label">Idioma de destino</label>
                <select
                  data-testid="translate-target"
                  value={translateTarget}
                  onChange={(e) => setTranslateTarget(e.target.value)}
                  className="input-base mb-1"
                >
                  <option value="pt">🇵🇹 Português Europeu (pt-PT)</option>
                  <option value="en">🇬🇧 English</option>
                  <option value="es">🇪🇸 Español</option>
                  <option value="fr">🇫🇷 Français</option>
                  <option value="de">🇩🇪 Deutsch</option>
                  <option value="ca">🏴 Català</option>
                </select>
                <p className="text-[11px] text-[#5B6B82] mb-4">
                  A tradução pode demorar até 90 segundos para agentes com prompts grandes. <b>Não feches esta janela nem navegues para outra página</b> durante a tradução.
                </p>

                <div className="flex gap-2 justify-end">
                  <button onClick={() => setTranslateOpen(false)} className="btn-ghost text-sm">
                    Cancelar
                  </button>
                  <button
                    data-testid="btn-confirm-translate"
                    onClick={duplicateTranslate}
                    className="btn-primary text-sm"
                  >
                    <Languages size={13} /> Traduzir agora
                  </button>
                </div>
              </>
            ) : (
              <>
                {/* BUSY STATE — barra de progresso visual */}
                <div className="py-3" data-testid="translate-progress">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-semibold text-[#0F172A]">
                      A traduzir para {({pt:"Português",en:"English",es:"Español",fr:"Français",de:"Deutsch",ca:"Català"})[translateTarget]}…
                    </div>
                    <div className="text-xs font-mono text-[#5B6B82] tabular-nums">
                      {translateElapsed}s
                    </div>
                  </div>

                  {/* Determinate progress estimated (90s expected → cap at 95%) */}
                  <div className="w-full h-2 bg-[#E5EAF2] rounded-full overflow-hidden mb-3">
                    <div
                      className="h-full bg-gradient-to-r from-[#4591CE] to-[#0069FE] transition-all duration-700 ease-out"
                      style={{
                        width: `${Math.min(95, (translateElapsed / 60) * 100)}%`,
                      }}
                    />
                  </div>

                  <div className="text-xs text-[#5B6B82] space-y-1">
                    <div className="flex items-center gap-2">
                      <Loader2 size={12} className="animate-spin text-[#0069FE]" />
                      A traduzir nome, prompt, regras, knowledge, icebreakers e welcome…
                    </div>
                    <div className="text-[11px] text-[#94A3B8] mt-3">
                      ⚠️ Aguarda — não feches esta janela nem navegues para outra página. A página vai recarregar a lista de agentes assim que terminar.
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Agentes;
