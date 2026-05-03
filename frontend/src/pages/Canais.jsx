import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import {
  MessageSquare, Instagram, Send, Globe, Phone, Database, CircleDot, Mail,
  X, CheckCircle2, AlertTriangle, Copy, Clock,
} from "lucide-react";

const icons = {
  webchat: Globe, whatsapp: Phone, instagram: Instagram,
  telegram: Send, messenger: MessageSquare,
  hubspot: Database, pipedrive: Database, salesforce: Database, webhook: Database,
  smtp: Mail,
};

// Channel-specific field schema
const schema = {
  whatsapp: [
    { k: "access_token", label: "WhatsApp Cloud API Token", type: "password", placeholder: "EAA..." },
    { k: "phone_number_id", label: "Phone Number ID", type: "text", placeholder: "123456789" },
  ],
  instagram: [
    { k: "access_token", label: "Instagram Access Token", type: "password" },
    { k: "page_id", label: "Page ID", type: "text" },
  ],
  telegram: [
    { k: "bot_token", label: "Bot Token", type: "password", placeholder: "123456:ABC-DEF..." },
  ],
  messenger: [
    { k: "access_token", label: "Page Access Token", type: "password" },
    { k: "page_id", label: "Page ID", type: "text" },
  ],
  webchat: [],
  smtp: [
    { k: "host", label: "Servidor SMTP", type: "text", placeholder: "smtp.gmail.com" },
    { k: "port", label: "Porta", type: "number", placeholder: "587" },
    { k: "secure", label: "Segurança", type: "select", options: [["tls", "STARTTLS (porta 587)"], ["ssl", "SSL/TLS (porta 465)"], ["none", "Nenhuma"]] },
    { k: "username", label: "Utilizador", type: "text" },
    { k: "password", label: "Palavra-passe", type: "password" },
    { k: "from_email", label: "Email remetente", type: "email", placeholder: "naoresponder@empresa.pt" },
    { k: "notify_email", label: "Email para receber leads (opcional)", type: "email" },
  ],
};

const CRM_KINDS = ["hubspot", "pipedrive", "salesforce", "webhook"];

