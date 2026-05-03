import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const stages = ["new", "contacted", "qualified", "won", "lost"];
const stageColor = {
  new: "border-white text-white",
  contacted: "border-[#EAB308] text-[#EAB308]",
  qualified: "border-[#FF5500] text-[#FF5500]",
  won: "border-[#22C55E] text-[#22C55E]",
  lost: "border-[#EF4444] text-[#EF4444]",
};

const Leads = () => {
  const [leads, setLeads] = useState([]);
  const [newLead, setNewLead] = useState({ name: "", email: "", phone: "", company: "", stage: "new", score: 50, source: "manual", notes: "" });
  const [showForm, setShowForm] = useState(false);

  const load = async () => setLeads((await api.get("/leads")).data);
  useEffect(() => { load(); }, []);

  const save = async () => {
    if (!newLead.name) return toast.error("Name required");
    await api.post("/leads", newLead);
    setShowForm(false);
    setNewLead({ name: "", email: "", phone: "", company: "", stage: "new", score: 50, source: "manual", notes: "" });
    load();
    toast.success("Lead added");
  };

  const updateStage = async (lead, stage) => {
    await api.put(`/leads/${lead.id}`, { ...lead, stage });
    load();
  };
  const del = async (id) => {
    await api.delete(`/leads/${id}`); load(); toast.success("Deleted");
  };

  return (
    <div className="h-full flex flex-col">
      <div className="border-b border-zinc-800 p-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold uppercase tracking-tight">Leads</h1>
          <div className="mono text-[10px] text-zinc-500 uppercase tracking-widest">
            {leads.length} TOTAL · {leads.filter(l => l.stage === "won").length} WON
          </div>
        </div>
        <button
          data-testid="btn-new-lead"
          onClick={() => setShowForm(!showForm)}
          className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-3 py-2 flex items-center gap-1"
        ><Plus size={12} /> New Lead</button>
      </div>

      {showForm && (
        <div className="border-b border-zinc-800 p-4 grid grid-cols-4 gap-2" data-testid="lead-form">
          {["name", "email", "phone", "company"].map(f => (
            <input
              key={f} data-testid={`lead-${f}`} placeholder={f}
              value={newLead[f]} onChange={(e) => setNewLead({ ...newLead, [f]: e.target.value })}
              className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs mono focus:border-white outline-none"
            />
          ))}
          <select
            data-testid="lead-stage"
            value={newLead.stage} onChange={(e) => setNewLead({ ...newLead, stage: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs mono uppercase"
          >
            {stages.map(s => <option key={s}>{s}</option>)}
          </select>
          <input data-testid="lead-score" type="number" placeholder="score" value={newLead.score}
            onChange={(e) => setNewLead({ ...newLead, score: parseInt(e.target.value) || 0 })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs mono" />
          <input data-testid="lead-notes" placeholder="notes" value={newLead.notes}
            onChange={(e) => setNewLead({ ...newLead, notes: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs col-span-2" />
          <button data-testid="btn-save-lead" onClick={save}
            className="bg-white text-black mono text-xs uppercase tracking-widest font-bold hover:bg-zinc-200">Save</button>
        </div>
      )}

      <div className="flex-1 overflow-y-auto">
        <table className="w-full mono text-xs">
          <thead className="border-b border-zinc-800 sticky top-0 bg-[#09090B]">
            <tr className="text-left text-zinc-500 uppercase tracking-widest text-[10px]">
              <th className="p-3">Name</th>
              <th className="p-3">Company</th>
              <th className="p-3">Email</th>
              <th className="p-3">Source</th>
              <th className="p-3">Stage</th>
              <th className="p-3">Score</th>
              <th className="p-3">Created</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {leads.map(l => (
              <tr key={l.id} className="border-b border-zinc-800 hover:bg-zinc-900/50" data-testid={`lead-row-${l.id}`}>
                <td className="p-3 text-white font-semibold">{l.name}</td>
                <td className="p-3">{l.company || "—"}</td>
                <td className="p-3">{l.email || "—"}</td>
                <td className="p-3 uppercase text-zinc-400">{l.source}</td>
                <td className="p-3">
                  <select value={l.stage} onChange={(e) => updateStage(l, e.target.value)}
                    className={`bg-transparent border px-2 py-0.5 uppercase text-[10px] ${stageColor[l.stage]}`}>
                    {stages.map(s => <option key={s} value={s} className="bg-[#09090B]">{s}</option>)}
                  </select>
                </td>
                <td className="p-3">
                  <div className="w-20 h-1 bg-zinc-900 border border-zinc-800">
                    <div className="h-full bg-[#FF5500]" style={{ width: `${l.score}%` }}></div>
                  </div>
                  <span className="text-[10px] text-zinc-500">{l.score}</span>
                </td>
                <td className="p-3 text-zinc-500">{new Date(l.created_at).toLocaleDateString()}</td>
                <td className="p-3">
                  <button data-testid={`btn-delete-lead-${l.id}`} onClick={() => del(l.id)} className="text-zinc-500 hover:text-[#EF4444]">
                    <Trash2 size={12} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {leads.length === 0 && (
          <div className="p-8 text-center text-zinc-500 mono text-xs uppercase tracking-widest">
            No leads yet. AI-created leads will appear here automatically.
          </div>
        )}
      </div>
    </div>
  );
};

export default Leads;
