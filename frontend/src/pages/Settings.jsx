import React, { useState } from "react";
import { useAuth } from "../lib/auth";
import { toast } from "sonner";
import { Copy } from "lucide-react";

const Settings = () => {
  const { user, tenant } = useAuth();
  const [copied, setCopied] = useState(false);

  const widgetUrl = `${process.env.REACT_APP_BACKEND_URL}/api/webchat/${tenant?.id}/message`;
  const snippet = `<!-- Consenso Plus Web Chat -->
<script>
  window.__CP_TENANT = "${tenant?.id}";
  window.__CP_API = "${process.env.REACT_APP_BACKEND_URL}/api";
  // fetch('${widgetUrl}', { method:'POST', body: JSON.stringify({
  //   external_user_id: 'visitor-123',
  //   contact_name: 'Visitor',
  //   text: 'Hi!'
  // })});
</script>`;

  const copy = (t) => {
    navigator.clipboard.writeText(t);
    setCopied(true); toast.success("Copied");
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="h-full overflow-y-auto p-6 space-y-6" data-testid="settings-page">
      <div>
        <h1 className="text-xl font-bold uppercase tracking-tight">Settings</h1>
        <p className="text-sm text-zinc-500 mt-1">Workspace, API and webchat setup.</p>
      </div>

      <section className="border border-zinc-800 p-4">
        <div className="label-mono">WORKSPACE</div>
        <div className="grid grid-cols-2 gap-4 mt-2 mono text-xs">
          <div><div className="text-zinc-500 uppercase">Tenant ID</div><div className="mt-1">{tenant?.id}</div></div>
          <div><div className="text-zinc-500 uppercase">Plan</div><div className="mt-1">{tenant?.plan?.toUpperCase()}</div></div>
          <div><div className="text-zinc-500 uppercase">Owner</div><div className="mt-1">{user?.name} · {user?.email}</div></div>
          <div><div className="text-zinc-500 uppercase">Slug</div><div className="mt-1">{tenant?.slug}</div></div>
        </div>
      </section>

      <section className="border border-zinc-800 p-4">
        <div className="flex justify-between items-center">
          <div className="label-mono">WEB CHAT ENDPOINT</div>
          <button data-testid="btn-copy-endpoint" onClick={() => copy(widgetUrl)}
            className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-2 py-1 flex items-center gap-1">
            <Copy size={10} /> {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <pre className="mt-2 bg-[#18181B] border border-zinc-800 p-3 text-xs mono overflow-x-auto">{widgetUrl}</pre>
      </section>

      <section className="border border-zinc-800 p-4">
        <div className="flex justify-between items-center">
          <div className="label-mono">EMBED SNIPPET</div>
          <button data-testid="btn-copy-snippet" onClick={() => copy(snippet)}
            className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-2 py-1 flex items-center gap-1">
            <Copy size={10} /> Copy
          </button>
        </div>
        <pre className="mt-2 bg-[#18181B] border border-zinc-800 p-3 text-xs mono overflow-x-auto whitespace-pre-wrap">{snippet}</pre>
      </section>

      <section className="border border-zinc-800 p-4">
        <div className="label-mono">AI MODELS AVAILABLE</div>
        <div className="grid grid-cols-3 gap-3 mt-3 mono text-xs">
          {[
            { name: "OPENAI GPT", task: "complex reasoning", color: "text-[#22C55E]" },
            { name: "CLAUDE SONNET 4.5", task: "long context", color: "text-[#FF5500]" },
            { name: "GEMINI FLASH", task: "fast / simple", color: "text-[#FAFAFA]" },
          ].map(m => (
            <div key={m.name} className="border border-zinc-800 p-3">
              <div className={`font-bold ${m.color}`}>{m.name}</div>
              <div className="text-zinc-500 text-[10px] uppercase mt-1">{m.task}</div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default Settings;
