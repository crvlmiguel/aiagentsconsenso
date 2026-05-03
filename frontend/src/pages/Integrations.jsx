import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  MessageSquare, Instagram, Send as TelegramIcon, Phone, Globe,
  Database, CircleDot,
} from "lucide-react";

const icons = {
  webchat: Globe,
  whatsapp: Phone,
  instagram: Instagram,
  telegram: TelegramIcon,
  messenger: MessageSquare,
  hubspot: Database, pipedrive: Database, salesforce: Database, webhook: Database,
};

const Integrations = () => {
  const [items, setItems] = useState([]);
  const load = async () => setItems((await api.get("/integrations")).data);
  useEffect(() => { load(); }, []);

  const toggle = async (it) => {
    const status = it.status === "connected" ? "disconnected" : "connected";
    await api.put(`/integrations/${it.id}`, { status });
    load();
    toast.success(`${it.name} ${status}`);
  };

  const channels = items.filter(i => i.category === "channel");
  const crms = items.filter(i => i.category === "crm");

  const Card = ({ it }) => {
    const Icon = icons[it.kind] || Database;
    return (
      <div data-testid={`integration-${it.kind}`} className="border border-zinc-800 p-4 bg-[#09090B] hover:bg-zinc-900/50 transition-colors">
        <div className="flex items-start justify-between">
          <div className="w-10 h-10 border border-zinc-800 flex items-center justify-center">
            <Icon size={18} className="text-[#FF5500]" />
          </div>
          <span className={`mono text-[10px] uppercase border px-2 py-0.5 flex items-center gap-1 ${
            it.status === "connected" ? "border-[#22C55E] text-[#22C55E]" : "border-zinc-700 text-zinc-500"
          }`}>
            <CircleDot size={8} /> {it.status}
          </span>
        </div>
        <div className="mt-4">
          <div className="font-bold">{it.name}</div>
          <div className="mono text-[10px] text-zinc-500 uppercase tracking-widest">{it.kind}</div>
        </div>
        <button
          data-testid={`btn-toggle-${it.kind}`}
          onClick={() => toggle(it)}
          className={`mt-4 w-full py-2 mono text-[10px] uppercase tracking-widest font-bold border transition-colors ${
            it.status === "connected"
              ? "border-zinc-700 hover:border-[#EF4444] hover:text-[#EF4444]"
              : "bg-white text-black border-white hover:bg-zinc-200"
          }`}
        >
          {it.status === "connected" ? "Disconnect" : "Connect"}
        </button>
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-8">
      <div>
        <h1 className="text-xl font-bold uppercase tracking-tight">Integrations</h1>
        <p className="text-sm text-zinc-500 mt-1">Connect channels and business systems.</p>
      </div>

      <section>
        <div className="label-mono mb-3">CHANNELS · {channels.length}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {channels.map(i => <Card key={i.id} it={i} />)}
        </div>
      </section>

      <section>
        <div className="label-mono mb-3">CRM & BUSINESS SYSTEMS · {crms.length}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {crms.map(i => <Card key={i.id} it={i} />)}
        </div>
      </section>
    </div>
  );
};

export default Integrations;
