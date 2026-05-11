"use client";

import { Lock, TrendingUp, TrendingDown, XCircle } from "lucide-react";
import type { TradeRecord } from "@/lib/types";

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

interface ActivityFeedProps {
  trades: TradeRecord[];
}

export default function ActivityFeed({ trades }: ActivityFeedProps) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
      <h2 className="text-sm font-semibold text-gray-200 mb-3">Activity Feed</h2>

      {trades.length === 0 ? (
        <p className="text-xs text-gray-500">No trades yet. Execute a trade to see activity.</p>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {trades.map((t) => (
            <div
              key={t.trade_id}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-[11px] ${
                t.executed
                  ? "border-emerald-500/15 bg-emerald-950/10"
                  : "border-red-500/15 bg-red-950/10"
              }`}
            >
              {t.direction === "UP" ? (
                <TrendingUp size={12} className="text-emerald-400 shrink-0" />
              ) : (
                <TrendingDown size={12} className="text-red-400 shrink-0" />
              )}

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className={t.executed ? "text-emerald-400" : "text-red-400"}>
                    {t.direction}
                  </span>
                  <span className="text-gray-400">
                    {(t.confidence * 100).toFixed(1)}% conf
                  </span>
                  <span className="text-gray-500">@${t.price.toFixed(2)}</span>
                </div>
                {!t.executed && t.reject_reason && (
                  <div className="flex items-center gap-1 text-[9px] text-red-400/70 mt-0.5">
                    <XCircle size={9} />
                    {t.reject_reason}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-1.5 shrink-0">
                {t.private && t.executed && <Lock size={10} className="text-emerald-500/60" />}
                <span className="text-gray-500">{formatTime(t.timestamp)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
