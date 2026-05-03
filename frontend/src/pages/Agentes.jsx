import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Bot, Play, Trash2, Plus, Save, Sparkles, Database } from "lucide-react";

const defaultAgent = {
  name: "Novo Agente", tone: "profissional", goal: "Ajudar clientes",
  system_prompt: "És um assistente útil. Responde em Português Europeu.",
  rules: "", model_provider: "auto", model_name: "gpt-5.1",
  tools: [
    { key: "create_lead", enabled: true }, { key: "create_ticket", enabled: true },
    { key: "send_email", enabled: false }, { key: "webhook", enabled: false },
  ],
  knowledge: "", data_source_ids: [], default_language: "pt", active: true,
};

const Agentes = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [sources, setSources] = useState([]);
  const [testText, setTestText] = useState("Quero ver imóveis T3 em Lisboa até 400k€");
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [params] = useSearchParams();

  const load = async () => {
    const [a, s] = await Promise.all([api.get("/agents"), api.get("/data-sources")]);
    setAgents(a.data); setSources(s.data);
    const preselect = params.get("selected");
    if (!selected && a.data.length > 0) setSelected(a.data.find(x => x.id === preselect) || a.data[0]);
  };
  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const save = async () => {
    try {
      if (selected.id && agents.find(a => a.id === selected.id)) {
        const { data } = await api.put(`/agents/${selected.id}`, selected);
        setSelected(data); toast.success("Agente guardado.");
      } else {
        const { data } = await api.post("/agents", selected);
        setSelected(data); toast.success("Agente criado.");
      }
      load();
    } catch { toast.error("Falha a guardar"); }
  };
  const del = async () => {
    if (!selected?.id) return;
    await api.delete(`/agents/${selected.id}`); setSelected(null); load(); toast.success("Eliminado.");
  };
  const test = async () => {
    if (!selected?.id) return toast.error("Guarde o agente primeiro.");
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post(`/agents/${selected.id}/test`, { text: testText });
      setTestResult(data);
    } catch { toast.error("Falha no teste"); }
    finally { setTesting(false); }
  };
  const update = (k, v) => setSelected({ ...selected, [k]: v });
  const toggleTool = (key) => {
    const tools = selected.tools.map(t => t.key === key ? { ...t, enabled: !t.enabled } : t);
    update("tools", tools);
  };
  const toggleSource = (id) => {
    const has = (selected.data_source_ids || []).includes(id);
    update("data_source_ids", has ? selected.data_source_ids.filter(x => x !== id) : [...(selected.data_source_ids || []), id]);
  };

  return (
    <div className="h-full grid grid-cols-[300px_1fr] overflow-hidden">
      <div className="border-r border-[#E5EAF2] bg-white flex flex-col">
        <div className="p-4 border-b border-[#E5EAF2] flex items-center justify-between">
          <h1 className="font-display text-xl font-bold">Agentes IA</h1>
          <button data-testid="btn-new-agent" onClick={() => setSelected({ ...defaultAgent })} className="btn-ghost text-[12px] py-2">
            <Plus size={12} /> Novo
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {agents.map(a => (
            <button key={a.id} data-testid={`agent-item-${a.id}`} onClick={() => setSelected(a)}
              className={`w-full text-left p-3 rounded-lg mb-1 transition-colors ${
                selected?.id === a.id ? "bg-[#EAF2FF]" : "hover:bg-[#F7F9FC]"
              }`}>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#0069FE] text-white flex items-center justify-center">
                  <Bot size={14} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-sm truncate">{a.name}</div>
                  <div className="text-[11px] text-[#5B6B82]">{a.model_provider} · {a.active ? "ATIVO" : "INATIVO"}</div>
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-y-auto p-8 bg-[#F7F9FC]">
        {!selected && <div className="text-sm text-[#5B6B82]">Selecione ou crie um agente.</div>}
        {selected && (
          <div className="max-w-3xl space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-[#5B6B82] uppercase tracking-wider">Agente</div>
                <input data-testid="agent-name" value={selected.name} onChange={(e) => update("name", e.target.value)}
                  className="font-display text-3xl font-bold bg-transparent border-b-2 border-transparent focus:border-[#0069FE] outline-none" />
              </div>
              <div className="flex gap-2">
                {selected.id && <button data-testid="btn-delete-agent" onClick={del} className="btn-ghost text-[13px] hover:text-[#DC2626]"><Trash2 size={13} /> Eliminar</button>}
                <button data-testid="btn-save-agent" onClick={save} className="btn-primary"><Save size={13} /> Guardar</button>
              </div>
            </div>

            <div className="card-surface p-6">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Tom</label>
                  <input data-testid="agent-tone" value={selected.tone} onChange={(e) => update("tone", e.target.value)} className="input-base" />
                </div>
                <div>
                  <label className="label">Objetivo</label>
                  <input data-testid="agent-goal" value={selected.goal} onChange={(e) => update("goal", e.target.value)} className="input-base" />
                </div>
                <div>
                  <label className="label">Provider LLM</label>
                  <select data-testid="agent-provider" value={selected.model_provider} onChange={(e) => update("model_provider", e.target.value)} className="input-base">
                    <option value="auto">AUTO (routing inteligente)</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="gemini">Gemini</option>
                  </select>
                </div>
                <div>
                  <label className="label">Modelo</label>
                  <input data-testid="agent-model" value={selected.model_name} onChange={(e) => update("model_name", e.target.value)} className="input-base" />
                </div>
                <div>
                  <label className="label">Idioma predefinido</label>
                  <select data-testid="agent-lang" value={selected.default_language || "pt"} onChange={(e) => update("default_language", e.target.value)} className="input-base">
                    <option value="pt">Português (pt-PT)</option>
                    <option value="en">English</option>
                    <option value="es">Español</option>
                    <option value="fr">Français</option>
                  </select>
                </div>
                <div>
                  <label className="label">Estado</label>
                  <select value={selected.active ? "1" : "0"} onChange={(e) => update("active", e.target.value === "1")} className="input-base">
                    <option value="1">Ativo</option>
                    <option value="0">Inativo</option>
                  </select>
                </div>
              </div>

              <label className="label mt-4">Prompt do sistema</label>
              <textarea data-testid="agent-system-prompt" rows={4} value={selected.system_prompt} onChange={(e) => update("system_prompt", e.target.value)} className="input-base" />

              <label className="label mt-4">Regras</label>
              <textarea data-testid="agent-rules" rows={3} value={selected.rules} onChange={(e) => update("rules", e.target.value)} className="input-base"
                placeholder="Ex: Pede sempre email antes de partilhar preços. Cria lead para orçamentos." />

              <label className="label mt-4">Conhecimento inline</label>
              <textarea data-testid="agent-knowledge" rows={3} value={selected.knowledge} onChange={(e) => update("knowledge", e.target.value)} className="input-base"
                placeholder="Cole FAQ, preços, políticas…" />
            </div>

            <div className="card-surface p-6">
              <div className="flex items-center gap-2 mb-3">
                <Database size={16} className="text-[#0069FE]" />
                <div className="font-display font-semibold">Fontes de dados ligadas</div>
              </div>
              {sources.length === 0 && <div className="text-xs text-[#5B6B82]">Nenhuma fonte. Adicione em "Fontes de dados".</div>}
              <div className="space-y-2">
                {sources.map(s => {
                  const on = (selected.data_source_ids || []).includes(s.id);
                  return (
                    <label key={s.id} data-testid={`src-toggle-${s.id}`}
                      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer ${on ? "border-[#0069FE] bg-[#EAF2FF]" : "border-[#E5EAF2]"}`}>
                      <input type="checkbox" checked={on} onChange={() => toggleSource(s.id)} className="accent-[#0069FE]" />
                      <div className="flex-1">
                        <div className="text-sm font-semibold">{s.name}</div>
                        <div className="text-[11px] text-[#5B6B82]">{s.chunks} chunks · {s.items} items · {s.status}</div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="card-surface p-6">
              <div className="font-display font-semibold mb-2">Ferramentas</div>
              <div className="grid grid-cols-2 gap-2">
                {selected.tools?.map(t => (
                  <label key={t.key} data-testid={`tool-${t.key}`}
                    className={`flex items-center gap-2 border rounded-lg px-3 py-2.5 text-sm cursor-pointer ${t.enabled ? "border-[#0069FE] bg-[#EAF2FF]" : "border-[#E5EAF2] text-[#5B6B82]"}`}>
                    <input type="checkbox" checked={t.enabled} onChange={() => toggleTool(t.key)} className="accent-[#0069FE]" />
                    <span className="font-semibold capitalize">{t.key.replace("_", " ")}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="card-surface p-6">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={16} className="text-[#0069FE]" />
                <div className="font-display font-semibold">Testar pipeline completo</div>
              </div>
              <textarea data-testid="agent-test-input" rows={2} value={testText} onChange={(e) => setTestText(e.target.value)} className="input-base" />
              <button data-testid="btn-test-agent" onClick={test} disabled={testing} className="btn-primary mt-3">
                <Play size={13} /> {testing ? "A processar…" : "Executar pipeline"}
              </button>
              {testResult && (
                <div className="mt-5 space-y-3 text-xs">
                  <div>
                    <div className="label">Resposta da IA</div>
                    <div className="bg-[#EAF2FF] border border-[#C7DDFF] rounded-xl p-4 text-[#0B1324] text-sm whitespace-pre-wrap">{testResult.reply}</div>
                    {testResult.cards?.length > 0 && (
                      <div className="grid grid-cols-2 gap-2 mt-2">
                        {testResult.cards.map((c, i) => (
                          <div key={i} className="card-surface p-3">
                            <div className="font-semibold text-sm">{c.title}</div>
                            {c.price && <div className="text-[#0069FE] text-xs font-bold">{c.price}</div>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  <details className="bg-[#F7F9FC] rounded-lg p-3">
                    <summary className="cursor-pointer text-[#5B6B82] font-semibold text-[11px] uppercase tracking-wider">Detalhes do pipeline</summary>
                    <pre className="mt-2 overflow-x-auto">{JSON.stringify({ intent: testResult.intent, structure: testResult.structure, decision: testResult.decision, retrieved: testResult.retrieved?.length, language: testResult.language }, null, 2)}</pre>
                  </details>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Agentes;
