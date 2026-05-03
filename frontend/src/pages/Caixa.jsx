import React, { useEffect, useState, useRef, useCallback, useMemo } from "react";
import { api, API } from "../lib/api";
import { toast } from "sonner";
import {
  Send, UserCheck, Zap, X, MessageSquare, Instagram,
  Globe, Phone, Tag, ExternalLink, Sparkles, ArrowDown,
} from "lucide-react";

const channelIcons = { webchat: Globe, whatsapp: Phone, instagram: Instagram, telegram: Send, messenger: MessageSquare };
const statusBadge = { ai: "badge-blue", human: "badge-green", closed: "badge-ghost", open: "badge-amber" };
const statusLabel = { ai: "IA", human: "Humano", closed: "Fechada", open: "Aberta" };

const NEAR_BOTTOM_PX = 120;

const Caixa = () => {
  const [convos, setConvos] = useState([]);
  const [agents, setAgents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [conversation, setConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [threadError, setThreadError] = useState(null);
  const [channelFilter, setChannelFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [agentFilter, setAgentFilter] = useState("all");
  const [input, setInput] = useState("");
  const [simText, setSimText] = useState("");
  const [simName, setSimName] = useState("Visitante Teste");
  const [simChannel, setSimChannel] = useState("webchat");
  const [sending, setSending] = useState(false);
  const [newMsgPill, setNewMsgPill] = useState(false);

  // Refs
  const msgsContainerRef = useRef(null);
  const selectedIdRef = useRef(null);
  const filtersRef = useRef({ channelFilter, statusFilter, agentFilter });
  const wsRef = useRef(null);
  const pendingScrollRef = useRef(null); // 'bottom' | null — used across async loads

  useEffect(() => { selectedIdRef.current = selectedId; }, [selectedId]);
  useEffect(() => { filtersRef.current = { channelFilter, statusFilter, agentFilter }; }, [channelFilter, statusFilter, agentFilter]);

  // ===== Scroll helpers (operate ONLY on the messages container) =====
  const isNearBottom = () => {
    const el = msgsContainerRef.current;
    if (!el) return true;
    return el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX;
  };
  const scrollToBottom = (smooth = false) => {
    const el = msgsContainerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? "smooth" : "auto" });
    setNewMsgPill(false);
  };

  // ===== Data loading =====
  const loadConvos = useCallback(async () => {
    const { data } = await api.get("/conversations", {
      params: {
        channel: filtersRef.current.channelFilter,
        status: filtersRef.current.statusFilter,
        agent_id: filtersRef.current.agentFilter,
      },
    });
    setConvos(data);
    // Do not auto-select here — we only auto-select on first mount (separate effect below)
    return data;
  }, []);

  const loadAgents = useCallback(async () => {
    setAgents((await api.get("/agents")).data);
  }, []);

  const loadThread = useCallback(async (id) => {
    if (!id) return;
    setLoadingThread(true); setThreadError(null);
    try {
      const { data } = await api.get(`/conversations/${id}`);
      setConversation(data.conversation);
      setMessages(data.messages);
      pendingScrollRef.current = "bottom";
    } catch (e) {
      setThreadError(e?.response?.data?.detail || "Falha a carregar");
    } finally {
      setLoadingThread(false);
    }
  }, []);

  // ===== Mount effects =====
  useEffect(() => { loadAgents(); }, [loadAgents]);

  // Reload convos when filters change; auto-select first only on the very first load
  const autoSelectedRef = useRef(false);
  useEffect(() => {
    loadConvos().then(data => {
      if (!autoSelectedRef.current && (data?.length || 0) > 0 && !selectedIdRef.current) {
        autoSelectedRef.current = true;
        setSelectedId(data[0].id);
      }
    });
  }, [channelFilter, statusFilter, agentFilter, loadConvos]);

  // Load thread whenever selectedId changes
  useEffect(() => {
    if (selectedId) loadThread(selectedId);
    else { setConversation(null); setMessages([]); }
  }, [selectedId, loadThread]);

  // After thread data applied, snap scroll to bottom (only on full reload, not on incremental appends)
  useEffect(() => {
    if (pendingScrollRef.current === "bottom") {
      pendingScrollRef.current = null;
      // double rAF to ensure layout is committed
      requestAnimationFrame(() => requestAnimationFrame(() => scrollToBottom(false)));
    }
  }, [conversation?.id]);

  // ===== WebSocket (connect ONCE) =====
  useEffect(() => {
    const token = localStorage.getItem("cp_token");
    if (!token) return;
    let tenantId;
    try { tenantId = JSON.parse(atob(token.split(".")[1])).tenant_id; }
    catch { return; }

    const wsUrl = API.replace(/^http/, "ws") + `/ws/${tenantId}`;
    let ws;
    let closed = false;
    let reconnectTimer;

    const connect = () => {
      if (closed) return;
      try { ws = new WebSocket(wsUrl); }
      catch { reconnectTimer = setTimeout(connect, 3000); return; }
      wsRef.current = ws;

      ws.onmessage = (e) => {
        let payload;
        try { payload = JSON.parse(e.data); } catch { return; }

        if (payload.type === "message") {
          const msg = payload.message;
          // Always refresh the list (updates last_message / unread / action_counts)
          loadConvos();
          // Append only if this message belongs to the open conversation
          if (msg && msg.conversation_id === selectedIdRef.current) {
            const wasNear = isNearBottom();
            setMessages(prev => {
              // dedupe by id
              if (prev.some(m => m.id === msg.id)) return prev;
              return [...prev, msg];
            });
            // Preserve user scroll position if they scrolled up — just show a pill
            if (wasNear || msg.sender === "human") {
              requestAnimationFrame(() => scrollToBottom(true));
            } else {
              setNewMsgPill(true);
            }
          }
        } else if (payload.type === "conversation_update") {
          loadConvos();
          if (payload.conversation_id === selectedIdRef.current) {
            // Refresh just the conversation metadata (status etc) — keep messages intact
            api.get(`/conversations/${payload.conversation_id}`).then(({ data }) => {
              setConversation(data.conversation);
            }).catch(() => {});
          }
        }
      };

      ws.onclose = () => {
        if (!closed) reconnectTimer = setTimeout(connect, 2500);
      };
      ws.onerror = () => { try { ws.close(); } catch {/* ignore */} };
    };

    connect();
    return () => {
      closed = true;
      clearTimeout(reconnectTimer);
      if (wsRef.current) { try { wsRef.current.close(); } catch {/* ignore */} }
    };
  }, [loadConvos]);

  // ===== Actions =====
  const send = async () => {
    if (!input.trim() || !selectedId) return;
    const text = input;
    setInput(""); setSending(true);
    try {
      const { data: msg } = await api.post(`/conversations/${selectedId}/messages`, { text });
      // Append locally (WS will also deliver but dedupe)
      setMessages(prev => prev.some(m => m.id === msg.id) ? prev : [...prev, msg]);
      requestAnimationFrame(() => scrollToBottom(true));
    } catch {
      toast.error("Falha ao enviar");
      setInput(text); // restore
    } finally { setSending(false); }
  };

  const takeover = async () => {
    try { await api.post(`/conversations/${selectedId}/takeover`); toast.success("Assumiu a conversa."); }
    catch { toast.error("Falha"); }
  };
  const release = async () => {
    try { await api.post(`/conversations/${selectedId}/release`); toast.success("IA retomou."); }
    catch { toast.error("Falha"); }
  };
  const closeC = async () => {
    try { await api.post(`/conversations/${selectedId}/close`); toast.success("Conversa fechada."); }
    catch { toast.error("Falha"); }
  };

  const simulate = async () => {
    if (!simText.trim()) return;
    setSending(true);
    try {
      const { data } = await api.post("/inbound/simulate", {
        channel: simChannel,
        external_user_id: simName.toLowerCase().replace(/\s+/g, "-"),
        contact_name: simName, text: simText,
      });
      toast.success("IA processou a mensagem.");
      setSimText("");
      if (data.conversation_id !== selectedId) setSelectedId(data.conversation_id);
    } catch { toast.error("Falha na simulação."); }
    finally { setSending(false); }
  };

  const intent = conversation?.intent;

  // Memoize the rendered message list to prevent re-rendering when only the list changes
  const renderedMessages = useMemo(() => (
    messages.map(m => <MessageRow key={m.id} m={m} />)
  ), [messages]);

  return (
    <div className="h-full grid grid-cols-[340px_1fr_340px]">
      {/* LEFT */}
      <div className="border-r border-[#E5EAF2] bg-white flex flex-col" data-testid="caixa-list">
        <div className="p-4 border-b border-[#E5EAF2]">
          <div className="flex items-center justify-between">
            <h1 className="font-display text-xl font-bold">Caixa de entrada</h1>
            <span className="badge badge-ghost">{convos.length}</span>
          </div>
          <div className="flex gap-1.5 mt-3 flex-wrap">
            {[["all", "Todas"], ["ai", "IA"], ["human", "Humano"], ["closed", "Fechada"]].map(([s, l]) => (
              <button key={s} data-testid={`filter-status-${s}`} onClick={() => setStatusFilter(s)}
                className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${
                  statusFilter === s ? "bg-[#0069FE] text-white border-[#0069FE]" : "border-[#E5EAF2] text-[#5B6B82] hover:bg-[#F7F9FC]"
                }`}>{l}</button>
            ))}
          </div>
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {[["all", "Todos"], ["webchat", "Web"], ["whatsapp", "WA"], ["telegram", "TG"]].map(([c, l]) => (
              <button key={c} data-testid={`filter-channel-${c}`} onClick={() => setChannelFilter(c)}
                className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${
                  channelFilter === c ? "bg-[#EAF2FF] text-[#0069FE] border-[#C7DDFF]" : "border-[#E5EAF2] text-[#5B6B82] hover:bg-[#F7F9FC]"
                }`}>{l}</button>
            ))}
          </div>
          {agents.length > 1 && (
            <div className="mt-2">
              <select data-testid="filter-agent" value={agentFilter} onChange={(e) => setAgentFilter(e.target.value)}
                className="w-full text-[12px] px-2 py-1.5 border border-[#E5EAF2] rounded-lg bg-white">
                <option value="all">Todos os agentes</option>
                {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
              </select>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-y-auto" data-testid="convo-list">
          {convos.map(c => (
            <ConvoItem key={c.id} c={c} isSel={c.id === selectedId} onClick={() => setSelectedId(c.id)} />
          ))}
          {convos.length === 0 && (
            <div className="p-8 text-center text-sm text-[#5B6B82]">Sem conversas.</div>
          )}
        </div>
      </div>

      {/* CENTER */}
      <div className="flex flex-col h-full bg-[#F7F9FC] relative min-h-0" data-testid="caixa-thread">
        {!conversation && !loadingThread && (
          <div className="flex-1 flex items-center justify-center text-[#5B6B82] text-sm">
            Selecione uma conversa
          </div>
        )}
        {conversation && (
          <>
            <div className="border-b border-[#E5EAF2] bg-white p-4 flex items-center justify-between shrink-0">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-display font-semibold text-lg">{conversation.contact_name}</span>
                  <span className={`badge ${statusBadge[conversation.status]}`}>{statusLabel[conversation.status]}</span>
                  {conversation.language && <span className="badge badge-ghost">{conversation.language.toUpperCase()}</span>}
                </div>
                <div className="text-xs text-[#5B6B82] mt-0.5 uppercase tracking-wider font-semibold">
                  {conversation.channel} · {new Date(conversation.created_at).toLocaleDateString("pt-PT")} · {messages.length} mensagens
                </div>
              </div>
              <div className="flex gap-2">
                {conversation.status !== "human" && (
                  <button data-testid="btn-takeover" onClick={takeover} className="btn-ghost text-[13px]">
                    <UserCheck size={14} /> Assumir
                  </button>
                )}
                {conversation.status === "human" && (
                  <button data-testid="btn-release" onClick={release} className="btn-ghost text-[13px]">
                    <Zap size={14} /> Voltar à IA
                  </button>
                )}
                {conversation.status !== "closed" && (
                  <button data-testid="btn-close" onClick={closeC} className="btn-ghost text-[13px] hover:text-[#DC2626]">
                    <X size={14} /> Fechar
                  </button>
                )}
              </div>
            </div>

            <div ref={msgsContainerRef}
              onScroll={() => { if (isNearBottom()) setNewMsgPill(false); }}
              className="flex-1 overflow-y-auto overflow-x-hidden p-6 space-y-4 min-h-0"
              data-testid="thread-messages">
              {threadError && (
                <div className="p-4 bg-[#FEE2E2] border border-[#FCA5A5] rounded-xl text-sm text-[#991B1B] flex items-center justify-between">
                  <span>{threadError}</span>
                  <button onClick={() => loadThread(selectedId)} className="font-semibold underline">Tentar novamente</button>
                </div>
              )}
              {loadingThread && messages.length === 0 && (
                <div className="text-center text-sm text-[#5B6B82] py-12">A carregar…</div>
              )}
              {renderedMessages}
            </div>

            {newMsgPill && (
              <button data-testid="btn-new-msg-pill" onClick={() => scrollToBottom(true)}
                className="absolute bottom-20 left-1/2 -translate-x-1/2 z-10 bg-[#0069FE] text-white px-3 py-1.5 rounded-full text-xs font-semibold shadow-lg flex items-center gap-1.5 hover:bg-[#0057D5]">
                <ArrowDown size={12} /> Novas mensagens
              </button>
            )}

            <div className="border-t border-[#E5EAF2] bg-white p-3 flex gap-2 shrink-0" data-testid="thread-composer">
              <input data-testid="thread-input" value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                placeholder={conversation.status === "human" ? "Escreva como agente humano…" : "Escrever resposta (pausa a IA)"}
                className="input-base flex-1" />
              <button data-testid="btn-send-message" onClick={send} disabled={sending}
                className="btn-primary"><Send size={14} /> Enviar</button>
            </div>
          </>
        )}
      </div>

      {/* RIGHT */}
      <div className="border-l border-[#E5EAF2] bg-white overflow-y-auto" data-testid="caixa-context">
        <div className="p-5 border-b border-[#E5EAF2]">
          <div className="label">Contacto</div>
          <div className="font-display font-semibold text-lg">{conversation?.contact_name || "—"}</div>
          <div className="text-xs text-[#5B6B82] mt-0.5 uppercase tracking-wider font-semibold">
            via {conversation?.channel}
          </div>
        </div>

        {intent && (
          <div className="p-5 border-b border-[#E5EAF2]">
            <div className="label flex items-center gap-1.5"><Sparkles size={12} className="text-[#0069FE]" /> Análise de IA</div>
            <div className="mt-3 space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-[#5B6B82]">Intenção</span><span className="font-semibold text-[#0069FE]">{intent.intent}</span></div>
              <div className="flex justify-between"><span className="text-[#5B6B82]">Categoria</span><span className="font-semibold">{intent.category}</span></div>
              <div className="flex justify-between"><span className="text-[#5B6B82]">Urgência</span>
                <span className={`badge ${intent.urgency === "urgent" ? "badge-red" : intent.urgency === "high" ? "badge-amber" : "badge-ghost"}`}>{intent.urgency}</span>
              </div>
              <div className="flex justify-between"><span className="text-[#5B6B82]">Confiança</span><span className="font-semibold">{Math.round((intent.confidence || 0) * 100)}%</span></div>
            </div>
          </div>
        )}

        {conversation?.tags?.length > 0 && (
          <div className="p-5 border-b border-[#E5EAF2]">
            <div className="label flex items-center gap-1"><Tag size={12} /> Tags</div>
            <div className="flex gap-1.5 flex-wrap mt-2">
              {conversation.tags.map(t => <span key={t} className="badge badge-blue">{t}</span>)}
            </div>
          </div>
        )}

        <div className="p-5">
          <div className="label">Simular mensagem</div>
          <p className="text-xs text-[#5B6B82] mb-3">Teste o pipeline completo de IA a partir de qualquer canal.</p>
          <div className="space-y-2">
            <input data-testid="sim-name" value={simName} onChange={(e) => setSimName(e.target.value)}
              placeholder="Nome" className="input-base text-sm" />
            <select data-testid="sim-channel" value={simChannel} onChange={(e) => setSimChannel(e.target.value)} className="input-base text-sm">
              {["webchat", "whatsapp", "telegram"].map(c => <option key={c}>{c}</option>)}
            </select>
            <textarea data-testid="sim-text" value={simText} onChange={(e) => setSimText(e.target.value)}
              rows={3} placeholder="Mensagem a simular…" className="input-base text-sm" />
            <button data-testid="btn-simulate" onClick={simulate} disabled={sending}
              className="btn-primary w-full justify-center">
              {sending ? "A processar…" : "Enviar para IA →"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// ===== Sub-components (memoized) =====
const ConvoItem = React.memo(function ConvoItem({ c, isSel, onClick }) {
  const Icon = channelIcons[c.channel] || Globe;
  return (
    <button data-testid={`convo-item-${c.id}`} onClick={onClick}
      className={`w-full text-left border-b border-[#E5EAF2] p-3.5 transition-colors ${isSel ? "bg-[#EAF2FF]" : "hover:bg-[#F7F9FC]"}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-full bg-[#EAF2FF] text-[#0069FE] font-bold text-xs flex items-center justify-center shrink-0">
            {c.contact_name.slice(0, 2).toUpperCase()}
          </div>
          <span className="font-semibold text-sm truncate">{c.contact_name}</span>
        </div>
        <span className={`badge ${statusBadge[c.status] || "badge-ghost"} shrink-0`}>{statusLabel[c.status]}</span>
      </div>
      <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-[#5B6B82]">
        <Icon size={10} />
        <span className="uppercase font-semibold">{c.channel}</span>
        {c.unread > 0 && <span className="text-[#0069FE] font-bold">· {c.unread} nova{c.unread > 1 ? "s" : ""}</span>}
      </div>
      <div className="text-[13px] text-[#2C3A52] mt-1 line-clamp-2">{c.last_message}</div>
      {c.tags?.length > 0 && (
        <div className="mt-2 flex gap-1 flex-wrap">
          {c.tags.slice(0, 3).map(t => <span key={t} className="badge badge-ghost">{t}</span>)}
        </div>
      )}
      {c.action_counts && (c.action_counts.leads > 0 || c.action_counts.tickets > 0) && (
        <div className="mt-2 flex gap-1.5 flex-wrap">
          {c.action_counts.leads > 0 && (
            <span className="badge badge-green">⚡ {c.action_counts.leads} lead{c.action_counts.leads > 1 ? "s" : ""}</span>
          )}
          {c.action_counts.tickets > 0 && (
            <span className="badge badge-amber">🎫 {c.action_counts.tickets} ticket{c.action_counts.tickets > 1 ? "s" : ""}</span>
          )}
        </div>
      )}
    </button>
  );
});

const MessageRow = React.memo(function MessageRow({ m }) {
  const isUser = m.sender === "user";
  return (
    <div className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
      <div className={`max-w-[72%] ${isUser ? "" : "flex flex-col items-end"}`}>
        <div className="text-[11px] font-semibold mb-1 text-[#5B6B82]">
          {m.sender_name} · {new Date(m.created_at).toLocaleTimeString("pt-PT", { hour: "2-digit", minute: "2-digit" })}
        </div>
        <div className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser ? "bg-white border border-[#E5EAF2] rounded-bl-md"
            : m.sender === "ai" ? "bg-[#EAF2FF] text-[#0B1324] rounded-br-md"
            : "bg-[#0069FE] text-white rounded-br-md"
        }`}>
          <div className="whitespace-pre-wrap">{m.text}</div>
        </div>
        {m.cards?.length > 0 && (
          <div className="mt-3 grid gap-2 max-w-[320px] w-full">
            {m.cards.map((c, i) => (
              <div key={i} className="card-surface overflow-hidden hover:shadow-md transition-shadow">
                {c.image && <img src={c.image} alt={c.title} className="w-full h-28 object-cover" onError={(e) => { e.target.style.display = "none"; }} />}
                <div className="p-3">
                  <div className="font-semibold text-sm leading-tight">{c.title}</div>
                  {c.price && <div className="text-[#0069FE] font-bold text-sm mt-1">{c.price}</div>}
                  {c.description && <div className="text-xs text-[#5B6B82] mt-1 line-clamp-2">{c.description}</div>}
                  {c.link && (
                    <a href={c.link} target="_blank" rel="noreferrer"
                      className="mt-2 text-xs text-[#0069FE] font-semibold inline-flex items-center gap-1 hover:underline">
                      Ver mais <ExternalLink size={11} />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
});

export default Caixa;
