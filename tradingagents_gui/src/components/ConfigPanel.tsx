import { useState, useEffect, useRef } from "react";
import { Activity, Play, Users, RefreshCw, Plus, Trash2, Eye, EyeOff, BarChart3, RotateCcw, Sparkles, Briefcase } from "lucide-react";
import { Card, Field } from "./ui";
import { api } from "../lib/api";
import {
  ANALYST_OPTIONS,
  apiKeyEnvForProvider,
  defaultModelsForProvider,
  DEPTH_OPTIONS,
  LANGUAGES,
  PROVIDERS,
  getTickerHistory,
  addTickerToHistory,
  latestTradingDate,
  type AnalysisConfig,
  type LLMPlatform,
  type ModelInfo,
} from "../lib/types";
import { useConfigStore } from "../stores/useConfigStore";
import { useAnalysisStore } from "../stores/useAnalysisStore";

interface Props {
  config: AnalysisConfig;
  onChange: (config: AnalysisConfig) => void;
  onAnalyze: (resume?: boolean) => void;
  onMarketData: () => void;
  onScreener: () => void;
  onPortfolio: () => void;
}

// ── localStorage helpers ──────────────────────────────────────────────────────

const MODELS_CACHE_KEY = "tradingagents_models_cache";
const PLATFORM_SELECTIONS_KEY = "tradingagents_platform_selections";

function safeJsonParse<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

function loadModelsCache(): Record<string, ModelInfo[]> {
  return safeJsonParse(MODELS_CACHE_KEY, {});
}

function saveModelsCache(cache: Record<string, ModelInfo[]>) {
  try { localStorage.setItem(MODELS_CACHE_KEY, JSON.stringify(cache)); } catch { /* ignore */ }
}

function loadPlatformSelections(): Record<string, string> {
  return safeJsonParse(PLATFORM_SELECTIONS_KEY, {});
}

function savePlatformSelections(sel: Record<string, string>) {
  try { localStorage.setItem(PLATFORM_SELECTIONS_KEY, JSON.stringify(sel)); } catch { /* ignore */ }
}

// ── ModelSelect ───────────────────────────────────────────────────────────────

