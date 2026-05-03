import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { UserPlus, Trash2 } from "lucide-react";

const Team = () => {
  const [team, setTeam] = useState([]);
  const [form, setForm] = useState({ email: "", name: "", role: "agent", password: "changeme123" });
  const [show, setShow] = useState(false);

  const load = async () => setTeam((await api.get("/team")).data);
  useEffect(() => { load(); }, []);

  const invite = async () => {
    if (!form.email || !form.name) return toast.error("Fill email + name");
    try {
      await api.post("/team/invite", form);
      toast.success("Member added");
      setForm({ email: "", name: "", role: "agent", password: "changeme123" });
      setShow(false); load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); }
  };

  const del = async (id) => { await api.delete(`/team/${id}`); load(); toast.success("Removed"); };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold uppercase tracking-tight">Team</h1>
          <div className="mono text-[10px] text-zinc-500 uppercase tracking-widest">
            {team.length} MEMBERS
          </div>
        </div>
        <button data-testid="btn-invite-member" onClick={() => setShow(!show)}
          className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-3 py-2 flex items-center gap-1">
          <UserPlus size={12} /> Add Member
        </button>
      </div>

      {show && (
        <div className="border border-zinc-800 p-4 grid grid-cols-5 gap-2" data-testid="invite-form">
          <input data-testid="invite-name" placeholder="Name" value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs" />
          <input data-testid="invite-email" placeholder="Email" value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs" />
          <select data-testid="invite-role" value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs mono uppercase">
            <option value="agent">AGENT</option>
            <option value="admin">ADMIN</option>
          </select>
          <input data-testid="invite-password" placeholder="Password" type="text" value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="bg-[#18181B] border border-zinc-800 px-2 py-1.5 text-xs" />
          <button data-testid="btn-send-invite" onClick={invite}
            className="bg-white text-black mono text-xs uppercase tracking-widest font-bold hover:bg-zinc-200">Add</button>
        </div>
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 text-zinc-500 uppercase tracking-widest text-[10px] text-left mono">
            <th className="p-3">Name</th>
            <th className="p-3">Email</th>
            <th className="p-3">Role</th>
            <th className="p-3">Joined</th>
            <th></th>
          </tr>
        </thead>
        <tbody className="mono text-xs">
          {team.map(m => (
            <tr key={m.id} className="border-b border-zinc-800 hover:bg-zinc-900/50">
              <td className="p-3 text-white font-semibold">{m.name}</td>
              <td className="p-3">{m.email}</td>
              <td className="p-3 uppercase text-[#FF5500]">{m.role}</td>
              <td className="p-3 text-zinc-500">{new Date(m.created_at).toLocaleDateString()}</td>
              <td className="p-3">
                <button data-testid={`btn-remove-${m.id}`} onClick={() => del(m.id)} className="text-zinc-500 hover:text-[#EF4444]">
                  <Trash2 size={12} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Team;
