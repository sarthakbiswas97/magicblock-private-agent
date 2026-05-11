"use client";

import { useState } from "react";
import {
  Zap,
  TrendingUp,
  TrendingDown,
  Lock,
  Loader2,
  AlertTriangle,
  Play,
  Square,
  ShieldCheck,
} from "lucide-react";
import type { PipelineResult, PredictionResponse } from "@/lib/types";

interface TradeCardProps {
  pipeline: PipelineResult | null;
  prediction: PredictionResponse | null;
  autoTrading: boolean;
  onExecute: () => Promise<void>;
  onAutoStart: () => Promise<void>;
  onAutoStop: () => Promise<void>;
}

export default function TradeCard({
  pipeline,
  prediction,
  autoTrading,
  onExecute,
  onAutoStart,
  onAutoStop,
}: TradeCardProps) {
  const [executing, setExecuting] = useState(false);

  const handleExecute = async () => {
    setExecuting(true);
    try {
      await onExecute();
    } finally {
      setExecuting(false);
    }
  };

  const pred = prediction?.prediction;
  const isUp = pred?.direction === "UP";

  const execStep = pipeline?.steps.find((s) => s.name === "private_execution");
  const riskStep = pipeline?.steps.find((s) => s.name === "risk_check");
  const settlementStep = pipeline?.steps.find((s) => s.name === "settlement");
  const mevSavings = (settlementStep?.data?.mev_savings as Record<string, unknown>) ?? null;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-gray-200">Trade Execution</h2>
        <div className="flex items-center gap-2">
          <button
            onClick={autoTrading ? onAutoStop : onAutoStart}
            className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border transition-colors ${
              autoTrading
                ? "bg-amber-600/20 text-amber-400 border-amber-500/30 hover:bg-amber-600/30"
                : "bg-gray-800/60 text-gray-400 border-gray-700 hover:bg-gray-800"
            }`}
          >
            {autoTrading ? <Square size={11} /> : <Play size={11} />}
            {autoTrading ? "Stop Auto" : "Auto Trade"}
          </button>
          <button
            onClick={handleExecute}
            disabled={executing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                       bg-emerald-600/20 text-emerald-400 border border-emerald-500/30
                       hover:bg-emerald-600/30 disabled:opacity-50 disabled:cursor-not-allowed
                       transition-colors"
          >
            {executing ? <Loader2 size={14} className="spin-slow" /> : <Zap size={14} />}
            {executing ? "Executing..." : "Execute"}
          </button>
        </div>
      </div>

      {pred && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="rounded-lg bg-gray-900/60 border border-gray-800 p-3">
            <div className="text-[10px] text-gray-500 mb-1">Direction</div>
            <div className={`flex items-center gap-1 text-sm font-semibold ${isUp ? "text-emerald-400" : "text-red-400"}`}>
              {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
              {pred.direction}
            </div>
          </div>
          <div className="rounded-lg bg-gray-900/60 border border-gray-800 p-3">
            <div className="text-[10px] text-gray-500 mb-1">Confidence</div>
            <div className="text-sm font-semibold text-gray-200">
              {(pred.confidence * 100).toFixed(1)}%
            </div>
          </div>
          <div className="rounded-lg bg-gray-900/60 border border-gray-800 p-3">
            <div className="text-[10px] text-gray-500 mb-1">Price</div>
            <div className="text-sm font-semibold text-gray-200">
              ${pred.price.toFixed(2)}
            </div>
          </div>
        </div>
      )}

      {pred?.shap_explanation && (
        <div className="mb-4">
          <div className="text-[10px] text-gray-500 mb-1.5">Top Signal Drivers (SHAP)</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(pred.shap_explanation).map(([feat, info]) => (
              <span
                key={feat}
                className={`text-[10px] px-2 py-0.5 rounded-full border ${
                  info.direction === "pushes UP"
                    ? "bg-emerald-950/30 border-emerald-500/20 text-emerald-400"
                    : "bg-red-950/30 border-red-500/20 text-red-400"
                }`}
              >
                {feat}: {info.value > 0 ? "+" : ""}{info.value.toFixed(3)}
              </span>
            ))}
          </div>
        </div>
      )}

      {pipeline && pipeline.steps.length > 0 && (
        <div className="border-t border-gray-800 pt-3 space-y-2">
          <div className="flex items-center justify-between text-[10px] text-gray-500">
            <span>Pipeline: {pipeline.total_duration_ms.toFixed(0)}ms total</span>
            {execStep?.status === "completed" && (
              <span className="flex items-center gap-1 text-emerald-400">
                <Lock size={10} /> Executed privately via MagicBlock PER
              </span>
            )}
            {execStep?.status === "rejected" && (
              <span className="flex items-center gap-1 text-red-400">
                <AlertTriangle size={10} /> {String(execStep.data.reason ?? "Rejected")}
              </span>
            )}
          </div>

          {riskStep?.status === "completed" && (
            <div className="flex gap-2 text-[10px]">
              <span className="text-gray-500">
                Risk: {((riskStep.data.risk_score as number) * 100).toFixed(1)}%
              </span>
              <span className="text-gray-500">
                Size: {((riskStep.data.position_size_pct as number) * 100).toFixed(2)}%
              </span>
              <span className={riskStep.data.can_trade ? "text-emerald-500" : "text-red-500"}>
                {riskStep.data.can_trade ? "PASSED" : "BLOCKED"}
              </span>
            </div>
          )}

          {mevSavings && (
            <div className="flex items-center gap-2 text-[10px] bg-emerald-950/15 border border-emerald-500/10 rounded-lg px-3 py-1.5">
              <ShieldCheck size={12} className="text-emerald-400 shrink-0" />
              <span className="text-gray-400">MEV savings:</span>
              <span className="text-emerald-400 font-medium">
                ${String((mevSavings as Record<string, unknown>).savings_usd ?? "0")} saved
              </span>
              <span className="text-gray-500">
                (without PER: -${String(((mevSavings as Record<string, unknown>).without_per as Record<string, unknown>)?.estimated_loss_usd ?? "0")} loss)
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
