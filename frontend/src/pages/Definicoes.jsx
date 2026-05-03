import React, { useState } from "react";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { Copy } from "lucide-react";

const Definicoes = () => {
  const { user, tenant } = useAuth();
  const [copied, setCopied] = useState("");
  const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

  const copy = (k, t) => {
    navigator.clipboard.writeText(t); setCopied(k); toast.success("Copiado");
    setTimeout(() => setCopied(""), 1500);
  };

  return (
    <div className="h-full overflow-y-auto p-8 space-y-6" data-testid="definicoes-page">
      <div>
        <h1 className="font-display text-2xl font-bold">Definições</h1>
        <p className="text-sm text-[#5B6B82] mt-1">Dados da organização. A instalação do widget está dentro de cada agente.</p>
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
        <div className="flex justify-between items-center mb-3">
          <div className="font-display font-semibold">Endpoint de entrada Web Chat</div>
          <button data-testid="btn-copy-endpoint" onClick={() => copy("ep", `${API}/webchat/${tenant?.id}/message`)} className="btn-ghost text-[13px]">
            <Copy size={12} /> {copied === "ep" ? "Copiado" : "Copiar"}
          </button>
        </div>
        <pre className="bg-[#F7F9FC] border border-[#E5EAF2] rounded-lg p-4 text-xs overflow-x-auto">{`POST ${API}/webchat/${tenant?.id}/message
Content-Type: application/json

{"channel":"webchat","external_user_id":"user-123","contact_name":"Ana","text":"Olá!","agent_id":"<agent_id>"}`}</pre>
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
