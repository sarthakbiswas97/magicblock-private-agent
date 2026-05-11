# Phantom Alpha -- Private AI Trading Agent

An autonomous AI trading agent that executes SOL/USDC trades privately using MagicBlock's Private Ephemeral Rollups. Trade intents, positions, and strategy signals are hidden from MEV bots and on-chain observers.

## Problem

When an AI agent places a trade on-chain, MEV bots see the pending transaction and front-run it. The agent's strategy signals -- what it's buying, how much, when -- are all public. This results in worse execution prices and leaked alpha.

## Solution

Use MagicBlock's Private Ephemeral Rollup (PER) to execute trades in a TEE-secured environment:

1. **AI predicts** trade direction using XGBoost with 14 technical indicators (off-chain, private)
2. **Risk gate** validates position sizing, drawdown limits, circuit breakers (off-chain, private)
3. **Trade executes** via MagicBlock Private Payments API inside a TEE (private, MEV-protected)
4. **Only settlement** hits Solana mainnet (public)

Steps 1-3 are invisible to MEV bots. The agent's intelligence pipeline is fully shielded.

## Architecture

```
[Jupiter/Birdeye] --> [FastAPI Backend] --> [MagicBlock Private Payments API]
                           |                         |
                      [ML + Risk]              [Solana Mainnet]
                           |
                      [Next.js Frontend]
```

### Backend (Python)
- **ML Model**: XGBoost binary classifier with SHAP explainability
- **Feature Engine**: 14 technical indicators (RSI, MACD, ADX, ATR, Bollinger, etc.)
- **Risk Guardian**: Multi-factor validation with adaptive position sizing, drawdown throttling, circuit breaker
- **MagicBlock Client**: Private Payments API integration (auth, deposit, private swap, withdraw)
- **Trade Executor**: Pipeline orchestrator tracking each step's privacy status

### Frontend (Next.js + TypeScript)
- **Privacy Pipeline**: Visual flow showing which steps are private vs public
- **Trade Card**: One-click private trade execution with SHAP signal explanations
- **Price Chart**: Real-time SOL/USDC candlestick chart
- **Risk Panel**: Live drawdown, throttle, and circuit breaker status
- **MagicBlock Status**: PER connection and ephemeral balance display

## MagicBlock Integration

Uses the **Private Payments API** (`payments.magicblock.app`):

- **Authentication**: Challenge-response with Solana keypair signature
- **Deposit**: Move SPL tokens from Solana into the ephemeral rollup
- **Private Swap**: Execute token swaps with `visibility: "private"` inside the PER (TEE-secured)
- **Withdraw**: Settle back to Solana mainnet
- **Balance**: Query ephemeral balance (auth-gated)

The Private Payments API runs inside Intel TDX TEE hardware, ensuring that even the machine operator cannot inspect trade state.

## Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Solana CLI (for keypair)

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp ../.env.example ../.env
# Edit .env with your keys
python main.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `SOLANA_RPC_URL` | Solana RPC endpoint |
| `AGENT_KEYPAIR_PATH` | Path to Solana keypair JSON |
| `MAGICBLOCK_API_URL` | MagicBlock API URL |
| `MAGICBLOCK_MOCK` | Set `true` for demo without real API |
| `BIRDEYE_API_KEY` | Birdeye API key for historical data |

## Demo Flow

1. Backend starts, loads ML model, fetches 7 days of SOL/USDC candles
2. Frontend connects, displays real-time price and agent status
3. Click "Execute Private Trade":
   - Market data fetched (public)
   - 14 features computed (private, off-chain)
   - XGBoost predicts direction + SHAP explains why (private, off-chain)
   - Risk gate validates trade (private, off-chain)
   - MagicBlock PER executes swap (private, TEE)
   - Settlement recorded (on-chain)
4. Pipeline visualization shows each step with privacy annotations

## Tech Stack

- **Backend**: FastAPI, XGBoost, SHAP, NumPy, httpx, solders
- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, lightweight-charts
- **Privacy**: MagicBlock Private Ephemeral Rollups (Intel TDX TEE)
- **Blockchain**: Solana (Devnet)
- **Data**: Birdeye OHLCV API, Jupiter Price API
