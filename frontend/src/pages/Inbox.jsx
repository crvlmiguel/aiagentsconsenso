import React, { useEffect, useState, useRef } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  Send, UserCheck, UserX, X, Zap, MessageSquare,
  Instagram, Send as TelegramIcon, Phone, Globe, Tag,
} from "lucide-react";

const channelIcons = {
  webchat: Globe,
  whatsapp: Phone,
  instagram: Instagram,
  telegram: TelegramIcon,
  messenger: MessageSquare,
};

const statusColor = {
  ai: "text-[#FF5500] border-[#FF5500]",
  human: "text-[#22C55E] border-[#22C55E]",
  closed: "text-zinc-500 border-zinc-700",
  open: "text-white border-white",
};

const Inbox = () => {
  const [convos, setConvos] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [thread, setThread] = useState(null);
  const [channelFilter, setChannelFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [input, setInput] = useState("");
  const [simText, setSimText] = useState("");
  const [simName, setSimName] = useState("Test Visitor");
  const [simChannel, setSimChannel] = useState("webchat");
  const [sending, setSending] = useState(false);
  const endRef = useRef(null);

  const loadConvos = async () => {
    const { data } = await api.get("/conversations", {
      params: { channel: channelFilter, status: statusFilter },
    });
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

  const send = async () => {
    if (!input.trim() || !selectedId) return;
    setSending(true);
    try {
      await api.post(`/conversations/${selectedId}/messages`, { text: input });
      setInput("");
      await loadThread(selectedId);
      loadConvos();
    } catch (e) {
      toast.error("Failed to send");
    } finally { setSending(false); }
  };

  const takeover = async () => {
    await api.post(`/conversations/${selectedId}/takeover`);
    toast.success("You're now handling this conversation.");
    loadThread(selectedId); loadConvos();
  };
  const release = async () => {
    await api.post(`/conversations/${selectedId}/release`);
    toast.success("AI is back in control.");
    loadThread(selectedId); loadConvos();
  };
  const closeC = async () => {
    await api.post(`/conversations/${selectedId}/close`);
    toast.success("Conversation closed.");
    loadThread(selectedId); loadConvos();
  };

  const simulate = async () => {
    if (!simText.trim()) return;
    setSending(true);
    try {
      const { data } = await api.post("/inbound/simulate", {
        channel: simChannel,
        external_user_id: simName.toLowerCase().replace(/\s+/g, "-"),
        contact_name: simName,
        text: simText,
      });
      toast.success("AI processed the inbound message.");
      setSimText("");
      setSelectedId(data.conversation_id);
      loadConvos();
    } catch (e) { toast.error("Simulation failed."); }
    finally { setSending(false); }
  };

  const convo = thread?.conversation;
  const messages = thread?.messages || [];
  const intent = convo?.intent;

  return (
    <div className="h-full grid grid-cols-[320px_1fr_340px] border-collapse">
      {/* LEFT - Conversation list */}
      <div className="border-r border-zinc-800 flex flex-col h-full" data-testid="inbox-list">
        <div className="p-4 border-b border-zinc-800">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-bold uppercase tracking-tight">Inbox</h1>
            <span className="mono text-[10px] text-zinc-500 uppercase">
              {convos.length} ACTIVE
            </span>
          </div>
          <div className="flex gap-1 mt-3">
            {["all", "ai", "human", "closed"].map((s) => (
              <button
                key={s}
                data-testid={`filter-status-${s}`}
                onClick={() => setStatusFilter(s)}
                className={`mono text-[10px] uppercase tracking-widest px-2 py-1 border ${
                  statusFilter === s ? "border-white bg-zinc-900 text-white" : "border-zinc-800 text-zinc-500 hover:text-white"
                }`}
              >{s}</button>
            ))}
          </div>
          <div className="flex gap-1 mt-2 flex-wrap">
            {["all", "webchat", "whatsapp", "instagram", "telegram", "messenger"].map((c) => (
              <button
                key={c}
                data-testid={`filter-channel-${c}`}
                onClick={() => setChannelFilter(c)}
                className={`mono text-[10px] uppercase tracking-widest px-2 py-1 border ${
                  channelFilter === c ? "border-white bg-zinc-900 text-white" : "border-zinc-800 text-zinc-500 hover:text-white"
                }`}
              >{c}</button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {convos.map((c) => {
            const Icon = channelIcons[c.channel] || Globe;
            const isSel = c.id === selectedId;
            return (
              <button
                key={c.id}
                data-testid={`convo-item-${c.id}`}
                onClick={() => setSelectedId(c.id)}
                className={`w-full text-left border-b border-zinc-800 p-3 border-l-2 transition-colors ${
                  isSel ? "bg-zinc-900 border-l-white" : "border-l-transparent hover:bg-zinc-900/50"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-bold text-sm truncate">{c.contact_name}</span>
                  <span className={`mono text-[9px] uppercase border px-1 ${statusColor[c.status] || "border-zinc-700 text-zinc-400"}`}>
                    {c.status}
                  </span>
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-zinc-500 mono">
                  <Icon size={11} />
                  <span className="uppercase">{c.channel}</span>
                  {c.unread > 0 && (
                    <span className="text-[#FF5500]">· {c.unread} NEW</span>
                  )}
                </div>
                <div className="text-xs text-zinc-400 mt-1 line-clamp-2">{c.last_message}</div>
                {c.tags?.length > 0 && (
                  <div className="mt-2 flex gap-1 flex-wrap">
                    {c.tags.slice(0, 3).map((t) => (
                      <span key={t} className="mono text-[9px] uppercase border border-zinc-700 text-zinc-400 px-1">{t}</span>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
          {convos.length === 0 && (
            <div className="p-8 text-center text-xs text-zinc-500 mono uppercase tracking-widest">
              No conversations
            </div>
          )}
        </div>
      </div>

      {/* CENTER - Thread */}
      <div className="flex flex-col h-full" data-testid="inbox-thread">
        {!convo && (
          <div className="flex-1 flex items-center justify-center text-zinc-500 mono text-xs uppercase tracking-widest">
            Select a conversation
          </div>
        )}
        {convo && (
          <>
            <div className="border-b border-zinc-800 p-4 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-bold text-lg">{convo.contact_name}</span>
                  <span className={`mono text-[10px] uppercase border px-2 py-0.5 ${statusColor[convo.status]}`}>
                    {convo.status === "ai" ? "AI HANDLING" : convo.status === "human" ? "HUMAN" : convo.status}
                  </span>
                </div>
                <div className="mono text-[10px] text-zinc-500 uppercase tracking-widest mt-0.5">
                  {convo.channel} · {new Date(convo.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex gap-2">
                {convo.status !== "human" && (
                  <button data-testid="btn-takeover" onClick={takeover}
                    className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-3 py-2 flex items-center gap-1">
                    <UserCheck size={12} /> Take over
                  </button>
                )}
                {convo.status === "human" && (
                  <button data-testid="btn-release" onClick={release}
                    className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-3 py-2 flex items-center gap-1">
                    <Zap size={12} /> Return to AI
                  </button>
                )}
                {convo.status !== "closed" && (
                  <button data-testid="btn-close" onClick={closeC}
                    className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-[#EF4444] hover:text-[#EF4444] px-3 py-2 flex items-center gap-1">
                    <X size={12} /> Close
                  </button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-4" data-testid="thread-messages">
              {messages.map((m) => {
                const isMe = m.sender !== "user";
                const isAI = m.sender === "ai";
                return (
                  <div key={m.id} className={`flex ${isMe ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-[70%] border border-zinc-800 p-3 text-sm ${isAI ? "ai-bubble bg-zinc-900" : isMe ? "bg-white text-black" : "bg-[#18181B]"}`}>
                      <div className={`mono text-[9px] uppercase tracking-widest mb-1 ${isMe && !isAI ? "text-zinc-600" : "text-zinc-500"}`}>
                        {m.sender_name} · {new Date(m.created_at).toLocaleTimeString()}
                      </div>
                      <div className="whitespace-pre-wrap">{m.text}</div>
                    </div>
                  </div>
                );
              })}
              <div ref={endRef} />
            </div>

            <div className="border-t border-zinc-800 p-3 flex gap-2" data-testid="thread-composer">
              <input
                data-testid="thread-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
                placeholder={convo.status === "human" ? "Type as human agent…" : "Type to reply (this pauses AI)"}
                className="flex-1 bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-3 py-2 text-sm"
              />
              <button
                data-testid="btn-send-message"
                onClick={send} disabled={sending}
                className="bg-white text-black px-4 py-2 font-bold mono text-xs uppercase tracking-widest hover:bg-zinc-200 disabled:opacity-50 flex items-center gap-1"
              >
                <Send size={12} /> Send
              </button>
            </div>
          </>
        )}
      </div>

      {/* RIGHT - Context panel */}
      <div className="border-l border-zinc-800 overflow-y-auto" data-testid="inbox-context">
        <div className="p-4 border-b border-zinc-800">
          <div className="label-mono">CONTACT</div>
          <div className="text-base font-bold mt-1">{convo?.contact_name || "—"}</div>
          <div className="mono text-[10px] text-zinc-500 uppercase mt-0.5">
            via {convo?.channel}
          </div>
        </div>

        {intent && (
          <div className="p-4 border-b border-zinc-800">
            <div className="label-mono">AI INTENT ANALYSIS</div>
            <div className="mt-2 space-y-1.5 mono text-xs">
              <div className="flex justify-between">
                <span className="text-zinc-500">INTENT</span>
                <span className="text-[#FF5500] uppercase">{intent.intent}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">CATEGORY</span>
                <span className="uppercase">{intent.category}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">URGENCY</span>
                <span className={`uppercase ${intent.urgency === "urgent" ? "text-[#EF4444]" : intent.urgency === "high" ? "text-[#EAB308]" : "text-zinc-300"}`}>
                  {intent.urgency}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">CONFIDENCE</span>
                <span>{Math.round((intent.confidence || 0) * 100)}%</span>
              </div>
            </div>
          </div>
        )}

        {convo?.tags?.length > 0 && (
          <div className="p-4 border-b border-zinc-800">
            <div className="label-mono flex items-center gap-1"><Tag size={10} /> TAGS</div>
            <div className="flex gap-1 flex-wrap mt-2">
              {convo.tags.map((t) => (
                <span key={t} className="mono text-[10px] uppercase border border-zinc-700 text-zinc-300 px-2 py-0.5">{t}</span>
              ))}
            </div>
          </div>
        )}

        {/* Simulator */}
        <div className="p-4 border-b border-zinc-800">
          <div className="label-mono">SIMULATE INBOUND MESSAGE</div>
          <div className="text-[10px] text-zinc-500 mt-1 mb-2">
            Test the full AI pipeline from any channel.
          </div>
          <div className="space-y-2">
            <input
              data-testid="sim-name"
              value={simName} onChange={(e) => setSimName(e.target.value)}
              placeholder="Contact name"
              className="w-full bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-2 py-1.5 text-xs mono"
            />
            <select
              data-testid="sim-channel"
              value={simChannel} onChange={(e) => setSimChannel(e.target.value)}
              className="w-full bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-2 py-1.5 text-xs mono uppercase"
            >
              {["webchat", "whatsapp", "instagram", "telegram", "messenger"].map(c => <option key={c}>{c}</option>)}
            </select>
            <textarea
              data-testid="sim-text"
              value={simText} onChange={(e) => setSimText(e.target.value)}
              rows={3} placeholder="Message to simulate…"
              className="w-full bg-[#18181B] border border-zinc-800 focus:border-white outline-none px-2 py-1.5 text-xs"
            />
            <button
              data-testid="btn-simulate"
              onClick={simulate} disabled={sending}
              className="w-full bg-[#FF5500] text-black px-3 py-2 font-bold mono text-[10px] uppercase tracking-widest hover:bg-[#ff7a33] disabled:opacity-50"
            >
              {sending ? "Processing…" : "→ Send to AI pipeline"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Inbox;
