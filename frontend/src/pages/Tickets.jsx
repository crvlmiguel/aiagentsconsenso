import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const statuses = [
  { k: "open", l: "Aberto" }, { k: "in_progress", l: "Em curso" },
  { k: "waiting", l: "A aguardar" }, { k: "resolved", l: "Resolvido" }, { k: "closed", l: "Fechado" },
];
const priorities = [
  { k: "low", l: "Baixa", cls: "badge-ghost" },
  { k: "medium", l: "Média", cls: "badge-amber" },
  { k: "high", l: "Alta", cls: "badge-blue" },
  { k: "urgent", l: "Urgente", cls: "badge-red" },
];

const Tickets = () => {
  const [tickets, setTickets] = useState([]);
  const [newT, setNewT] = useState({ subject: "", description: "", priority: "medium", status: "open" });
  const [show, setShow] = useState(false);

  const load = async () => setTickets((await api.get("/tickets")).data);
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!newT.subject) return toast.error("Assunto obrigatório");
    await api.post("/tickets", newT); setShow(false);
    setNewT({ subject: "", description: "", priority: "medium", status: "open" });
    load(); toast.success("Ticket criado");
  };
  const update = async (t, changes) => { await api.put(`/tickets/${t.id}`, { ...t, ...changes }); load(); };
  const del = async (id) => { await api.delete(`/tickets/${id}`); load(); toast.success("Eliminado"); };

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-display text-2xl font-bold">Tickets</h1>
          <p className="text-sm text-[#5B6B82] mt-1">{tickets.filter(t => t.status !== "closed" && t.status !== "resolved").length} em aberto</p>
        </div>
        <button data-testid="btn-new-ticket" onClick={() => setShow(!show)} className="btn-primary">
          <Plus size={14} /> Novo ticket
        </button>
      </div>

      {show && (
        <div className="card-surface p-5 mb-5 space-y-3" data-testid="ticket-form">
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="label">Assunto</label>
              <input data-testid="ticket-subject" value={newT.subject} onChange={(e) => setNewT({ ...newT, subject: e.target.value })} className="input-base" />
            </div>
            <div>
              <label className="label">Prioridade</label>
              <select data-testid="ticket-priority" value={newT.priority} onChange={(e) => setNewT({ ...newT, priority: e.target.value })} className="input-base">
                {priorities.map(p => <option key={p.k} value={p.k}>{p.l}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="label">Descrição</label>
            <textarea data-testid="ticket-description" rows={3} value={newT.description} onChange={(e) => setNewT({ ...newT, description: e.target.value })} className="input-base" />
          </div>
          <div className="flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setShow(false)}>Cancelar</button>
            <button data-testid="btn-save-ticket" onClick={save} className="btn-primary">Criar</button>
          </div>
        </div>
      )}

      <div className="card-surface divide-y divide-[#E5EAF2]">
        {tickets.map(t => {
          const pr = priorities.find(p => p.k === t.priority) || priorities[1];
          return (
            <div key={t.id} data-testid={`ticket-row-${t.id}`} className="p-4 hover:bg-[#F7F9FC] flex items-center gap-4">
              <span className={`badge ${pr.cls} shrink-0`}>{pr.l}</span>
              <div className="flex-1 min-w-0">
                <div className="font-semibold truncate">{t.subject}</div>
                <div className="text-xs text-[#5B6B82] truncate">{t.description}</div>
              </div>
              <select value={t.status} onChange={(e) => update(t, { status: e.target.value })}
                className="text-xs px-2.5 py-1.5 border border-[#E5EAF2] rounded-lg">
                {statuses.map(s => <option key={s.k} value={s.k}>{s.l}</option>)}
              </select>
              <div className="text-xs text-[#5B6B82] w-24 text-right">{new Date(t.created_at).toLocaleDateString("pt-PT")}</div>
              <button data-testid={`btn-delete-ticket-${t.id}`} onClick={() => del(t.id)} className="text-[#5B6B82] hover:text-[#DC2626]">
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
        {tickets.length === 0 && <div className="p-12 text-center text-sm text-[#5B6B82]">Sem tickets. A IA cria tickets automaticamente para problemas de suporte.</div>}
      </div>
    </div>
  );
};

export default Tickets;
