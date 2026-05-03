import React, { useEffect, useState, useRef } from "react";
import { api, API } from "../lib/api";
import { toast } from "sonner";
import {
  Send, UserCheck, Zap, X, MessageSquare, Instagram,
  Globe, Phone, Tag, ExternalLink, Sparkles,
} from "lucide-react";

const channelIcons = { webchat: Globe, whatsapp: Phone, instagram: Instagram, telegram: Send, messenger: MessageSquare };

const statusBadge = {
  ai: "badge-blue",
  human: "badge-green",
  closed: "badge-ghost",
  open: "badge-amber",
};

const statusLabel = { ai: "IA", human: "Humano", closed: "Fechada", open: "Aberta" };

const Caixa = () => {
  const [convos, setConvos] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [thread, setThread] = useState(null);
  const [channelFilter, setChannelFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [input, setInput] = useState("");
  const [simText, setSimText] = useState("");
  const [simName, setSimName] = useState("Visitante Teste");
  const [simChannel, setSimChannel] = useState("webchat");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);
  const wsRef = useRef(null);

  const loadConvos = async () => {
    const { data } = await api.get("/conversations", { params: { channel: channelFilter, status: statusFilter } });
    setConvos(data);
    if (!selectedId && data.length > 0) setSelectedId(data[0].id);
  };
  const loadThread = async (id) => {
    if (!id) return;
    const { data } = await api.get(`/conversations/${id}`);
    setThread(data);
    setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  useEffect(() => { loadConvos(); /* eslint-disable-next-line */ }, [channelFilter, statusFilter]);
  useEffect(() => { loadThread(selectedId); /* eslint-disable-next-line */ }, [selectedId]);

  // WebSocket live updates
  useEffect(() => {
    const token = localStorage.getItem("cp_token");
    if (!token) return;
    const tenantId = JSON.parse(atob(token.split(".")[1])).tenant_id;
    const wsUrl = API.replace(/^http/, "ws") + `/ws/${tenantId}`;
    let ws;
    let cancelled = false;
    // small delay to avoid StrictMode double-mount tearing down an open socket
    const t = setTimeout(() => {
      if (cancelled) return;
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const payload = JSON.parse(e.data);
          if (payload.type === "message" || payload.type === "conversation_update") {
            loadConvos();
            if (payload.conversation_id === selectedId) loadThread(selectedId);
          }
        } catch { /* ignore */ }
      };
    }, 150);
    return () => {
      cancelled = true;
      clearTimeout(t);
      if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    };
    // eslint-disable-next-line
  }, [selectedId]);

  const send = async () => {
    if (!input.trim() || !selectedId) return;
    setSending(true);
    try {
      await api.post(`/conversations/${selectedId}/messages`, { text: input });
      setInput("");
      await loadThread(selectedId); loadConvos();
    } catch { toast.error("Falha ao enviar"); }
    finally { setSending(false); }
  };

  const takeover = async () => { await api.post(`/conversations/${selectedId}/takeover`); toast.success("Assumiu a conversa."); loadThread(selectedId); loadConvos(); };
  const release = async () => { await api.post(`/conversations/${selectedId}/release`); toast.success("IA retomou."); loadThread(selectedId); loadConvos(); };
  const closeC = async () => { await api.post(`/conversations/${selectedId}/close`); toast.success("Conversa fechada."); loadThread(selectedId); loadConvos(); };

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
      setSimText(""); setSelectedId(data.conversation_id); loadConvos();
    } catch { toast.error("Falha na simulação."); }
    finally { setSending(false); }
  };

  const convo = thread?.conversation;
  const messages = thread?.messages || [];
  const intent = convo?.intent;

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
            {[["all", "Todos"], ["webchat", "Web"], ["whatsapp", "WA"], ["instagram", "IG"], ["telegram", "TG"], ["messenger", "FB"]].map(([c, l]) => (
              <button key={c} data-testid={`filter-channel-${c}`} onClick={() => setChannelFilter(c)}
                className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border transition-colors ${
                  channelFilter === c ? "bg-[#EAF2FF] text-[#0069FE] border-[#C7DDFF]" : "border-[#E5EAF2] text-[#5B6B82] hover:bg-[#F7F9FC]"
                }`}>{l}</button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {convos.map(c => {
            const Icon = channelIcons[c.channel] || Globe;
            const isSel = c.id === selectedId;
            return (
              <button key={c.id} data-testid={`convo-item-${c.id}`} onClick={() => setSelectedId(c.id)}
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
              </button>
            );
          })}
          {convos.length === 0 && (
            <div className="p-8 text-center text-sm text-[#5B6B82]">Sem conversas.</div>
          )}
        </div>
      </div>

      {/* CENTER */}
      <div className="flex flex-col h-full bg-[#F7F9FC]" data-testid="caixa-thread">
        {!convo && (
          <div className="flex-1 flex items-center justify-center text-[#5B6B82] text-sm">
            Selecione uma conversa
          </div>
        )}
        {convo && (
          <>
            <div className="border-b border-[#E5EAF2] bg-white p-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-display font-semibold text-lg">{convo.contact_name}</span>
                  <span className={`badge ${statusBadge[convo.status]}`}>{statusLabel[convo.status]}</span>
                  {convo.language && <span className="badge badge-ghost">{convo.language.toUpperCase()}</span>}
                </div>
                <div className="text-xs text-[#5B6B82] mt-0.5 uppercase tracking-wider font-semibold">
                  {convo.channel} · {new Date(convo.created_at).toLocaleDateString("pt-PT")}
                </div>
              </div>
              <div className="flex gap-2">
                {convo.status !== "human" && (
                  <button data-testid="btn-takeover" onClick={takeover} className="btn-ghost text-[13px]">
                    <UserCheck size={14} /> Assumir
                  </button>
                )}
                {convo.status === "human" && (
                  <button data-testid="btn-release" onClick={release} className="btn-ghost text-[13px]">
                    <Zap size={14} /> Voltar à IA
                  </button>
                )}
                {convo.status !== "closed" && (
                  <button data-testid="btn-close" onClick={closeC} className="btn-ghost text-[13px] hover:text-[#DC2626]">
                    <X size={14} /> Fechar
                  </button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4" data-testid="thread-messages">
              {messages.map(m => {
                const isUser = m.sender === "user";
                return (
                  <div key={m.id} className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
                    <div className={`max-w-[72%] ${isUser ? "" : "flex flex-col items-end"}`}>
                      <div className={`text-[11px] font-semibold mb-1 ${isUser ? "text-[#5B6B82]" : "text-[#5B6B82]"}`}>
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
                              {c.image && <img src={c.image} alt={c.title} className="w-full h-28 object-cover" onError={(e) => e.target.style.display = "none"} />}
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
              })}
              <div ref={endRef} />
            </div>

            <div className="border-t border-[#E5EAF2] bg-white p-3 flex gap-2" data-testid="thread-composer">
              <input data-testid="thread-input" value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                placeholder={convo.status === "human" ? "Escreva como agente humano…" : "Escrever resposta (pausa a IA)"}
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
          <div className="font-display font-semibold text-lg">{convo?.contact_name || "—"}</div>
          <div className="text-xs text-[#5B6B82] mt-0.5 uppercase tracking-wider font-semibold">
            via {convo?.channel}
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

        {convo?.tags?.length > 0 && (
          <div className="p-5 border-b border-[#E5EAF2]">
            <div className="label flex items-center gap-1"><Tag size={12} /> Tags</div>
            <div className="flex gap-1.5 flex-wrap mt-2">
              {convo.tags.map(t => <span key={t} className="badge badge-blue">{t}</span>)}
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
              {["webchat", "whatsapp", "instagram", "telegram", "messenger"].map(c => <option key={c}>{c}</option>)}
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

export default Caixa;
