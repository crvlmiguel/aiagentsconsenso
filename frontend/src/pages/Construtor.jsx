import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Wand2, Bot, Sparkles, Database, Check, ArrowRight } from "lucide-react";

const templates = [
  { key: "realestate", name: "Imobiliária", tone: "profissional e caloroso", goal: "Qualificar interesse em imóveis e marcar visitas",
    prompt: "És o assistente de uma imobiliária em Portugal. Ajuda os clientes a encontrar imóveis, pede localização desejada, tipologia e orçamento. Responde sempre em Português Europeu.",
    rules: "Pede sempre nome e contacto antes de dar preços. Se o cliente pedir imóvel fora do inventário, cria ticket. Nunca inventes preços." },
  { key: "support", name: "Suporte técnico", tone: "paciente e preciso", goal: "Resolver problemas técnicos rapidamente",
    prompt: "És o assistente de suporte técnico. Ajuda clientes a diagnosticar problemas e encontrar soluções.",
    rules: "Pede versão do produto, sistema operativo e passos para reproduzir. Escala problemas urgentes criando ticket." },
  { key: "ecommerce", name: "E-commerce", tone: "simpático e eficiente", goal: "Aumentar vendas e apoiar pré-venda",
    prompt: "És o assistente de uma loja online. Ajuda clientes a encontrar produtos, tirar dúvidas de envios e devoluções.",
    rules: "Mostra produtos como cards com imagem e preço. Cria lead para carrinhos abandonados." },
  { key: "clinic", name: "Clínica / Saúde", tone: "empático e formal", goal: "Marcar consultas e responder a dúvidas",
    prompt: "És o assistente de uma clínica. Ajuda a marcar consultas e esclareces dúvidas.",
    rules: "Nunca dês conselho médico. Para urgências, encaminha para humano." },
];

