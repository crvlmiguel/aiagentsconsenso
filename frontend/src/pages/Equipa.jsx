import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { UserPlus, Trash2 } from "lucide-react";

const roles = { owner: "Proprietário", admin: "Admin", agent: "Agente" };

const Equipa = () => {
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState({ email: "", name: "", role: "agent", password: "changeme123" });
  const [show, setShow] = useState(false);

  const load = async () => setTeam((await api.get("/team")).data);
  useEffect(() => { load(); }, []);

  const invite = async () => {
    if (!form.email || !form.name) return toast.error("Preencha nome e email");
    try {
      await api.post("/team/invite", form); toast.success("Membro adicionado");
      setForm({ email: "", name: "", role: "agent", password: "changeme123" }); setShow(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Falha"); }
  };
  const del = async (id) => { await api.delete(`/team/${id}`); load(); toast.success("Removido"); };

  return (
    <div className="h-full overflow-y-auto p-8">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-display text-2xl font-bold">Equipa</h1>
          <p className="text-sm text-[#5B6B82] mt-1">{team.length} membros</p>
        </div>
        <button data-testid="btn-invite-member" onClick={() => setShow(!show)} className="btn-primary">
          <UserPlus size={14} /> Adicionar
        </button>
      </div>

      {show && (
        <div className="card-surface p-5 mb-5 grid grid-cols-4 gap-3" data-testid="invite-form">
          <div><label className="label">Nome</label><input data-testid="invite-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-base" /></div>
          <div><label className="label">Email</label><input data-testid="invite-email" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="input-base" /></div>
          <div><label className="label">Função</label>
            <select data-testid="invite-role" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="input-base">
              <option value="agent">Agente</option><option value="admin">Admin</option>
            </select>
          </div>
          <div><label className="label">Palavra-passe</label>
            <input data-testid="invite-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="input-base" />
          </div>
          <div className="col-span-4 flex justify-end gap-2">
            <button className="btn-ghost" onClick={() => setShow(false)}>Cancelar</button>
            <button data-testid="btn-send-invite" onClick={invite} className="btn-primary">Adicionar</button>
          </div>
        </div>
      )}

      <div className="card-surface overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#E5EAF2] text-left text-[#5B6B82] text-[11px] uppercase tracking-wider font-semibold">
              <th className="p-4">Nome</th><th className="p-4">Email</th><th className="p-4">Função</th><th className="p-4">Juntou-se</th><th></th>
            </tr>
          </thead>
          <tbody>
            {team.map(m => (
              <tr key={m.id} className="border-b border-[#E5EAF2] hover:bg-[#F7F9FC]">
                <td className="p-4">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-[#EAF2FF] text-[#0069FE] font-bold text-xs flex items-center justify-center">
                      {m.name.slice(0, 2).toUpperCase()}
                    </div>
                    <span className="font-semibold">{m.name}</span>
                  </div>
                </td>
                <td className="p-4 text-[#5B6B82]">{m.email}</td>
                <td className="p-4"><span className="badge badge-blue">{roles[m.role] || m.role}</span></td>
                <td className="p-4 text-[#5B6B82] text-xs">{new Date(m.created_at).toLocaleDateString("pt-PT")}</td>
                <td className="p-4">
                  <button data-testid={`btn-remove-${m.id}`} onClick={() => del(m.id)} className="text-[#5B6B82] hover:text-[#DC2626]">
                    <Trash2 size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Equipa;
