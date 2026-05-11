export interface PipelineStep {
  name: string;
  status: "pending" | "running" | "completed" | "failed" | "rejected" | "skipped";
  data: Record<string, unknown>;
  timestamp: number;
  is_private: boolean;
  duration_ms: number;
}

export interface PipelineResult {
  steps: PipelineStep[];
  executed: boolean;
  trade_id: string | null;
  total_duration_ms: number;
}

export interface AgentStatus {
  agent_name: string;
  status: string;
  latest_price: number;
  symbol: string;
  magicblock_connected: boolean;
  model_loaded: boolean;
}

export interface PredictionResponse {
  prediction: {
    timestamp: number;
    price: number;
    direction: string;
    confidence: number;
    shap_explanation: Record<string, { value: number; direction: string }>;
  };
  features: Record<string, number>;
  model: { status: string; accuracy?: number };
}

export interface RiskStatus {
  drawdown: { current_pct: number; max_pct: number; peak_capital: number };
  throttle: { factor: number };
  circuit_breaker: { active: boolean; reason: string | null };
  daily: { pnl_pct: number; trades: number };
  trading_enabled: boolean;
}

export interface TradesStatus {
  total_trades: number;
  executed_trades: number;
  rejected_trades: number;
  auto_trading: boolean;
  auto_interval_seconds: number;
}

export interface MagicBlockStatus {
  authenticated: boolean;
  mock_mode: boolean;
  wallet: string;
  api_url: string;
  private_balance?: {
    balances: Array<{ mint: string; amount: number; decimals: number }>;
  };
}

export interface TradeRecord {
  trade_id: string;
  timestamp: number;
  direction: string;
  confidence: number;
  position_size_pct: number;
  price: number;
  risk_score: number;
  executed: boolean;
  private: boolean;
  tx_signature: string;
  reject_reason: string;
}

export interface CandleData {
  open_time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}