const Construtor = () => {
  const nav = useNavigate();
  const [step, setStep] = useState(1);
  const [template, setTemplate] = useState(null);
  const [form, setForm] = useState({
    name: "", tone: "", goal: "", system_prompt: "", rules: "",
    default_language: "pt", knowledge: "",
  });
  const [urlSource, setUrlSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [sources, setSources] = useState([]);
  const [selectedSources, setSelectedSources] = useState([]);

  useEffect(() => { api.get("/data-sources").then(r => setSources(r.data)); }, []);

  const applyTemplate = (t) => {
    setTemplate(t);
    setForm({
      name: t.name, tone: t.tone, goal: t.goal,
      system_prompt: t.prompt, rules: t.rules,
      default_language: "pt", knowledge: "",
    });
    setStep(2);
  };

  const next = () => setStep(step + 1);
  const back = () => setStep(Math.max(1, step - 1));

  const importUrl = async () => {
    if (!urlSource) return;
    setBusy(true);
    try {
      const { data } = await api.post("/data-sources/url", { name: `Importado — ${new URL(urlSource).hostname}`, url: urlSource });
      toast.success("Fonte ligada.");
      setSources([data, ...sources]);
      setSelectedSources([...selectedSources, data.id]);
      setUrlSource("");
    } catch { toast.error("Falha a raspar o URL"); }
    finally { setBusy(false); }
  };

  const finish = async () => {
    setBusy(true);
    try {
      const payload = {
        ...form,
        model_provider: "auto", model_name: "gpt-5.1",
        tools: [
          { key: "create_lead", enabled: true },
          { key: "create_ticket", enabled: true },
          { key: "send_email", enabled: false },
          { key: "webhook", enabled: false },
        ],
        data_source_ids: selectedSources,
        active: true,
      };
      const { data } = await api.post("/agents", payload);
      toast.success("Agente criado e ativo!");
      nav(`/app/agentes?selected=${data.id}`);
    } catch (e) { toast.error("Falha ao criar agente"); }
    finally { setBusy(false); }
  };

  const Step = ({ n, label, active, done }) => (
    <div className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
        done ? "bg-[#16A34A] text-white" : active ? "bg-[#0069FE] text-white" : "bg-[#E5EAF2] text-[#5B6B82]"
      }`}>{done ? <Check size={14} /> : n}</div>
      <span className={`text-sm font-semibold ${active || done ? "text-[#0B1324]" : "text-[#5B6B82]"}`}>{label}</span>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-8" data-testid="construtor-page">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-2 text-[#0069FE] mb-2">
          <Wand2 size={18} />
          <span className="text-sm font-semibold uppercase tracking-wider">Construtor de chatbot</span>
        </div>
        <h1 className="font-display text-3xl font-bold">Crie o seu agente em minutos</h1>
        <p className="text-[#5B6B82] mt-1">Escolha um modelo, conecte os seus dados e coloque online.</p>

        <div className="flex items-center gap-6 mt-8">
          <Step n={1} label="Modelo" active={step === 1} done={step > 1} />
          <div className="flex-1 h-px bg-[#E5EAF2]" />
          <Step n={2} label="Instruções" active={step === 2} done={step > 2} />
          <div className="flex-1 h-px bg-[#E5EAF2]" />
          <Step n={3} label="Dados" active={step === 3} done={step > 3} />
          <div className="flex-1 h-px bg-[#E5EAF2]" />
          <Step n={4} label="Ativar" active={step === 4} done={false} />
        </div>

        <div className="mt-8 card-surface p-8">
          {step === 1 && (
            <div data-testid="step-1">
              <h2 className="font-display text-xl font-bold">Escolha um ponto de partida</h2>
              <p className="text-sm text-[#5B6B82] mt-1">Pode personalizar depois.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-6">
                {templates.map(t => (
                  <button key={t.key} data-testid={`tpl-${t.key}`} onClick={() => applyTemplate(t)}
                    className={`text-left p-4 rounded-xl border-2 transition-all ${
                      template?.key === t.key ? "border-[#0069FE] bg-[#EAF2FF]" : "border-[#E5EAF2] hover:border-[#0069FE]"
                    }`}>
                    <div className="flex items-center gap-2">
                      <div className="w-9 h-9 rounded-lg bg-[#EAF2FF] text-[#0069FE] flex items-center justify-center">
                        <Bot size={16} />
                      </div>
                      <div className="font-semibold">{t.name}</div>
                    </div>
                    <div className="text-xs text-[#5B6B82] mt-2 leading-relaxed">{t.goal}</div>
                  </button>
                ))}
              </div>
            </div>
          )}

          {step === 2 && (
            <div data-testid="step-2" className="space-y-4">
              <h2 className="font-display text-xl font-bold">Personalize as instruções</h2>
              <div>
                <label className="label">Nome do agente</label>
                <input data-testid="b-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="input-base" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Tom de voz</label>
                  <input data-testid="b-tone" value={form.tone} onChange={(e) => setForm({ ...form, tone: e.target.value })} className="input-base" />
                </div>
                <div>
                  <label className="label">Objetivo</label>
                  <input data-testid="b-goal" value={form.goal} onChange={(e) => setForm({ ...form, goal: e.target.value })} className="input-base" />
                </div>
              </div>
              <div>
                <label className="label">Prompt do sistema</label>
                <textarea data-testid="b-prompt" rows={4} value={form.system_prompt} onChange={(e) => setForm({ ...form, system_prompt: e.target.value })} className="input-base" />
              </div>
              <div>
                <label className="label">Regras (qualificação, tags, etc.)</label>
                <textarea data-testid="b-rules" rows={3} value={form.rules} onChange={(e) => setForm({ ...form, rules: e.target.value })} className="input-base" />
              </div>
              <div>
                <label className="label">Idioma predefinido</label>
                <select data-testid="b-lang" value={form.default_language} onChange={(e) => setForm({ ...form, default_language: e.target.value })} className="input-base">
                  <option value="pt">Português (pt-PT)</option>
                  <option value="en">English</option>
                  <option value="es">Español</option>
                  <option value="fr">Français</option>
                </select>
              </div>
            </div>
          )}

          {step === 3 && (
            <div data-testid="step-3" className="space-y-4">
              <h2 className="font-display text-xl font-bold">Ligue as suas fontes de dados</h2>
              <p className="text-sm text-[#5B6B82]">Sites, catálogos, FAQs. A IA usa-os para responder com cards.</p>
              <div className="flex gap-2">
                <input data-testid="b-url" value={urlSource} onChange={(e) => setUrlSource(e.target.value)}
                  placeholder="https://exemplo.pt/imoveis" className="input-base flex-1" />
                <button data-testid="btn-import-url" onClick={importUrl} disabled={busy} className="btn-primary">
                  <Database size={14} /> {busy ? "A indexar…" : "Importar"}
                </button>
              </div>
              <div className="border-t border-[#E5EAF2] pt-4">
                <div className="label">Ou selecione fontes existentes</div>
                {sources.length === 0 && <div className="text-xs text-[#5B6B82]">Nenhuma fonte ainda.</div>}
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {sources.map(s => {
                    const on = selectedSources.includes(s.id);
                    return (
                      <label key={s.id} data-testid={`src-${s.id}`}
                        className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          on ? "border-[#0069FE] bg-[#EAF2FF]" : "border-[#E5EAF2] hover:bg-[#F7F9FC]"
                        }`}>
                        <input type="checkbox" checked={on} onChange={() => {
                          setSelectedSources(on ? selectedSources.filter(x => x !== s.id) : [...selectedSources, s.id]);
                        }} className="accent-[#0069FE]" />
                        <Database size={16} className="text-[#5B6B82]" />
                        <div className="flex-1">
                          <div className="text-sm font-semibold">{s.name}</div>
                          <div className="text-[11px] text-[#5B6B82]">{s.chunks} chunks · {s.items} items · {s.kind}</div>
                        </div>
                        <span className={`badge ${s.status === "indexed" ? "badge-green" : s.status === "error" ? "badge-red" : "badge-amber"}`}>{s.status}</span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {step === 4 && (
            <div data-testid="step-4" className="space-y-4">
              <h2 className="font-display text-xl font-bold">Confirme e ative</h2>
              <div className="card-surface p-5 bg-[#F7F9FC]">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl bg-[#0069FE] text-white flex items-center justify-center">
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <div className="font-display font-bold text-lg">{form.name}</div>
                    <div className="text-xs text-[#5B6B82]">{form.goal}</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3 mt-4 text-sm">
                  <div><span className="text-[#5B6B82]">Tom:</span> <b>{form.tone}</b></div>
                  <div><span className="text-[#5B6B82]">Idioma:</span> <b>{form.default_language.toUpperCase()}</b></div>
                  <div><span className="text-[#5B6B82]">Fontes:</span> <b>{selectedSources.length}</b></div>
                  <div><span className="text-[#5B6B82]">Estado:</span> <span className="badge badge-green">Pronto</span></div>
                </div>
              </div>
              <p className="text-sm text-[#5B6B82]">Após ativar, o agente fica imediatamente disponível na caixa de entrada e no widget web.</p>
            </div>
          )}

          <div className="flex justify-between mt-8">
            <button data-testid="btn-back" onClick={back} disabled={step === 1} className="btn-ghost">Voltar</button>
            {step < 4 && (
              <button data-testid="btn-next" onClick={next} disabled={step === 1 && !template} className="btn-primary">
                Continuar <ArrowRight size={14} />
              </button>
            )}
            {step === 4 && (
              <button data-testid="btn-activate" onClick={finish} disabled={busy} className="btn-primary">
                <Sparkles size={14} /> {busy ? "A criar…" : "Ativar agente"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Construtor;
