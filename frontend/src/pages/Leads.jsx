import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2 } from "lucide-react";

const stages = [
  { k: "new", l: "Novo", cls: "badge-ghost" },
  { k: "contacted", l: "Contactado", cls: "badge-amber" },
  { k: "qualified", l: "Qualificado", cls: "badge-blue" },
  { k: "won", l: "Ganho", cls: "badge-green" },
  { k: "lost", l: "Perdido", cls: "badge-red" },
];

const Leads = () => {
  const [leads, setLeads] = useState([]);
  const [newLead, setNewLead] = useState({ name: "", email: "", phone: "", company: "", stage: "new", score: 50, source: "manual", notes: "", tags: [] });
  const [show, setShow] = useState(false);

  const load = async () => setLeads((await api.get("/leads")).data);
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!newLead.name) return toast.error("Nome obrigatório");
    await api.post("/leads", newLead); setShow(false);
    setNewLead({ name: "", email: "", phone: "", company: "", stage: "new", score: 50, source: "manual", notes: "", tags: [] });
    load(); toast.success("Lead adicionado");
  };
  const updateStage = async (lead, stage) => { await api.put(`/leads/${lead.id}`, { ...lead, stage }); load(); };
  const del = async (id) => { await api.delete(`/leads/${id}`); load(); toast.success("Eliminado"); };
  const syncCrm = async (id) => { await api.post(`/leads/${id}/sync-crm`); load(); toast.success("Sincronizado com CRM"); };

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-display text-2xl font-bold">Leads</h1>
          <p className="text-sm text-[#5B6B82] mt-1">{leads.length} total · {leads.filter(l => l.stage === "won").length} ganhos</p>
        </div>
        <button data-testid="btn-new-lead" onClick={() => setShow(!show)} className="btn-primary">
          <Plus size={14} /> Novo lead
        </button>
      </div>

      {show && (
        <div className="card-surface p-5 mb-5 grid grid-cols-4 gap-3" data-testid="lead-form">
          {[["name", "Nome"], ["email", "Email"], ["phone", "Telefone"], ["company", "Empresa"]].map(([k, l]) => (
            <div key={k}>
              <label className="label">{l}</label>
              <input data-testid={`lead-${k}`} placeholder={l} value={newLead[k]}
                onChange={(e) => setNewLead({ ...newLead, [k]: e.target.value })} className="input-base" />
            </div>
          ))}
          <div>
            <label className="label">Estado</label>
            <select data-testid="lead-stage" value={newLead.stage} onChange={(e) => setNewLead({ ...newLead, stage: e.target.value })} className="input-base">
              {stages.map(s => <option key={s.k} value={s.k}>{s.l}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Score</label>
            <input data-testid="lead-score" type="number" min={0} max={100} value={newLead.score}
              onChange={(e) => setNewLead({ ...newLead, score: parseInt(e.target.value) || 0 })} className="input-base" />
          </div>
          <div className="col-span-2">
            <label className="label">Notas</label>
            <input data-testid="lead-notes" value={newLead.notes} onChange={(e) => setNewLead({ ...newLead, notes: e.target.value })} className="input-base" />
          </div>
          <div className="col-span-4 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setShow(false)}>Cancelar</button>
            <button data-testid="btn-save-lead" onClick={save} className="btn-primary">Guardar</button>
          </div>
        </div>
      )}

      <div className="card-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#E5EAF2] text-left text-[#5B6B82] text-[11px] uppercase tracking-wider font-semibold">
              <th className="p-4">Nome</th>
              <th className="p-4">Empresa</th>
              <th className="p-4">Email</th>
              <th className="p-4">Origem</th>
              <th className="p-4">Tags</th>
              <th className="p-4">Estado</th>
              <th className="p-4">Score</th>
              <th className="p-4">CRM</th>
              <th className="p-4">Criado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {leads.map(l => {
              const stage = stages.find(s => s.k === l.stage) || stages[0];
              return (
                <tr key={l.id} data-testid={`lead-row-${l.id}`} className="border-b border-[#E5EAF2] hover:bg-[#F7F9FC]">
                  <td className="p-4 font-semibold">{l.name}</td>
                  <td className="p-4">{l.company || "—"}</td>
                  <td className="p-4 text-[#5B6B82]">{l.email || "—"}</td>
                  <td className="p-4"><span className="badge badge-ghost">{l.source}</span></td>
                  <td className="p-4">
                    <div className="flex gap-1 flex-wrap">
                      {(l.tags || []).slice(0, 3).map(t => <span key={t} className="badge badge-blue">{t}</span>)}
                    </div>
                  </td>
                  <td className="p-4">
                    <select value={l.stage} onChange={(e) => updateStage(l, e.target.value)}
                      className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${stage.cls}`}>
                      {stages.map(s => <option key={s.k} value={s.k}>{s.l}</option>)}
                    </select>
                  </td>
                  <td className="p-4">
                    <div className="w-20 h-1.5 bg-[#E5EAF2] rounded-full overflow-hidden">
                      <div className="h-full bg-[#0069FE]" style={{ width: `${l.score}%` }} />
                    </div>
                    <span className="text-[10px] text-[#5B6B82]">{l.score}</span>
                  </td>
                  <td className="p-4">
                    {l.crm_synced
                      ? <span className="badge badge-green"><CheckCircle2 size={10} /> Sincronizado</span>
                      : <button data-testid={`btn-sync-${l.id}`} onClick={() => syncCrm(l.id)} className="text-[#0069FE] text-xs font-semibold hover:underline">Enviar</button>
                    }
                  </td>
                  <td className="p-4 text-[#5B6B82] text-xs">{new Date(l.created_at).toLocaleDateString("pt-PT")}</td>
                  <td className="p-4">
                    <button data-testid={`btn-delete-lead-${l.id}`} onClick={() => del(l.id)} className="text-[#5B6B82] hover:text-[#DC2626]">
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {leads.length === 0 && <div className="p-12 text-center text-sm text-[#5B6B82]">Sem leads. Os leads gerados por IA aparecem automaticamente aqui.</div>}
      </div>
    </div>
  );
};

export default Leads;