const ConfigDialog = ({ item, onClose, onSaved }) => {
  const fields = schema[item.kind] || [];
  const [cfg, setCfg] = useState(item.config || {});
  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [webchatActive, setWebchatActive] = useState(item.status === "connected");

  const save = async (nextStatus) => {
    setBusy(true);
    try {
      const body = { config: cfg };
      if (nextStatus) body.status = nextStatus;
      const { data } = await api.put(`/integrations/${item.id}`, body);
      toast.success("Guardado.");
      onSaved(data);
      if (nextStatus) onClose();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falha");
    } finally { setBusy(false); }
  };

  const testEmail = async () => {
    setTesting(true);
    try {
      // save first
      await api.put(`/integrations/${item.id}`, { config: cfg });
      const { data } = await api.post(`/integrations/${item.id}/test-email`, { to: cfg.notify_email || cfg.from_email });
      data.ok ? toast.success("Email de teste enviado!") : toast.error(data.error || "Falha");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Falha a enviar");
    } finally { setTesting(false); }
  };

  const webchatSnippet = `<iframe
  src="${process.env.REACT_APP_BACKEND_URL}/api/widget/${item.tenant_id || ""}?api=${encodeURIComponent(process.env.REACT_APP_BACKEND_URL + "/api")}&tenant=${item.tenant_id || ""}"
  style="position:fixed;bottom:20px;right:20px;width:420px;height:620px;border:0;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.15);z-index:9999"
  title="Chat"
></iframe>`;

  return (
    <div className="fixed inset-0 bg-black/30 z-50 flex items-center justify-center p-6" data-testid={`config-dialog-${item.kind}`}>
      <div className="bg-white w-full max-w-lg rounded-2xl border border-[#E5EAF2] max-h-[90vh] flex flex-col">
        <div className="p-5 border-b border-[#E5EAF2] flex items-start justify-between">
          <div>
            <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Configuração</div>
            <div className="font-display text-lg font-bold">{item.name}</div>
          </div>
          <button data-testid="btn-close-config" onClick={onClose} className="btn-ghost p-2"><X size={14} /></button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {item.kind === "webchat" && (
            <>
              <div>
                <div className="label">Ativação do widget</div>
                <label className="flex items-center gap-2 mt-1">
                  <input data-testid="webchat-active" type="checkbox" checked={webchatActive} onChange={(e) => setWebchatActive(e.target.checked)} className="accent-[#0069FE]" />
                  <span className="text-sm">Widget ativo no seu site</span>
                </label>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <div className="label">Código de incorporação</div>
                  <button data-testid="btn-copy-webchat" onClick={() => { navigator.clipboard.writeText(webchatSnippet); toast.success("Copiado"); }} className="btn-ghost text-[11px] py-1">
                    <Copy size={10} /> Copiar
                  </button>
                </div>
                <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-3 text-[11px] overflow-x-auto whitespace-pre-wrap">{webchatSnippet}</pre>
              </div>
            </>
          )}

          {fields.map(f => (
            <div key={f.k}>
              <label className="label">{f.label}</label>
              {f.type === "select" ? (
                <select data-testid={`cfg-${f.k}`} value={cfg[f.k] || f.options[0][0]} onChange={(e) => setCfg({ ...cfg, [f.k]: e.target.value })} className="input-base">
                  {f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              ) : (
                <input data-testid={`cfg-${f.k}`} type={f.type} value={cfg[f.k] || ""}
                  onChange={(e) => setCfg({ ...cfg, [f.k]: e.target.value })}
                  placeholder={f.placeholder || ""} className="input-base" />
              )}
            </div>
          ))}

          {item.kind === "whatsapp" && (
            <div className="bg-[#EAF2FF] border border-[#C7DDFF] rounded-lg p-3 text-xs">
              <div className="font-semibold text-[#0069FE] mb-1">Webhook URL</div>
              <code className="block break-all text-[11px]">{process.env.REACT_APP_BACKEND_URL}/api/webhooks/whatsapp/{item.tenant_id || "<tenant_id>"}</code>
              <div className="text-[#5B6B82] mt-1">Configure este URL no Meta Business Manager.</div>
            </div>
          )}
          {item.kind === "telegram" && (
            <div className="bg-[#EAF2FF] border border-[#C7DDFF] rounded-lg p-3 text-xs">
              <div className="font-semibold text-[#0069FE] mb-1">Webhook URL</div>
              <code className="block break-all text-[11px]">{process.env.REACT_APP_BACKEND_URL}/api/webhooks/telegram/{item.tenant_id || "<tenant_id>"}</code>
              <div className="text-[#5B6B82] mt-1">Chame setWebhook na Bot API com este URL.</div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-[#E5EAF2] flex gap-2 justify-end">
          <button className="btn-ghost" onClick={onClose}>Cancelar</button>
          {item.kind === "smtp" && (
            <button data-testid="btn-test-email" onClick={testEmail} disabled={testing} className="btn-ghost">
              {testing ? "A enviar…" : "Enviar email de teste"}
            </button>
          )}
          <button data-testid="btn-save-config" onClick={() => save(null)} disabled={busy} className="btn-ghost">
            Guardar
          </button>
          <button data-testid="btn-connect" onClick={() => save(webchatActive || item.kind !== "webchat" ? "connected" : "disconnected")}
            disabled={busy} className="btn-primary">
            {item.kind === "webchat" ? (webchatActive ? "Ativar widget" : "Desativar") : "Ligar"}
          </button>
        </div>
      </div>
    </div>
  );
};

const Canais = () => {
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null);
  const load = async () => setItems((await api.get("/integrations")).data);
  useEffect(() => { load(); }, []);

  const disconnect = async (it) => {
    await api.put(`/integrations/${it.id}`, { status: "disconnected" });
    load(); toast.success(`${it.name} desligado`);
  };

  const byCat = { channel: [], crm: [], email: [] };
  items.forEach(i => (byCat[i.category] || byCat.channel).push(i));

  const Card = ({ it }) => {
    const Icon = icons[it.kind] || Database;
    const on = it.status === "connected";
    const comingSoon = CRM_KINDS.includes(it.kind);
    return (
      <div data-testid={`integration-${it.kind}`}
        className={`card-surface p-5 transition-all ${comingSoon ? "opacity-75" : "hover:shadow-md"}`}>
        <div className="flex items-start justify-between">
          <div className="w-11 h-11 rounded-xl bg-[#EAF2FF] text-[#0069FE] flex items-center justify-center">
            <Icon size={18} />
          </div>
          {comingSoon ? (
            <span className="badge badge-amber"><Clock size={9} /> Em breve</span>
          ) : (
            <span className={`badge ${on ? "badge-green" : "badge-ghost"}`}>
              <CircleDot size={8} /> {on ? "Ligado" : "Desligado"}
            </span>
          )}
        </div>
        <div className="mt-4">
          <div className="font-semibold">{it.name}</div>
          <div className="text-xs text-[#5B6B82] uppercase tracking-wider font-semibold mt-0.5">{it.kind}</div>
        </div>
        <div className="flex gap-2 mt-4">
          {comingSoon ? (
            <button disabled data-testid={`btn-coming-${it.kind}`}
              className="w-full py-2.5 text-sm font-semibold rounded-lg border border-[#E5EAF2] bg-[#F7F9FC] text-[#5B6B82] cursor-not-allowed">
              Em breve
            </button>
          ) : (
            <>
              <button data-testid={`btn-configure-${it.kind}`} onClick={() => setEditing(it)}
                className="flex-1 py-2.5 text-sm font-semibold rounded-lg border border-[#E5EAF2] hover:bg-[#F7F9FC]">
                Configurar
              </button>
              {on && it.kind !== "webchat" && (
                <button data-testid={`btn-disconnect-${it.kind}`} onClick={() => disconnect(it)}
                  className="py-2.5 px-3 text-sm font-semibold rounded-lg border border-[#E5EAF2] text-[#DC2626] hover:bg-[#FEF2F2]">
                  Desligar
                </button>
              )}
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-8 space-y-8" data-testid="canais-page">
      <div>
        <h1 className="font-display text-2xl font-bold">Canais & CRM</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Configure cada canal antes de o ativar. Nenhum canal fica ativo sem configuração.</p>
      </div>

      <section>
        <div className="text-sm font-semibold text-[#2C3A52] mb-3 uppercase tracking-wider">Canais · {byCat.channel.length}</div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {byCat.channel.map(i => <Card key={i.id} it={i} />)}
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

      <section>
        <div className="text-sm font-semibold text-[#2C3A52] mb-3 uppercase tracking-wider">CRMs</div>
        <div className="bg-[#FFF4E1] border border-[#F4DCB0] rounded-xl p-4 mb-4 flex items-start gap-3">
          <AlertTriangle size={16} className="text-[#D97706] mt-0.5" />
          <div className="text-sm">
            <div className="font-semibold text-[#92450C]">Integrações CRM em breve</div>
            <div className="text-[#5B6B82] text-xs mt-0.5">HubSpot, Pipedrive e Salesforce estão em desenvolvimento. Entretanto, pode usar o Webhook genérico ou receber leads por email.</div>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
          {byCat.crm.map(i => <Card key={i.id} it={i} />)}
        </div>
      </section>

      {editing && <ConfigDialog item={editing} onClose={() => setEditing(null)} onSaved={load} />}
    </div>
  );
};

export default Canais;
