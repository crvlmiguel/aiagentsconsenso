import React, { useState } from "react";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { Copy, ExternalLink } from "lucide-react";

const Definicoes = () => {
  const { user, tenant } = useAuth();
  const [copied, setCopied] = useState("");

  const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
  const widgetPageUrl = `${process.env.REACT_APP_BACKEND_URL}/api/widget/${tenant?.id}?api=${encodeURIComponent(API)}&tenant=${tenant?.id}`;
  const scriptSnippet = `<!-- Widget Consenso+ -->
<script src="${process.env.REACT_APP_BACKEND_URL}/api/widget.js"
  data-tenant-id="${tenant?.id}"
  defer></script>`;
  const iframeSnippet = `<iframe
  src="${widgetPageUrl}"
  style="position:fixed;bottom:20px;right:20px;width:420px;height:620px;border:0;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.15);z-index:9999"
  title="Chat"
></iframe>`;

  const copy = (k, t) => {
    navigator.clipboard.writeText(t); setCopied(k); toast.success("Copiado");
    setTimeout(() => setCopied(""), 1500);
  };

  return (
    <div className="h-full overflow-y-auto p-8 space-y-6" data-testid="definicoes-page">
      <div>
        <h1 className="font-display text-2xl font-bold">Definições</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Organização, API e instalação do widget.</p>
      </div>

      <section className="card-surface p-6">
        <div className="font-display font-semibold">Organização</div>
        <div className="grid grid-cols-2 gap-4 mt-3 text-sm">
          <div><div className="label">Tenant ID</div><div className="font-mono text-xs">{tenant?.id}</div></div>
          <div><div className="label">Plano</div><div>{tenant?.plan}</div></div>
          <div><div className="label">Proprietário</div><div>{user?.name} · {user?.email}</div></div>
          <div><div className="label">Slug</div><div>{tenant?.slug}</div></div>
        </div>
      </section>

      <section className="card-surface p-6">
        <div className="flex justify-between items-center">
          <div>
            <div className="font-display font-semibold">Widget de chat ao vivo</div>
            <p className="text-xs text-[#5B6B82] mt-0.5">Abra a página do widget num separador ou incorpore no seu site.</p>
          </div>
          <a href={widgetPageUrl} target="_blank" rel="noreferrer" data-testid="btn-open-widget" className="btn-ghost text-[13px]">
            <ExternalLink size={13} /> Abrir widget
          </a>
        </div>
      </section>

      <section className="card-surface p-6">
        <div className="flex justify-between items-center mb-3">
          <div>
            <div className="font-display font-semibold">Script de incorporação (recomendado)</div>
            <p className="text-xs text-[#5B6B82] mt-0.5">Cola no HTML do teu site. Cria botão flutuante + chat automaticamente.</p>
          </div>
          <button data-testid="btn-copy-script" onClick={() => copy("script", scriptSnippet)} className="btn-ghost text-[13px]">
            <Copy size={12} /> {copied === "script" ? "Copiado" : "Copiar"}
          </button>
        </div>
        <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 text-xs overflow-x-auto whitespace-pre-wrap">{scriptSnippet}</pre>
      </section>

      <section className="card-surface p-6">
        <div className="flex justify-between items-center mb-3">
          <div>
            <div className="font-display font-semibold">Iframe (alternativa)</div>
            <p className="text-xs text-[#5B6B82] mt-0.5">Incorporação direta sem botão flutuante.</p>
          </div>
          <button data-testid="btn-copy-snippet" onClick={() => copy("snip", iframeSnippet)} className="btn-ghost text-[13px]">
            <Copy size={12} /> {copied === "snip" ? "Copiado" : "Copiar"}
          </button>
        </div>
        <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 text-xs overflow-x-auto whitespace-pre-wrap">{iframeSnippet}</pre>
      </section>

      <section className="card-surface p-6">
        <div className="flex justify-between items-center mb-3">
          <div className="font-display font-semibold">Endpoint de entrada Web Chat</div>
          <button data-testid="btn-copy-endpoint" onClick={() => copy("ep", `${API}/webchat/${tenant?.id}/message`)} className="btn-ghost text-[13px]">
            <Copy size={12} /> {copied === "ep" ? "Copiado" : "Copiar"}
          </button>
        </div>
        <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 text-xs overflow-x-auto">{`POST ${API}/webchat/${tenant?.id}/message
Content-Type: application/json

{"channel":"webchat","external_user_id":"user-123","contact_name":"Ana","text":"Olá!"}`}</pre>
      </section>

      <section className="card-surface p-6">
        <div className="font-display font-semibold mb-3">Modelos de IA disponíveis</div>
        <div className="grid grid-cols-3 gap-3">
          {[
            { name: "OpenAI GPT-5.1", task: "raciocínio complexo", tag: "badge-blue" },
            { name: "Claude Sonnet 4.5", task: "contexto longo", tag: "badge-amber" },
            { name: "Gemini 2.5 Flash", task: "rápido / simples", tag: "badge-green" },
          ].map(m => (
            <div key={m.name} className="border border-[#E5EAF2] rounded-xl p-4">
              <span className={`badge ${m.tag}`}>{m.task}</span>
              <div className="font-semibold mt-2">{m.name}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default Definicoes;
