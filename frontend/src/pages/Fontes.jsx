import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { toast } from "sonner";
import { Database, Globe, FileText, RefreshCw, Trash2, Plus, CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";

const Fontes = () => {
  const [sources, setSources] = useState([]);
  const [mode, setMode] = useState(null); // "url" | "text" | null
  const [urlForm, setUrlForm] = useState({ name: "", url: "" });
  const [textForm, setTextForm] = useState({ name: "", text: "" });
  const [busy, setBusy] = useState(false);

  const load = async () => setSources((await api.get("/data-sources")).data);
  useEffect(() => { load(); }, []);

  const addUrl = async () => {
    if (!urlForm.url || !urlForm.name) return toast.error("Preencha nome e URL");
    setBusy(true);
    try {
      await api.post("/data-sources/url", urlForm);
      toast.success("Fonte indexada.");
      setUrlForm({ name: "", url: "" }); setMode(null); load();
    } catch (e) { toast.error("Falha ao indexar"); }
    finally { setBusy(false); }
  };
  const addText = async () => {
    if (!textForm.text || !textForm.name) return toast.error("Preencha nome e texto");
    setBusy(true);
    try {
      await api.post("/data-sources/text", textForm);
      toast.success("Texto indexado.");
      setTextForm({ name: "", text: "" }); setMode(null); load();
    } catch { toast.error("Falha"); }
    finally { setBusy(false); }
  };

  const reindex = async (id) => {
    await api.post(`/data-sources/${id}/reindex`); toast.success("Reindexado"); load();
  };
  const del = async (id) => {
    await api.delete(`/data-sources/${id}`); toast.success("Eliminado"); load();
  };

  const kindIcon = { url: Globe, text: FileText, file: FileText };
  const statusBadge = {
    indexed: { cls: "badge-green", icon: CheckCircle2, label: "Indexada" },
    pending: { cls: "badge-amber", icon: Loader2, label: "A processar" },
    error: { cls: "badge-red", icon: AlertTriangle, label: "Erro" },
  };

  return (
    <div className="h-full overflow-y-auto p-8 space-y-6" data-testid="fontes-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold">Fontes de dados</h1>
          <p className="text-sm text-[#5B6B82] mt-1">Ligue sites, catálogos e documentos. A IA usa-os para responder.</p>
        </div>
        <div className="flex gap-2">
          <button data-testid="btn-add-url" onClick={() => setMode(mode === "url" ? null : "url")}
            className="btn-ghost"><Globe size={14} /> Ligar site</button>
          <button data-testid="btn-add-text" onClick={() => setMode(mode === "text" ? null : "text")}
            className="btn-primary"><Plus size={14} /> Adicionar texto</button>
        </div>
      </div>

      {mode === "url" && (
        <div className="card-surface p-5" data-testid="url-form">
          <div className="label">Nome interno</div>
          <input data-testid="url-name" value={urlForm.name} onChange={(e) => setUrlForm({ ...urlForm, name: e.target.value })}
            placeholder="Ex: Catálogo de imóveis" className="input-base mb-3" />
          <div className="label">URL a raspar</div>
          <input data-testid="url-url" value={urlForm.url} onChange={(e) => setUrlForm({ ...urlForm, url: e.target.value })}
            placeholder="https://exemplo.pt/imoveis" className="input-base mb-3" />
          <div className="flex gap-2 justify-end">
            <button className="btn-ghost" onClick={() => setMode(null)}>Cancelar</button>
            <button data-testid="btn-save-url" onClick={addUrl} disabled={busy} className="btn-primary">
              {busy ? "A indexar…" : "Indexar agora"}
            </button>
          </div>
        </div>
      )}

      {mode === "text" && (
        <div className="card-surface p-5" data-testid="text-form">
          <div className="label">Nome</div>
          <input data-testid="text-name" value={textForm.name} onChange={(e) => setTextForm({ ...textForm, name: e.target.value })}
            placeholder="Ex: Políticas e FAQ" className="input-base mb-3" />
          <div className="label">Texto / conhecimento</div>
          <textarea data-testid="text-text" value={textForm.text} onChange={(e) => setTextForm({ ...textForm, text: e.target.value })}
            rows={6} className="input-base mb-3" placeholder="Cole aqui o conhecimento que a IA deve usar…" />
          <div className="flex gap-2 justify-end">
            <button className="btn-ghost" onClick={() => setMode(null)}>Cancelar</button>
            <button data-testid="btn-save-text" onClick={addText} disabled={busy} className="btn-primary">
              {busy ? "A indexar…" : "Indexar"}
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {sources.map(s => {
          const Icon = kindIcon[s.kind] || Database;
          const sb = statusBadge[s.status] || statusBadge.pending;
          const SIcon = sb.icon;
          return (
            <div key={s.id} data-testid={`source-${s.id}`} className="card-surface p-5">
              <div className="flex items-start justify-between">
                <div className="w-10 h-10 rounded-lg bg-[#EAF2FF] text-[#0069FE] flex items-center justify-center">
                  <Icon size={18} />
                </div>
                <span className={`badge ${sb.cls}`}><SIcon size={10} /> {sb.label}</span>
              </div>
              <div className="mt-4">
                <div className="font-semibold">{s.name}</div>
                {s.url && <div className="text-xs text-[#5B6B82] mt-1 truncate">{s.url}</div>}
              </div>
              <div className="grid grid-cols-2 gap-3 mt-4 text-xs">
                <div>
                  <div className="text-[#5B6B82] uppercase tracking-wider font-semibold">Chunks</div>
                  <div className="text-lg font-bold font-display">{s.chunks}</div>
                </div>
                <div>
                  <div className="text-[#5B6B82] uppercase tracking-wider font-semibold">Items</div>
                  <div className="text-lg font-bold font-display">{s.items}</div>
                </div>
              </div>
              {s.error && <div className="text-[11px] text-[#DC2626] mt-2 truncate">{s.error}</div>}
              <div className="flex gap-2 mt-4">
                {s.kind === "url" && (
                  <button data-testid={`btn-reindex-${s.id}`} onClick={() => reindex(s.id)}
                    className="btn-ghost text-[12px] flex-1 justify-center"><RefreshCw size={12} /> Reindexar</button>
                )}
                <button data-testid={`btn-delete-${s.id}`} onClick={() => del(s.id)}
                  className="btn-ghost text-[12px] justify-center hover:text-[#DC2626]"><Trash2 size={12} /></button>
              </div>
            </div>
          );
        })}
        {sources.length === 0 && !mode && (
          <div className="col-span-full card-surface p-12 text-center">
            <Database size={36} className="mx-auto text-[#C7D0DF]" />
            <div className="font-semibold mt-3">Ainda sem fontes de dados</div>
            <div className="text-sm text-[#5B6B82] mt-1">Ligue um site (ex: listagens imobiliárias) ou adicione texto para a IA usar.</div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Fontes;
