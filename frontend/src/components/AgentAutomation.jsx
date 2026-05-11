import React, { useState, useEffect } from "react";
import { Plus, Trash2, RefreshCw, Loader2, Check, AlertCircle, Rss, Zap } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";

const FEED_TYPES = [
  { v: "csv", label: "CSV (URL pública)" },
  { v: "xml", label: "XML (feed Idealista/Imovirtual)" },
  { v: "gsheet", label: "Google Sheets (publicado em CSV)" },
];

export default function AgentAutomation({ agentId }) {
  const [loading, setLoading] = useState(true);
  const [feeds, setFeeds] = useState([]);
  const [followUpEnabled, setFollowUpEnabled] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      setLoading(true);
      const { data } = await api.get(`/agents/${agentId}/feeds`);
      setFeeds(data.feeds || []);
      setFollowUpEnabled(data.follow_up_enabled !== false);
    } catch {
      toast.error("Não foi possível carregar feeds");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (agentId) load();
    // eslint-disable-next-line
  }, [agentId]);

  const addFeed = () => {
    setFeeds([...feeds, { type: "csv", url: "", name: "" }]);
  };

  const updateFeed = (idx, patch) => {
    const next = [...feeds];
    next[idx] = { ...next[idx], ...patch };
    setFeeds(next);
  };

  const removeFeed = (idx) => {
    setFeeds(feeds.filter((_, i) => i !== idx));
  };

  const save = async () => {
    try {
      setSaving(true);
      const payload = {
        feeds: feeds.filter(f => f.url),
        follow_up_enabled: followUpEnabled,
      };
      const { data } = await api.put(`/agents/${agentId}/feeds`, payload);
      setFeeds(data.feeds || []);
      toast.success("Configuração guardada");
    } catch {
      toast.error("Falha ao guardar");
    } finally {
      setSaving(false);
    }
  };

  const refreshNow = async () => {
    try {
      setRefreshing(true);
      const { data } = await api.post(`/agents/${agentId}/feeds/refresh`);
      const ok = (data.results || []).filter(r => r.ok).length;
      const total = (data.results || []).length;
      toast.success(`Refresh: ${ok}/${total} feeds atualizados`);
      load();
    } catch {
      toast.error("Refresh falhou");
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="card-surface p-8 flex justify-center">
        <Loader2 className="animate-spin text-[#0069FE]" />
      </div>
    );
  }

  return (
    <div className="space-y-5" data-testid="automation-panel">
      {/* WhatsApp Follow-up */}
      <div className="card-surface p-6">
        <div className="flex items-center gap-2 mb-2">
          <Zap size={16} className="text-[#0069FE]" />
          <div className="font-display font-semibold">Follow-up automático WhatsApp</div>
        </div>
        <p className="text-xs text-[#5B6B82] mb-3">
          Quando um lead com telefone e score ≥ 40 não responde, envia mensagens
          automáticas em 3 momentos: 24h → 3 dias → 7 dias. Requer canal WhatsApp ativo.
        </p>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={followUpEnabled}
            onChange={(e) => setFollowUpEnabled(e.target.checked)}
            className="accent-[#0069FE] w-4 h-4"
            data-testid="follow-up-toggle"
          />
          <span className="text-sm font-medium">
            {followUpEnabled ? "Ativo" : "Inativo"}
          </span>
        </label>
      </div>

      {/* External feeds */}
      <div className="card-surface p-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Rss size={16} className="text-[#0069FE]" />
            <div className="font-display font-semibold">Feeds de imóveis externos</div>
          </div>
          <button
            onClick={refreshNow}
            disabled={refreshing || feeds.length === 0}
            className="text-xs text-[#0069FE] flex items-center gap-1 hover:underline disabled:opacity-50"
            data-testid="btn-feed-refresh"
          >
            {refreshing ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
            Refresh agora
          </button>
        </div>
        <p className="text-xs text-[#5B6B82] mb-4">
          Importa imóveis de Idealista, Imovirtual ou qualquer feed CSV/XML público.
          A Maria só os apresenta quando o portefólio próprio não tem opções para o cliente.
          Refresh automático semanal.
        </p>

        <div className="space-y-3">
          {feeds.map((f, idx) => (
            <div
              key={idx}
              className="border border-[#E5EAF2] rounded-lg p-3 space-y-2"
              data-testid={`feed-row-${idx}`}
            >
              <div className="flex gap-2">
                <select
                  value={f.type}
                  onChange={(e) => updateFeed(idx, { type: e.target.value })}
                  className="text-xs border border-[#E5EAF2] rounded px-2 py-1.5 bg-white"
                  data-testid={`feed-type-${idx}`}
                >
                  {FEED_TYPES.map(t => (
                    <option key={t.v} value={t.v}>{t.label}</option>
                  ))}
                </select>
                <input
                  type="text"
                  placeholder="Nome (ex: Idealista Lisboa)"
                  value={f.name || ""}
                  onChange={(e) => updateFeed(idx, { name: e.target.value })}
                  className="flex-1 text-xs border border-[#E5EAF2] rounded px-2 py-1.5"
                  data-testid={`feed-name-${idx}`}
                />
                <button
                  onClick={() => removeFeed(idx)}
                  className="text-[#FF4D4F] hover:bg-[#FFF0F0] rounded p-1.5"
                  data-testid={`feed-remove-${idx}`}
                  title="Remover"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <input
                type="url"
                placeholder="https://exemplo.com/feed.csv"
                value={f.url || ""}
                onChange={(e) => updateFeed(idx, { url: e.target.value })}
                className="w-full text-xs border border-[#E5EAF2] rounded px-2.5 py-1.5"
                data-testid={`feed-url-${idx}`}
              />
              {f.items != null && (
                <div className="text-[11px] text-[#5B6B82] flex items-center gap-1">
                  <Check size={11} className="text-[#22c55e]" />
                  {f.items} imóveis indexados
                  {f.indexed_at && (
                    <span className="ml-1">· {new Date(f.indexed_at).toLocaleDateString("pt-PT")}</span>
                  )}
                </div>
              )}
            </div>
          ))}

          <button
            onClick={addFeed}
            className="w-full border-2 border-dashed border-[#E5EAF2] rounded-lg py-3 text-sm text-[#5B6B82] hover:border-[#0069FE] hover:text-[#0069FE] flex items-center justify-center gap-2"
            data-testid="btn-feed-add"
          >
            <Plus size={14} /> Adicionar feed
          </button>
        </div>

        <div className="bg-[#FFF9E6] border border-[#FCE4A6] rounded-lg p-3 mt-4 flex gap-2">
          <AlertCircle size={14} className="text-[#B8860B] flex-shrink-0 mt-0.5" />
          <div className="text-[11px] text-[#7A5C00] leading-relaxed">
            <strong>Dica:</strong> Para Google Sheets, cole o URL do sheet. Para CSV/XML públicos
            (Idealista, Imovirtual), use o URL direto do export. Colunas suportadas:
            title, price, location, typology, area_m2, image, link, description.
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={save}
          disabled={saving}
          className="bg-[#0069FE] hover:bg-[#003F99] text-white px-5 py-2 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2"
          data-testid="btn-automation-save"
        >
          {saving && <Loader2 size={14} className="animate-spin" />}
          Guardar
        </button>
      </div>
    </div>
  );
}
