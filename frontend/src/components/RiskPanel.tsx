"use client";

import { ShieldAlert, Activity } from "lucide-react";
import type { RiskStatus } from "@/lib/types";

function RiskBar({ label, value, max, warn }: { label: string; value: number; max: number; warn: number }) {
  const pct = Math.min((value / max) * 100, 100);
  const color = value >= warn ? "bg-red-500" : value >= warn * 0.6 ? "bg-amber-500" : "bg-emerald-500";

  return (
    <div>
      <div className="flex justify-between text-[10px] mb-0.5">
        <span className="text-gray-400">{label}</span>
        <span className="text-gray-300">{value.toFixed(2)}% / {max}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-800 overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

interface RiskPanelProps {
  risk: RiskStatus | null;
}

export default function RiskPanel({ risk }: RiskPanelProps) {
  if (!risk) {
    return (
      <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
        <h2 className="text-sm font-semibold text-gray-200 mb-3">Risk Management</h2>
        <p className="text-xs text-gray-500">Loading...</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
      <div className="flex items-center gap-2 mb-4">
        <ShieldAlert size={14} className="text-violet-400" />
        <h2 className="text-sm font-semibold text-gray-200">Risk Management</h2>
        <span
          className={`ml-auto text-[10px] px-2 py-0.5 rounded-full ${
            risk.trading_enabled
              ? "bg-emerald-950/30 text-emerald-400 border border-emerald-500/20"
              : "bg-red-950/30 text-red-400 border border-red-500/20"
          }`}
        >
          {risk.trading_enabled ? "Active" : "Halted"}
        </span>
      </div>

      <div className="space-y-3">
        <RiskBar label="Drawdown" value={risk.drawdown.current_pct} max={10} warn={8} />
        <RiskBar label="Daily P&L" value={Math.abs(risk.daily.pnl_pct)} max={3} warn={2} />
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <div className="text-center">
          <div className="text-[10px] text-gray-500">Throttle</div>
          <div className="text-sm font-semibold text-gray-200">{(risk.throttle.factor * 100).toFixed(0)}%</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-gray-500">Trades Today</div>
          <div className="text-sm font-semibold text-gray-200">{risk.daily.trades}</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-gray-500">Max DD</div>
          <div className="text-sm font-semibold text-gray-200">{risk.drawdown.max_pct.toFixed(2)}%</div>
        </div>
      </div>

      {risk.circuit_breaker.active && (
        <div className="mt-3 flex items-center gap-1.5 text-[10px] text-red-400 bg-red-950/20 border border-red-500/20 rounded-lg px-3 py-1.5">
          <Activity size={12} />
          Circuit breaker: {risk.circuit_breaker.reason}
        </div>
      )}
    </div>
  );
}
