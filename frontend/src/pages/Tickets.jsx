import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const statuses = ["open", "in_progress", "waiting", "resolved", "closed"];
const priorities = ["low", "medium", "high", "urgent"];

const priorityColor = {
  low: "border-zinc-700 text-zinc-400",
  medium: "border-[#EAB308] text-[#EAB308]",
  high: "border-[#FF5500] text-[#FF5500]",
  urgent: "border-[#EF4444] text-[#EF4444]",
};

const Tickets = () => {
  const [tickets, setTickets] = useState([]);
  const [newT, setNewT] = useState({ subject: "", description: "", priority: "medium", status: "open" });
  const [show, setShow] = useState(false);

  const load = async () => setTickets((await api.get("/tickets")).data);
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!newT.subject) return toast.error("Subject required");
    await api.post("/tickets", newT);
    setShow(false); setNewT({ subject: "", description: "", priority: "medium", status: "open" });
    load(); toast.success("Ticket created");
  };
  const update = async (t, changes) => {
    await api.put(`/tickets/${t.id}`, { ...t, ...changes });
    load();
  };
  const del = async (id) => { await api.delete(`/tickets/${id}`); load(); toast.success("Deleted"); };

  return (
    <div className="h-full flex flex-col">
      <div className="border-b border-zinc-800 p-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold uppercase tracking-tight">Support Tickets</h1>
          <div className="mono text-[10px] text-zinc-500 uppercase tracking-widest">
            {tickets.filter(t => t.status !== "closed" && t.status !== "resolved").length} OPEN
          </div>
        </div>
        <button data-testid="btn-new-ticket" onClick={() => setShow(!show)}
          className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-3 py-2 flex items-center gap-1">
          <Plus size={12} /> New Ticket
        </button>
      </div>

      {show && (
        <div className="border-b border-zinc-800 p-4 grid grid-cols-4 gap-2" data-testid="ticket-form">
          <input data-testid="ticket-subject" placeholder="Subject" value={newT.subject}
            onChange={(e) => setNewT({ ...newT, subject: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs col-span-2 focus:border-white outline-none" />
          <select data-testid="ticket-priority" value={newT.priority}
            onChange={(e) => setNewT({ ...newT, priority: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs mono uppercase">
            {priorities.map(p => <option key={p}>{p}</option>)}
          </select>
          <button data-testid="btn-save-ticket" onClick={save}
            className="bg-white text-black mono text-xs uppercase tracking-widest font-bold hover:bg-zinc-200">Create</button>
          <textarea data-testid="ticket-description" placeholder="Description" rows={2}
            value={newT.description} onChange={(e) => setNewT({ ...newT, description: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs col-span-4" />
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        {tickets.map(t => (
          <div key={t.id} data-testid={`ticket-row-${t.id}`} className="border-b border-zinc-800 p-4 hover:bg-zinc-900/50 flex items-center gap-4">
            <span className={`mono text-[10px] uppercase border px-2 py-0.5 ${priorityColor[t.priority]}`}>{t.priority}</span>
            <div className="flex-1">
              <div className="font-semibold">{t.subject}</div>
              <div className="text-xs text-zinc-500 truncate">{t.description}</div>
            </div>
            <select value={t.status} onChange={(e) => update(t, { status: e.target.value })}
              className="bg-[#18181B] border border-zinc-800 px-2 py-1 text-[10px] mono uppercase">
              {statuses.map(s => <option key={s}>{s}</option>)}
            </select>
            <div className="mono text-[10px] text-zinc-500 w-24 text-right">
              {new Date(t.created_at).toLocaleDateString()}
            </div>
            <button data-testid={`btn-delete-ticket-${t.id}`} onClick={() => del(t.id)} className="text-zinc-500 hover:text-[#EF4444]">
              <Trash2 size={12} />
            </button>
          </div>
        ))}
        {tickets.length === 0 && (
          <div className="p-8 text-center text-zinc-500 mono text-xs uppercase tracking-widest">
            No tickets. AI-generated tickets will appear here.
          </div>
        )}
      </div>
    </div>
  );
};

export default Tickets;
