import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Bot, Play, Trash2, Plus, Save } from "lucide-react";

const defaultAgent = {
  name: "New Agent",
  tone: "professional",
  goal: "Help customers",
  system_prompt: "You are a helpful AI assistant.",
  rules: "",
  model_provider: "auto",
  model_name: "gpt-5.1",
  tools: [
    { key: "create_lead", enabled: true },
    { key: "create_ticket", enabled: true },
    { key: "send_email", enabled: false },
    { key: "webhook", enabled: false },
  ],
  knowledge: "",
  active: true,
};

const Agents = () => {
  const [agents, setAgents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [testText, setTestText] = useState("I'm interested in pricing for 20 users.");
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);

  const load = async () => {
    const { data } = await api.get("/agents");
    setAgents(data);
    if (!selected && data.length > 0) setSelected(data[0]);
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const save = async () => {
    try {
      if (selected.id && agents.find(a => a.id === selected.id)) {
        const { data } = await api.put(`/agents/${selected.id}`, selected);
        setSelected(data);
        toast.success("Agent saved.");
      } else {
        const { data } = await api.post("/agents", selected);
        setSelected(data);
        toast.success("Agent created.");
      }
      load();
    } catch { toast.error("Save failed"); }
  };

  const del = async () => {
    if (!selected?.id) return;
    await api.delete(`/agents/${selected.id}`);
    setSelected(null);
    load();
    toast.success("Deleted.");
  };

  const test = async () => {
    if (!selected?.id) return toast.error("Save agent first.");
    setTesting(true); setTestResult(null);
    try {
      const { data } = await api.post(`/agents/${selected.id}/test`, { text: testText });
      setTestResult(data);
    } catch { toast.error("Test failed"); }
    finally { setTesting(false); }
  };

  const update = (k, v) => setSelected({ ...selected, [k]: v });
  const toggleTool = (key) => {
    const tools = selected.tools.map(t => t.key === key ? { ...t, enabled: !t.enabled } : t);
    update("tools", tools);
  };

  return (
    <div className="h-full grid grid-cols-[300px_1fr] overflow-hidden">
      <div className="border-r border-zinc-800 flex flex-col">
        <div className="p-4 border-b border-zinc-800 flex items-center justify-between">
          <h1 className="text-xl font-bold uppercase tracking-tight">Agents</h1>
          <button
            data-testid="btn-new-agent"
            onClick={() => setSelected({ ...defaultAgent })}
            className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-white px-2 py-1 flex items-center gap-1"
          >
            <Plus size={12} /> New
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {agents.map((a) => (
            <button
              key={a.id}
              data-testid={`agent-item-${a.id}`}
              onClick={() => setSelected(a)}
              className={`w-full text-left border-b border-zinc-800 p-3 border-l-2 transition-colors ${
                selected?.id === a.id ? "bg-zinc-900 border-l-[#FF5500]" : "border-l-transparent hover:bg-zinc-900/50"
              }`}
            >
              <div className="flex items-center gap-2">
                <Bot size={14} className="text-[#FF5500]" />
                <span className="font-bold text-sm">{a.name}</span>
              </div>
              <div className="mono text-[10px] text-zinc-500 uppercase mt-1">
                {a.model_provider} · {a.active ? "ACTIVE" : "INACTIVE"}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-y-auto p-6">
        {!selected && (
          <div className="text-zinc-500 mono text-xs uppercase tracking-widest">
            Select or create an agent
          </div>
        )}
        {selected && (
          <div className="max-w-3xl space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="label-mono">AGENT / CONFIG</div>
                <input
                  data-testid="agent-name"
                  value={selected.name}
                  onChange={(e) => update("name", e.target.value)}
                  className="text-3xl font-bold uppercase tracking-tight bg-transparent border-b border-transparent focus:border-white outline-none"
                />
              </div>
              <div className="flex gap-2">
                {selected.id && (
                  <button
                    data-testid="btn-delete-agent"
                    onClick={del}
                    className="mono text-[10px] uppercase tracking-widest border border-zinc-700 hover:border-[#EF4444] hover:text-[#EF4444] px-3 py-2 flex items-center gap-1"
                  ><Trash2 size={12} /> Delete</button>
                )}
                <button
                  data-testid="btn-save-agent"
                  onClick={save}
                  className="bg-white text-black px-4 py-2 font-bold mono text-xs uppercase tracking-widest hover:bg-zinc-200 flex items-center gap-1"
                ><Save size={12} /> Save</button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="label-mono mb-1">TONE</div>
                <input
                  data-testid="agent-tone"
                  className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm focus:border-white outline-none"
                  value={selected.tone} onChange={(e) => update("tone", e.target.value)}
                />
              </div>
              <div>
                <div className="label-mono mb-1">GOAL</div>
                <input
                  data-testid="agent-goal"
                  className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm focus:border-white outline-none"
                  value={selected.goal} onChange={(e) => update("goal", e.target.value)}
                />
              </div>
              <div>
                <div className="label-mono mb-1">LLM PROVIDER</div>
                <select
                  data-testid="agent-provider"
                  className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm mono uppercase focus:border-white outline-none"
                  value={selected.model_provider} onChange={(e) => update("model_provider", e.target.value)}
                >
                  <option value="auto">AUTO (SMART ROUTING)</option>
                  <option value="openai">OPENAI</option>
                  <option value="anthropic">ANTHROPIC</option>
                  <option value="gemini">GEMINI</option>
                </select>
              </div>
              <div>
                <div className="label-mono mb-1">MODEL</div>
                <input
                  data-testid="agent-model"
                  className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm mono focus:border-white outline-none"
                  value={selected.model_name} onChange={(e) => update("model_name", e.target.value)}
                />
              </div>
            </div>

            <div>
              <div className="label-mono mb-1">SYSTEM PROMPT</div>
              <textarea
                data-testid="agent-system-prompt"
                rows={4}
                className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm focus:border-white outline-none"
                value={selected.system_prompt} onChange={(e) => update("system_prompt", e.target.value)}
              />
            </div>

            <div>
              <div className="label-mono mb-1">RULES</div>
              <textarea
                data-testid="agent-rules"
                rows={3}
                className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm focus:border-white outline-none"
                placeholder="e.g. Always collect email before quoting. Escalate refunds to humans."
                value={selected.rules} onChange={(e) => update("rules", e.target.value)}
              />
            </div>

            <div>
              <div className="label-mono mb-1">KNOWLEDGE (inline)</div>
              <textarea
                data-testid="agent-knowledge"
                rows={3}
                className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm focus:border-white outline-none"
                placeholder="Paste FAQ, pricing, policies here…"
                value={selected.knowledge} onChange={(e) => update("knowledge", e.target.value)}
              />
            </div>

            <div>
              <div className="label-mono mb-2">TOOLS</div>
              <div className="grid grid-cols-2 gap-2">
                {selected.tools?.map((t) => (
                  <label
                    key={t.key}
                    data-testid={`tool-${t.key}`}
                    className={`flex items-center gap-2 border px-3 py-2 text-sm cursor-pointer ${t.enabled ? "border-white bg-zinc-900" : "border-zinc-800 text-zinc-500"}`}
                  >
                    <input type="checkbox" checked={t.enabled} onChange={() => toggleTool(t.key)} className="accent-white" />
                    <span className="mono uppercase text-xs tracking-widest">{t.key.replace("_", " ")}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Tester */}
            <div className="border border-zinc-800 p-4">
              <div className="flex items-center gap-2 mb-2">
                <Play size={14} className="text-[#FF5500]" />
                <div className="label-mono">LIVE AGENT TEST</div>
              </div>
              <textarea
                data-testid="agent-test-input"
                rows={2}
                className="w-full bg-[#18181B] border border-zinc-800 px-3 py-2 text-sm focus:border-white outline-none"
                value={testText} onChange={(e) => setTestText(e.target.value)}
              />
              <button
                data-testid="btn-test-agent"
                onClick={test} disabled={testing}
                className="mt-2 bg-[#FF5500] text-black px-4 py-2 font-bold mono text-xs uppercase tracking-widest hover:bg-[#ff7a33] disabled:opacity-50"
              >
                {testing ? "Running pipeline…" : "Run full pipeline →"}
              </button>

              {testResult && (
                <div className="mt-4 space-y-3 text-xs mono">
                  <div>
                    <div className="label-mono mb-1">INTENT</div>
                    <pre className="bg-[#09090B] border border-zinc-800 p-2 overflow-x-auto">{JSON.stringify(testResult.intent, null, 2)}</pre>
                  </div>
                  <div>
                    <div className="label-mono mb-1">STRUCTURE</div>
                    <pre className="bg-[#09090B] border border-zinc-800 p-2 overflow-x-auto">{JSON.stringify(testResult.structure, null, 2)}</pre>
                  </div>
                  <div>
                    <div className="label-mono mb-1">DECISION</div>
                    <pre className="bg-[#09090B] border border-zinc-800 p-2 overflow-x-auto">{JSON.stringify(testResult.decision, null, 2)}</pre>
                  </div>
                  <div>
                    <div className="label-mono mb-1">AI REPLY</div>
                    <div className="bg-[#09090B] border border-zinc-800 ai-bubble p-3 text-white text-sm whitespace-pre-wrap">{testResult.reply}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Agents;
