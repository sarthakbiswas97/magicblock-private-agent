"use client";

import { useCallback, useState } from "react";
import { useAppData, executeTrade } from "@/lib/api";
import PrivacyPipeline from "@/components/PrivacyPipeline";
import TradeCard from "@/components/TradeCard";
import PriceChart from "@/components/PriceChart";
import RiskPanel from "@/components/RiskPanel";
import ActivityFeed from "@/components/ActivityFeed";
import MagicBlockStatus from "@/components/MagicBlockStatus";
import type { PipelineResult } from "@/lib/types";
import { Shield, Brain, Lock } from "lucide-react";

export default function Home() {
  const data = useAppData();
  const [livePipeline, setLivePipeline] = useState<PipelineResult | null>(null);

  const handleExecute = useCallback(async () => {
    const result = await executeTrade();
    if (result) setLivePipeline(result);
  }, []);

  const pipeline = livePipeline ?? data.pipeline;

  return (
    <main className="min-h-screen px-4 py-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="flex items-center gap-2">
            <Shield size={20} className="text-emerald-400" />
            <h1 className="text-lg font-bold text-gray-100">
              {data.agent?.agent_name ?? "Phantom Alpha"}
            </h1>
          </div>

          <div className="flex items-center gap-2 ml-auto">
            {data.agent?.magicblock_connected && (
              <span className="flex items-center gap-1 text-[10px] text-emerald-400 bg-emerald-950/30 border border-emerald-500/20 px-2 py-0.5 rounded-full">
                <Lock size={9} />
                PER Active
              </span>
            )}
            {data.agent?.model_loaded && (
              <span className="flex items-center gap-1 text-[10px] text-amber-400 bg-amber-950/30 border border-amber-500/20 px-2 py-0.5 rounded-full">
                <Brain size={9} />
                ML Ready
              </span>
            )}
            {data.agent?.latest_price ? (
              <span className="text-sm font-mono text-gray-300">
                SOL ${data.agent.latest_price.toFixed(2)}
              </span>
            ) : null}
          </div>
        </div>

        <p className="text-xs text-gray-500">
          MEV-protected AI trading agent powered by MagicBlock Private Ephemeral Rollups
        </p>
        <div className="h-[1px] mt-3 bg-gradient-to-r from-emerald-500/40 via-amber-500/30 to-transparent" />
      </div>

      {/* Pipeline */}
      <div className="mb-5">
        <PrivacyPipeline steps={pipeline?.steps ?? []} />
      </div>

      {/* Trade + Chart row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mb-5">
        <TradeCard
          pipeline={pipeline}
          prediction={data.prediction}
          onExecute={handleExecute}
        />
        <PriceChart
          candles={data.candles}
          latestPrice={data.agent?.latest_price ?? 0}
        />
      </div>

      {/* Risk + MagicBlock + Activity row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <RiskPanel risk={data.risk} />
        <MagicBlockStatus status={data.magicblock} />
        <ActivityFeed trades={data.trades} />
      </div>
    </main>
  );
}
