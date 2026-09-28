/**
 * GoalsPanel — Investment goals progress tracker.
 * Shows each goal with a progress bar and percentage.
 */

import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "../../lib/api";
import type { Goal } from "../../lib/types";
import { Card } from "../ui";

interface Props {
  onRefresh?: () => void;
}

const PRESET_GOALS: Omit<Goal, "id" | "current_value" | "created_at">[] = [
  { name: "总资产", target_value: 1_200_000, unit: "元", deadline: "" },
  { name: "总收益", target_value: 200_000, unit: "元", deadline: "" },
  { name: "收益率", target_value: 20, unit: "%", deadline: "" },
];

function GoalCard({ goal, onDelete }: { goal: Goal; onDelete: (id: string) => void }) {
  const pct = goal.target_value > 0
    ? Math.min(100, (goal.current_value / goal.target_value) * 100)
    : 0;
  const reached = pct >= 100;

  return (
    <div className={`rounded-lg border p-3 transition-colors ${
      reached ? "border-up/40 bg-up/5" : "border-line bg-bg-secondary"
    }`}>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[12px] font-medium text-text-primary">{goal.name}</span>
        <button
          className="text-text-muted hover:text-down transition-colors"
          onClick={() => onDelete(goal.id)}
          title="删除目标"
        >
          <Trash2 size={11} />
        </button>
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-[14px] font-mono text-text-primary">
          {goal.current_value.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </span>
        <span className="text-[11px] text-text-muted">/</span>
        <span className="text-[12px] font-mono text-text-secondary">
          {goal.target_value.toLocaleString(undefined, { maximumFractionDigits: 2 })} {goal.unit}
        </span>
      </div>
      {/* Progress bar */}
      <div className="h-1.5 bg-line rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            reached ? "bg-up" : pct > 60 ? "bg-accent" : "bg-accent/60"
          }`}
          style={{ width: `${Math.min(100, pct)}%` }}
        />
      </div>
      <div className="flex items-center justify-between mt-1">
        <span className={`text-[10px] font-mono ${reached ? "text-up" : "text-text-muted"}`}>
          {pct.toFixed(1)}%
        </span>
        {goal.deadline && (
          <span className="text-[10px] text-text-muted">截止 {goal.deadline}</span>
        )}
      </div>
    </div>
  );
}

export default function GoalsPanel({ onRefresh }: Props) {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newName, setNewName] = useState("");
  const [newTarget, setNewTarget] = useState("");
  const [newUnit, setNewUnit] = useState("元");

  const fetchGoals = useCallback(async () => {
    try {
      const data = await api.getPortfolioGoals();
      setGoals(data);
    } catch {
      // If 404 (no goals yet), start empty
      setGoals([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchGoals(); }, [fetchGoals]);

  const handleAddPreset = useCallback(async (preset: Omit<Goal, "id" | "current_value" | "created_at">) => {
    const updated = await api.setPortfolioGoals([
      ...goals.map((g) => ({ ...g })),
      { ...preset, id: "", current_value: 0, created_at: "" },
    ]);
    setGoals(updated);
    onRefresh?.();
  }, [goals, onRefresh]);

  const handleAddCustom = useCallback(async () => {
    const target = parseFloat(newTarget);
    if (!newName || !target || target <= 0) return;
    const updated = await api.setPortfolioGoals([
      ...goals.map((g) => ({ ...g })),
      { name: newName, target_value: target, unit: newUnit, id: "", current_value: 0, created_at: "", deadline: "" },
    ]);
    setGoals(updated);
    setNewName("");
    setNewTarget("");
    setShowAdd(false);
    onRefresh?.();
  }, [goals, newTarget, newUnit, newName, onRefresh]);

  const handleDelete = useCallback(async (id: string) => {
    const remaining = goals.filter((g) => g.id !== id);
    const updated = await api.setPortfolioGoals(remaining.map((g) => ({ ...g })));
    setGoals(updated);
    onRefresh?.();
  }, [goals, onRefresh]);

  if (loading) {
    return (
      <Card title="目标进度监控">
        <div className="text-[11px] text-text-muted py-4 text-center">加载中...</div>
      </Card>
    );
  }

  return (
    <Card title="目标进度监控">
      <div className="space-y-2">
        {goals.length === 0 && (
          <div className="text-center py-4">
            <div className="text-[11px] text-text-muted mb-3">暂无投资目标，添加一个吧</div>
            <div className="flex flex-wrap gap-1.5 justify-center">
              {PRESET_GOALS.map((preset) => (
                <button
                  key={preset.name}
                  className="text-[10px] px-2 py-1 rounded border border-line text-text-secondary hover:border-accent hover:text-accent transition-colors"
                  onClick={() => handleAddPreset(preset)}
                >
                  + {preset.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {goals.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {goals.map((g) => (
              <GoalCard key={g.id} goal={g} onDelete={handleDelete} />
            ))}
          </div>
        )}

        {goals.length > 0 && (
          <div className="pt-1">
            {showAdd ? (
              <div className="flex items-center gap-1.5">
                <input
                  className="input flex-1 text-[11px]"
                  placeholder="目标名称"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
                <input
                  className="input w-20 text-[11px]"
                  placeholder="目标值"
                  type="number"
                  value={newTarget}
                  onChange={(e) => setNewTarget(e.target.value)}
                />
                <select
                  className="input w-14 text-[11px]"
                  value={newUnit}
                  onChange={(e) => setNewUnit(e.target.value)}
                >
                  <option value="元">元</option>
                  <option value="%">%</option>
                  <option value="股">股</option>
                </select>
                <button
                  className="text-[10px] px-2 py-1 rounded bg-accent text-white hover:bg-accent/80"
                  onClick={handleAddCustom}
                >
                  添加
                </button>
                <button
                  className="text-[10px] px-2 py-1 rounded border border-line text-text-secondary hover:text-text-primary"
                  onClick={() => setShowAdd(false)}
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                className="text-[10px] text-accent hover:underline flex items-center gap-1"
                onClick={() => setShowAdd(true)}
              >
                <Plus size={10} /> 添加自定义目标
              </button>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
