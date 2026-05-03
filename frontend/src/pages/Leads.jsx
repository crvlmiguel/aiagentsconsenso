import React, { useEffect, useState, useMemo } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2, CheckCircle2, Download, Search } from "lucide-react";

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
  const [query, setQuery] = useState("");
  const [stageFilter, setStageFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");

  const load = async () => setLeads((await api.get("/leads")).data);
  useEffect(() => { load(); }, []);

  const sources = useMemo(() => Array.from(new Set(leads.map(l => l.source).filter(Boolean))), [leads]);

  const filtered = useMemo(() => leads.filter(l => {
    if (stageFilter !== "all" && l.stage !== stageFilter) return false;
    if (sourceFilter !== "all" && l.source !== sourceFilter) return false;
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return [l.name, l.email, l.phone, l.company, l.notes, ...(l.tags || [])]
      .some(v => (v || "").toLowerCase().includes(q));
  }), [leads, query, stageFilter, sourceFilter]);

  const exportCsv = () => {
    if (filtered.length === 0) { toast.error("Nenhum lead para exportar"); return; }
    const fields = ["name", "email", "phone", "company", "stage", "score", "source", "tags", "notes", "created_at"];
    const escape = (v) => {
      if (v === null || v === undefined) return "";
      const s = Array.isArray(v) ? v.join("; ") : String(v);
      return /[",\n;]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const header = ["Nome", "Email", "Telefone", "Empresa", "Estado", "Score", "Origem", "Tags", "Notas", "Criado em"];
    const rows = filtered.map(l => fields.map(f => escape(l[f])).join(","));
    const csv = "\ufeff" + [header.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `leads-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`${filtered.length} leads exportados`);
  };

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
    <div className="h-full overflow-y-auto p-4 md:p-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 md:mb-5 gap-3">
        <div>
          <h1 className="font-display text-xl md:text-2xl font-bold">Leads</h1>
          <p className="text-xs md:text-sm text-[#5B6B82] mt-1">
            {leads.length} total · {leads.filter(l => l.stage === "won").length} ganhos
            {filtered.length !== leads.length && ` · ${filtered.length} filtrados`}
          </p>
        </div>
        <div className="flex gap-2">
          <button data-testid="btn-export-csv" onClick={exportCsv} className="btn-ghost flex-1 sm:flex-initial justify-center">
            <Download size={14} /> <span className="hidden sm:inline">Exportar CSV</span><span className="sm:hidden">CSV</span>
          </button>
          <button data-testid="btn-new-lead" onClick={() => setShow(!show)} className="btn-primary flex-1 sm:flex-initial justify-center">
            <Plus size={14} /> Novo lead
          </button>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 md:gap-3 mb-4 md:mb-5">
        <div className="relative flex-1 sm:max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#5B6B82] pointer-events-none" />
          <input data-testid="leads-search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder="Pesquisar por nome, email…"
            className="input-base pl-9 text-sm" />
        </div>
        <div className="flex gap-2">
          <select data-testid="leads-filter-stage" value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}
            className="input-base text-sm flex-1 sm:flex-initial">
            <option value="all">Todos estados</option>
            {stages.map(s => <option key={s.k} value={s.k}>{s.l}</option>)}
          </select>
          <select data-testid="leads-filter-source" value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)}
            className="input-base text-sm flex-1 sm:flex-initial">
            <option value="all">Todas origens</option>
            {sources.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
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

      <div className="card-surface overflow-x-auto">
        <table className="w-full text-sm min-w-[900px]">
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
            {filtered.map(l => {
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
        {filtered.length === 0 && (
          <div className="p-12 text-center text-sm text-[#5B6B82]">
            {leads.length === 0
              ? "Sem leads. Os leads gerados por IA aparecem automaticamente aqui."
              : "Nenhum lead corresponde aos filtros."}
          </div>
        )}
      </div>
    </div>
  );
};

export default Leads;