function ModelSelect({
  value,
  onChange,
  models,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  models: ModelInfo[];
  placeholder: string;
}) {
  return (
    <div className="flex gap-2">
      <input
        className="input flex-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
      {models.length > 0 && (
        <select
          className="input w-32"
          value=""
          onChange={(e) => {
            if (e.target.value) onChange(e.target.value);
            e.target.value = "";
          }}
        >
          <option value="">选择...</option>
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}

// ── PlatformRow ───────────────────────────────────────────────────────────────

function PlatformRow({
  platform,
  onChange,
  onDelete,
  onFetchModels,
  models,
  loading,
}: {
  platform: LLMPlatform;
  onChange: (p: LLMPlatform) => void;
  onDelete: () => void;
  onFetchModels: () => void;
  models: ModelInfo[];
  loading: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const hasApiKey = !!platform.api_key;
  const hasProxy = !!platform.backend_url;

  return (
    <div className="rounded-md bg-bg-surface/50 border border-line/50">
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-bg-hover/30 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <span className="text-[11px] text-text-muted transition-transform duration-200">
            {expanded ? "▼" : "▶"}
          </span>
          <span className="text-[12px] font-medium text-text-primary">{platform.name}</span>
          <span className="text-[10px] text-text-muted">({platform.provider})</span>
          {hasApiKey && <span className="text-[10px] text-green-400">●</span>}
          {hasProxy && <span className="text-[10px] text-blue-400">●</span>}
        </div>
        <button
          className="btn-ghost !p-1 text-text-muted hover:text-red-400"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          title="删除此平台"
        >
          <Trash2 size={14} />
        </button>
      </div>

      {/* Detail */}
      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-line/30">
          <div className="pt-2">
            <Field label="平台名称">
              <input
                className="input flex-1"
                value={platform.name}
                onChange={(e) => onChange({ ...platform, name: e.target.value })}
                placeholder="平台名称"
              />
            </Field>
          </div>
          <Field label="提供商">
            <select
              className="input w-48"
              value={platform.provider}
              onChange={(e) => onChange({ ...platform, provider: e.target.value })}
            >
              {PROVIDERS.map(([k, n]) => (
                <option key={k} value={k}>{n}</option>
              ))}
            </select>
          </Field>
          <Field label="API Key">
            <input
              type={showKey ? "text" : "password"}
              className="input flex-1"
              value={platform.api_key}
              onChange={(e) => onChange({ ...platform, api_key: e.target.value })}
              placeholder={apiKeyEnvForProvider(platform.provider) || "API Key"}
            />
            <button
              type="button"
              className="btn-ghost !p-1 text-text-muted hover:text-text-primary shrink-0"
              onClick={() => setShowKey(!showKey)}
              title={showKey ? "隐藏" : "显示"}
            >
              {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
            {apiKeyEnvForProvider(platform.provider) && (
              <span className="text-[10px] text-text-muted whitespace-nowrap">
                {apiKeyEnvForProvider(platform.provider)}
              </span>
            )}
          </Field>
          <Field label="代理 URL">
            <input
              className="input flex-1"
              value={platform.backend_url}
              onChange={(e) => onChange({ ...platform, backend_url: e.target.value })}
              placeholder="如 http://host:port/v1 (可选)"
            />
          </Field>
          <div className="flex justify-end pt-1">
            <button
              className="btn-secondary !px-2 !py-0.5 text-[10px]"
              onClick={(e) => {
                e.stopPropagation();
                onFetchModels();
              }}
              disabled={loading}
            >
              <RefreshCw size={10} className={loading ? "animate-spin" : ""} />
              {loading ? "查询中..." : "查询可用模型"}
            </button>
          </div>
          {models.length > 0 && (
            <div className="text-[10px] text-text-muted">
              可用模型: {models.map((m) => m.label).join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── ConfigPanel ───────────────────────────────────────────────────────────────

export default function ConfigPanel({
  config,
  onChange,
  onAnalyze,
  onMarketData,
  onScreener,
  onPortfolio,
}: Props) {
  const backendOnline = useConfigStore((s) => s.backendOnline);
  const backendStatus = useConfigStore((s) => s.backendStatus);
  const testConnection = useConfigStore((s) => s.testConnection);
  const checkpointInfo = useAnalysisStore((s) => s.checkpointInfo);
  const [platformModels, setPlatformModels] = useState<Record<string, ModelInfo[]>>(loadModelsCache);
  const [platformSelections, setPlatformSelections] = useState<Record<string, string>>(loadPlatformSelections);
  const [platformLoading, setPlatformLoading] = useState<Record<string, boolean>>({});
  const [testing, setTesting] = useState(false);
  const [manualTesting, setManualTesting] = useState(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const set = (patch: Partial<AnalysisConfig>) => onChange({ ...config, ...patch });

  const addPlatform = () => {
    const newPlatform: LLMPlatform = {
      id: `platform_${Date.now()}`,
      name: `平台 ${config.llm_platforms.length + 1}`,
      provider: "openai",
      api_key: "",
      backend_url: "",
    };
    set({ llm_platforms: [...config.llm_platforms, newPlatform] });
  };

  const updatePlatform = (index: number, platform: LLMPlatform) => {
    const platforms = [...config.llm_platforms];
    platforms[index] = platform;
    set({ llm_platforms: platforms });
  };

  const deletePlatform = (index: number) => {
    const platformId = config.llm_platforms[index].id;
    const platforms = config.llm_platforms.filter((_, i) => i !== index);
    const quickModel = config.quick_model.platform_id === platformId
      ? { platform_id: "", model: "" }
      : config.quick_model;
    const deepModel = config.deep_model.platform_id === platformId
      ? { platform_id: "", model: "" }
      : config.deep_model;
    const newPlatformModels = { ...platformModels };
    delete newPlatformModels[platformId];
    const newSelections = { ...platformSelections };
    delete newSelections[platformId];
    set({ llm_platforms: platforms, quick_model: quickModel, deep_model: deepModel });
    setPlatformModels(newPlatformModels);
    setPlatformSelections(newSelections);
    saveModelsCache(newPlatformModels);
    savePlatformSelections(newSelections);
  };

  const handleFetchPlatformModels = async (platform: LLMPlatform) => {
    setPlatformLoading((prev) => ({ ...prev, [platform.id]: true }));
    try {
      const m = await api.getModels(
        platform.provider,
        platform.backend_url || undefined,
        platform.api_key || undefined,
      );
      const result = { quick: m.quick, deep: m.deep };
      const updated = { ...platformModels, [platform.id]: result.quick };
      setPlatformModels(updated);
      saveModelsCache(updated);
    } catch (e) {
      console.error("Failed to fetch models:", e);
    } finally {
      setPlatformLoading((prev) => ({ ...prev, [platform.id]: false }));
    }
  };

  const resolveModel = (platformId: string, isQuick: boolean): string => {
    const cached = platformSelections[platformId];
    if (cached) return cached;
    const platform = config.llm_platforms.find((p) => p.id === platformId);
    if (platform) {
      const [q, d] = defaultModelsForProvider(platform.provider);
      return isQuick ? q : d;
    }
    return "";
  };

  const [tickerHistory, setTickerHistory] = useState<string[]>(getTickerHistory);
  const [showHistory, setShowHistory] = useState(false);

  const handleTest = async () => {
    if (manualTesting) return;
    setManualTesting(true);
    setTesting(true);
    await testConnection();
    // Keep the spinner visible briefly so the user sees feedback.
    setTimeout(() => {
      setTesting(false);
      setManualTesting(false);
    }, 800);
  };

  // Cleanup pending timer on unmount.
  useEffect(() => {
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    };
  }, []);

  return (
    <div className="h-full overflow-y-auto spotlight-bg relative">
      <div className="max-w-4xl mx-auto px-8 py-8 relative animate-fade-up">
        <div className="mb-8">
          <span className="chip mb-4 animate-fade-in">
            <Sparkles size={11} className="text-accent" />
            多智能体协同 · 实时行情驱动
          </span>
          <h1 className="text-[30px] font-bold tracking-tight leading-tight">
            <span className="gradient-text">TradingAgents</span>
          </h1>
          <p className="text-[13px] text-text-secondary mt-2 flex items-center gap-1.5 flex-wrap">
            <span>AI 驱动的多智能体股票分析</span>
            {["分析师", "研究", "交易", "风控", "投资决策"].map((step, i) => (
              <span key={step} className="inline-flex items-center gap-1.5">
                {i > 0 && <span className="text-text-muted">→</span>}
                <span className="text-text-secondary/90">{step}</span>
              </span>
            ))}
          </p>
        </div>

        {!backendOnline && backendStatus === "connecting" && (
          <div className="mb-4 rounded-lg border border-blue-400/30 bg-blue-400/10 px-4 py-3 text-[12px] text-blue-300 leading-relaxed flex items-center gap-2">
            <span className="inline-block w-4 h-4 border-2 border-blue-300 border-t-transparent rounded-full animate-spin shrink-0" />
            正在连接后端服务（127.0.0.1:8420）…如果后端刚启动，请稍候。
          </div>
        )}

        {!backendOnline && backendStatus === "failed" && (
          <div className="mb-4 rounded-lg border border-warn/30 bg-warn/15 px-4 py-3 text-[12px] text-warn leading-relaxed">
            ⚠️ 后端服务未响应（127.0.0.1:8420）。请先运行{" "}
            <code className="font-mono">python start_gui.py</code>{" "}
            启动后端，或在项目目录执行{" "}
            <code className="font-mono">python -m granian --interface asgi --host 127.0.0.1 --port 8420 tradingagents_api.server:app</code>
            ，然后点击「测试连接」确认。当前「开始分析」已禁用。
          </div>
        )}

        <Card title="Symbol" className="mb-4" glow>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <Field label="代码">
              <div className="relative">
                <input
                  className="input w-32"
                  value={config.ticker}
                  onChange={(e) => set({ ticker: e.target.value.toUpperCase() })}
                  onFocus={() => { setTickerHistory(getTickerHistory()); setShowHistory(true); }}
                  onBlur={() => setTimeout(() => setShowHistory(false), 200)}
                  placeholder="AAPL"
                />
                {showHistory && tickerHistory.length > 0 && (
                  <div className="absolute z-50 mt-1 w-32 max-h-40 overflow-auto rounded-lg border border-neutral-700 bg-neutral-900 shadow-lg">
                    {tickerHistory.map((t) => (
                      <div
                        key={t}
                        className="cursor-pointer px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 hover:text-white"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          set({ ticker: t });
                          setShowHistory(false);
                        }}
                      >
                        {t}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Field>
            <Field label="日期">
              <input
                type="date"
                className="input w-40"
                value={config.date}
                onChange={(e) => set({ date: e.target.value })}
                max={latestTradingDate()}
              />
            </Field>
            <Field label="语言">
              <select
                className="input w-28"
                value={config.language}
                onChange={(e) => set({ language: e.target.value })}
              >
                {LANGUAGES.map((l) => (
                  <option key={l} value={l}>{l}</option>
                ))}
              </select>
            </Field>
          </div>
        </Card>

        <Card title="分析师团队" className="mb-4" glow>
          <div className="flex flex-wrap gap-3">
            {ANALYST_OPTIONS.map(([key, label]) => {
              const checked = config.analysts.includes(key);
              return (
                <label
                  key={key}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-[3px] border cursor-pointer transition-colors ${
                    checked
                      ? "bg-accent/15 border-accent/40 text-text-primary"
                      : "bg-bg-surface border-line text-text-secondary hover:bg-bg-hover"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="hidden"
                    checked={checked}
                    onChange={() =>
                      set({
                        analysts: checked
                          ? config.analysts.filter((a) => a !== key)
                          : [...config.analysts, key],
                      })
                    }
                  />
                  <Users size={13} className={checked ? "text-accent" : "text-text-muted"} />
                  {label}
                </label>
              );
            })}
          </div>
        </Card>

        <Card title="研究深度" className="mb-4" glow>
          <div className="flex gap-6">
            {DEPTH_OPTIONS.map(([value, label]) => (
              <label
                key={value}
                className={`flex items-center gap-2 cursor-pointer text-[12px] ${
                  config.depth === value ? "text-text-primary" : "text-text-secondary"
                }`}
              >
                <input
                  type="radio"
                  className="hidden"
                  checked={config.depth === value}
                  onChange={() => set({ depth: value })}
                />
                <span
                  className={`w-3.5 h-3.5 rounded-full border flex items-center justify-center ${
                    config.depth === value ? "border-accent" : "border-line"
                  }`}
                >
                  {config.depth === value && (
                    <span className="w-1.5 h-1.5 rounded-full bg-accent" />
                  )}
                </span>
                {label}
              </label>
            ))}
          </div>
        </Card>

        {/* Platform Configuration */}
        <Card title="LLM 平台配置" className="mb-4" glow>
          <div className="space-y-3">
            {config.llm_platforms.map((platform, index) => (
              <PlatformRow
                key={platform.id}
                platform={platform}
                onChange={(p) => updatePlatform(index, p)}
                onDelete={() => deletePlatform(index)}
                onFetchModels={() => handleFetchPlatformModels(platform)}
                models={platformModels[platform.id] || []}
                loading={platformLoading[platform.id] || false}
              />
            ))}
            <button
              className="btn-secondary w-full flex items-center justify-center gap-2"
              onClick={addPlatform}
            >
              <Plus size={14} />
              添加平台
            </button>
          </div>
        </Card>

        {/* Model Selection */}
        <Card title="模型选择" className="mb-8" glow>
          <div className="space-y-4">
            {/* Quick Model */}
            <div className="p-3 rounded-md bg-bg-surface/50 border border-line/50">
              <div className="text-[11px] font-medium text-text-secondary mb-2">
                快速模型 (分析师团队)
              </div>
              <div className="space-y-2">
                <Field label="选择平台">
                  <select
                    className="input w-full"
                    value={config.quick_model.platform_id}
                    onChange={(e) => {
                      const platformId = e.target.value;
                      const model = platformId ? resolveModel(platformId, true) : "";
                      set({ quick_model: { platform_id: platformId, model } });
                    }}
                  >
                    <option value="">请选择平台...</option>
                    {config.llm_platforms.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.provider})
                      </option>
                    ))}
                  </select>
                </Field>
                {config.quick_model.platform_id && (
                  <Field label="模型">
                    <ModelSelect
                      value={config.quick_model.model}
                      onChange={(v) => {
                        set({ quick_model: { ...config.quick_model, model: v } });
                        const updated = { ...platformSelections, [config.quick_model.platform_id]: v };
                        setPlatformSelections(updated);
                        savePlatformSelections(updated);
                      }}
                      models={platformModels[config.quick_model.platform_id] || []}
                      placeholder="输入模型 ID 或从右侧选择"
                    />
                  </Field>
                )}
              </div>
            </div>

            {/* Deep Model */}
            <div className="p-3 rounded-md bg-bg-surface/50 border border-line/50">
              <div className="text-[11px] font-medium text-text-secondary mb-2">
                深度模型 (研究/交易团队)
              </div>
              <div className="space-y-2">
                <Field label="选择平台">
                  <select
                    className="input w-full"
                    value={config.deep_model.platform_id}
                    onChange={(e) => {
                      const platformId = e.target.value;
                      const model = platformId ? resolveModel(platformId, false) : "";
                      set({ deep_model: { platform_id: platformId, model } });
                    }}
                  >
                    <option value="">请选择平台...</option>
                    {config.llm_platforms.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.provider})
                      </option>
                    ))}
                  </select>
                </Field>
                {config.deep_model.platform_id && (
                  <Field label="模型">
                    <ModelSelect
                      value={config.deep_model.model}
                      onChange={(v) => {
                        set({ deep_model: { ...config.deep_model, model: v } });
                        const updated = { ...platformSelections, [config.deep_model.platform_id]: v };
                        setPlatformSelections(updated);
                        savePlatformSelections(updated);
                      }}
                      models={platformModels[config.deep_model.platform_id] || []}
                      placeholder="输入模型 ID 或从右侧选择"
                    />
                  </Field>
                )}
              </div>
            </div>
          </div>
        </Card>

        <div className="flex items-center justify-between">
          <button className="btn-ghost" onClick={handleTest} disabled={testing}>
            <Activity size={13} />
            {backendStatus === "connecting"
              ? "连接中…"
              : testing
                ? "检测中…"
                : "测试连接"}
            <span
              className={`dot ${
                backendOnline ? "bg-up" : backendStatus === "connecting" ? "bg-warn animate-pulse" : "bg-text-muted"
              }`}
              style={{ marginLeft: 4 }}
            />
          </button>

          <button
            className="btn-ghost"
            onClick={onMarketData}
            disabled={!backendOnline || !config.ticker}
          >
            <BarChart3 size={13} />
            查看数据
          </button>

          <button
            className="btn-ghost"
            onClick={onScreener}
            disabled={!backendOnline}
          >
            <Sparkles size={13} />
            选股器
          </button>

          <button
            className="btn-ghost"
            onClick={onPortfolio}
            disabled={!backendOnline}
          >
            <Briefcase size={13} />
            组合
          </button>

          <button
            className="btn-primary !px-8 !py-2.5 text-[13px] font-medium"
            disabled={!backendOnline}
            title={backendOnline ? "" : "后端未运行，请先启动后端"}
            onClick={() => {
              addTickerToHistory(config.ticker);
              setTickerHistory(getTickerHistory());
              onAnalyze();
            }}
          >
            <Play size={14} fill="currentColor" />
            开始分析
          </button>

          {checkpointInfo?.has_checkpoint && (
            <button
              className="btn-ghost !px-4 !py-2.5 text-[13px] font-medium border border-amber-500/40 text-amber-400 hover:bg-amber-500/10"
              disabled={!backendOnline}
              title={`从断点恢复（已完成步骤 ${checkpointInfo.step}）`}
              onClick={() => {
                addTickerToHistory(config.ticker);
                setTickerHistory(getTickerHistory());
                onAnalyze(true);
              }}
            >
              <RotateCcw size={14} />
              继续分析
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
