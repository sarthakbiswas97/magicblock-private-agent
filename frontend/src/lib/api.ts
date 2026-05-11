import { useState, useEffect, useCallback } from "react";
import type {
  AgentStatus,
  PredictionResponse,
  RiskStatus,
  MagicBlockStatus,
  PipelineResult,
  TradeRecord,
  CandleData,
} from "./types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

async function fetchJSON<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export interface AppData {
  agent: AgentStatus | null;
  prediction: PredictionResponse | null;
  risk: RiskStatus | null;
  magicblock: MagicBlockStatus | null;
  pipeline: PipelineResult | null;
  trades: TradeRecord[];
  candles: CandleData[];
  loading: boolean;
}

export function useAppData(): AppData {
  const [data, setData] = useState<AppData>({
    agent: null,
    prediction: null,
    risk: null,
    magicblock: null,
    pipeline: null,
    trades: [],
    candles: [],
    loading: true,
  });

  const poll = useCallback(async () => {
    const [agent, prediction, risk, magicblock, pipeline, tradesRes, candlesRes] =
      await Promise.all([
        fetchJSON<AgentStatus>(`${API}/agent/status`),
        fetchJSON<PredictionResponse>(`${API}/predict`),
        fetchJSON<RiskStatus>(`${API}/risk/status`),
        fetchJSON<MagicBlockStatus>(`${API}/magicblock/status`),
        fetchJSON<PipelineResult>(`${API}/pipeline/latest`),
        fetchJSON<{ trades: TradeRecord[] }>(`${API}/trades/history?limit=20`),
        fetchJSON<{ candles: CandleData[] }>(`${API}/market/candles?limit=200`),
      ]);

    setData({
      agent,
      prediction,
      risk,
      magicblock,
      pipeline,
      trades: tradesRes?.trades ?? [],
      candles: candlesRes?.candles ?? [],
      loading: false,
    });
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, [poll]);

  return data;
}

export async function executeTrade(): Promise<PipelineResult | null> {
  try {
    const res = await fetch(`${API}/trade/execute`, { method: "POST" });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function startAutoTrading(): Promise<boolean> {
  try {
    const res = await fetch(`${API}/trade/auto/start`, { method: "POST" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function stopAutoTrading(): Promise<boolean> {
  try {
    const res = await fetch(`${API}/trade/auto/stop`, { method: "POST" });
    return res.ok;
  } catch {
    return false;
  }
}
