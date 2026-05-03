import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { MessageSquare, Instagram, Send, Globe, Phone, Database, CircleDot, Mail } from "lucide-react";

const icons = {
  webchat: Globe, whatsapp: Phone, instagram: Instagram,
  telegram: Send, messenger: MessageSquare,
  hubspot: Database, pipedrive: Database, salesforce: Database, webhook: Database,
  smtp: Mail, sendgrid: Mail,
};

const Canais = () => {
  const [items, setItems] = useState([]);
  const load = async () => setItems((await api.get("/integrations")).data);
  useEffect(() => { load(); }, []);

  const toggle = async (it) => {
    const status = it.status === "connected" ? "disconnected" : "connected";
    await api.put(`/integrations/${it.id}`, { status }); load();
    toast.success(`${it.name}: ${status === "connected" ? "ligado" : "desligado"}`);
  };

  const byCat = { channel: [], crm: [], email: [] };
  items.forEach(i => (byCat[i.category] || byCat.channel).push(i));

  const Card = ({ it }) => {
    const Icon = icons[it.kind] || Database;
    const on = it.status === "connected";
    return (
      <div data-testid={`integration-${it.kind}`} className="card-surface p-5 transition-all hover:shadow-md">
        <div className="flex items-start justify-between">
          <div className="w-11 h-11 rounded-xl bg-[#EAF2FF] text-[#0069FE] flex items-center justify-center">
            <Icon size={18} />
          </div>
          <span className={`badge ${on ? "badge-green" : "badge-ghost"}`}>
            <CircleDot size={8} /> {on ? "Ligado" : "Desligado"}
          </span>
        </div>
        <div className="mt-4">
          <div className="font-semibold">{it.name}</div>
          <div className="text-xs text-[#5B6B82] uppercase tracking-wider font-semibold mt-0.5">{it.kind}</div>
        </div>
        <button data-testid={`btn-toggle-${it.kind}`} onClick={() => toggle(it)}
          className={`mt-4 w-full py-2.5 text-sm font-semibold rounded-lg transition-colors ${
            on ? "border border-[#E5EAF2] bg-white text-[#DC2626] hover:bg-[#FEF2F2]"
               : "bg-[#0069FE] text-white hover:bg-[#0057D5]"
          }`}>
          {on ? "Desligar" : "Ligar"}
        </button>
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-8 space-y-8" data-testid="canais-page">
      <div>
        <h1 className="font-display text-2xl font-bold">Canais & CRM</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Ligue canais de comunicação e sistemas de negócio.</p>
      </div>

      <section>
        <div className="text-sm font-semibold text-[#2C3A52] mb-3 uppercase tracking-wider">Canais de comunicação · {byCat.channel.length}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {byCat.channel.map(i => <Card key={i.id} it={i} />)}
        </div>
      </section>

      <section>
        <div className="text-sm font-semibold text-[#2C3A52] mb-3 uppercase tracking-wider">CRMs · {byCat.crm.length}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {byCat.crm.map(i => <Card key={i.id} it={i} />)}
        </div>
      </section>

      {byCat.email.length > 0 && (
        <section>
          <div className="text-sm font-semibold text-[#2C3A52] mb-3 uppercase tracking-wider">Email · {byCat.email.length}</div>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
            {byCat.email.map(i => <Card key={i.id} it={i} />)}
          </div>
        </section>
      )}
    </div>
  );
};

export default Canais;
