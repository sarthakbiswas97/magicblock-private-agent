# Phantom Alpha -- Private AI Trading Agent

> **Colosseum Hackathon -- Privacy Track** (Powered by MagicBlock, ST MY & SNS)
>
> An autonomous AI trading agent where every trade signal, risk check, and execution is hidden from MEV bots using MagicBlock's Private Ephemeral Rollups.

**[Demo Video (3 min)](#)** | **[Live Demo](#)** | **[Architecture](#architecture)**

---

## Problem

AI trading agents on Solana leak everything. When an agent submits a trade on-chain, MEV bots see the pending transaction -- the direction, size, timing -- and front-run it. The agent gets worse execution, and its strategy alpha is public for anyone to copy.

This isn't theoretical. MEV extraction on Solana costs traders millions in value annually. For autonomous agents that trade programmatically, every single transaction is visible and exploitable.

## Solution

Phantom Alpha keeps the entire trading pipeline private using MagicBlock's Private Ephemeral Rollup (PER):

```
What MEV bots see:              What actually happens:
                                
  [nothing]                      1. Market data fetched
  [nothing]                      2. 14 technical indicators computed
  [nothing]                      3. XGBoost predicts direction + SHAP explains why
  [nothing]                      4. Risk gate validates position sizing
  [nothing]                      5. Private swap executes inside MagicBlock PER (TEE)
  [settlement only]              6. Final state settles to Solana mainnet
```

Steps 1-5 are invisible. MEV bots only see the settled result -- by then it's too late to front-run.

---

## MagicBlock Integration

This project uses the **Private Payments API** (`payments.magicblock.app`) -- MagicBlock's REST interface to Private Ephemeral Rollups running inside Intel TDX TEE hardware.

### How it works

**Authentication** -- The agent authenticates via challenge-response. It requests a challenge string from `/v1/spl/challenge`, signs it with its Solana keypair, and submits the signature to `/v1/spl/login` to receive a bearer token. All subsequent API calls are auth-gated.

**Private Swap Execution** -- When the AI decides to trade, the agent:
1. Calls `/v1/swap/quote` to get swap pricing between SOL and USDC
2. Calls `/v1/swap` with `visibility: "private"` and `fromBalance: "ephemeral"` to execute the swap inside the PER
3. Signs the returned unsigned transaction with its Solana keypair
4. Submits to the ephemeral rollup -- not to mainnet

The swap executes inside TEE-secured infrastructure. The machine operator, validators, and observers cannot inspect the trade state. Only the final settlement is written to Solana L1.

**Balance Management** -- The agent can:
- `/v1/spl/deposit` -- move tokens from Solana into the ephemeral rollup
- `/v1/spl/private-balance` -- query its shielded balance (auth-gated)
- `/v1/spl/withdraw` -- settle tokens back to Solana mainnet

### Why PER over standard ER

Standard Ephemeral Rollups give performance (sub-10ms, gasless). Private Ephemeral Rollups add **confidentiality** -- the rollup runs inside Intel TDX TEE, so account state and transaction content are encrypted in memory. For a trading agent, this is the difference between "fast execution" and "invisible execution."

---

## Architecture

```
                         PRIVATE BOUNDARY
                    ________________________
                   |                        |
[Birdeye/Jupiter] --> [Feature Engine]       |
       |           |  [ML Prediction]       |
       |           |  [Risk Guardian]       |  --> [MagicBlock PER]
       |           |  [Trade Executor]      |         |
       |           |________________________|         |
       |                    |                    [Solana Mainnet]
       |                    |
  [Next.js Frontend] <------
```

### Backend (Python / FastAPI)

| Service | Purpose |
|---------|---------|
| `core/indicators.py` | 14 technical indicators -- RSI, MACD, ADX, ATR, Bollinger, momentum, volatility regime |
| `services/feature_engine.py` | Computes features from OHLCV candles for ML input |
| `services/prediction_service.py` | XGBoost inference with SHAP explanations for each prediction |
| `services/risk_guardian.py` | Multi-factor risk gate -- position sizing, drawdown throttle, circuit breaker, cooldown |
| `services/magicblock_client.py` | Private Payments API client -- auth, deposit, private swap, withdraw |
| `services/trade_executor.py` | Orchestrates the full 6-step pipeline, tracks privacy status per step |

### Frontend (Next.js / React / Tailwind)

| Component | Purpose |
|-----------|---------|
| `PrivacyPipeline` | Visual 6-node pipeline showing which steps are private vs public |
| `TradeCard` | One-click trade execution with SHAP signal breakdown |
| `PriceChart` | Real-time SOL/USDC candlestick chart |
| `RiskPanel` | Live drawdown, throttle factor, circuit breaker status |
| `MagicBlockStatus` | PER connection status and ephemeral balance |
| `ActivityFeed` | Trade history with privacy annotations |

---

## Demo Flow

1. Backend starts -- loads XGBoost model, fetches SOL/USDC candles, authenticates with MagicBlock
2. Frontend connects -- shows real-time price, agent status, MagicBlock PER connection
3. User clicks **"Execute Private Trade"**:
   - Market data fetched (public, ~1ms)
   - 14 features computed (private, off-chain, ~7ms)
   - XGBoost predicts direction + top 3 SHAP drivers (private, off-chain, ~10ms)
   - Risk gate validates -- position size, drawdown, cooldown (private, off-chain, ~1ms)
   - MagicBlock PER executes private swap (private, TEE, ~5ms)
   - Settlement status recorded (on-chain)
4. Pipeline visualization animates through each step with privacy labels
5. Activity feed shows trade with lock icon indicating private execution

Total pipeline: ~24ms end-to-end.

---

## Judging Criteria Alignment

### Technology (40%)

- **MagicBlock Integration**: Full Private Payments API integration -- challenge-response auth, swap quotes, private swap execution with `visibility: "private"`, ephemeral balance queries
- **Working Demo**: End-to-end pipeline runs in ~24ms. Backend serves real predictions, frontend visualizes each step
- **Architecture**: Clean separation -- pure indicator functions, ML inference, risk validation, MagicBlock client, pipeline orchestrator. Each service is independently testable

### Impact (30%)

- **Real Problem**: MEV front-running costs Solana traders millions. AI agents are especially vulnerable because every trade is programmatic and predictable
- **Market Need**: As autonomous agents proliferate on-chain, private execution becomes a requirement, not a feature
- **Adoption**: Any AI agent framework can integrate the MagicBlock client pattern -- authenticate, quote, swap privately, settle

### Creativity & UX (30%)

- **Novel Primitive**: Combining ML prediction + risk management + private execution in a single pipeline where each step's privacy status is tracked and visualized
- **UX**: One-click private trade with real-time pipeline animation showing exactly what's hidden from MEV bots
- **System Clarity**: The privacy pipeline visualization makes the abstract concept of "private execution" concrete -- users see which steps are shielded and which are public

---

## Track Requirements

- [x] Working demo with MagicBlock integration (Private Payments API)
- [x] Public GitHub repository
- [ ] 3-min demo video: Problem -> Solution -> Demo

---

## Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
cp ../.env.example ../.env  # edit with your keys
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
| `AGENT_KEYPAIR_PATH` | Path to Solana keypair JSON |
| `MAGICBLOCK_API_URL` | MagicBlock Private Payments API URL |
| `MAGICBLOCK_MOCK` | `true` for demo without real API calls |
| `BIRDEYE_API_KEY` | Birdeye API key for historical OHLCV data |
| `SOLANA_RPC_URL` | Solana RPC endpoint |

## Tech Stack

| Layer | Tools |
|-------|-------|
| Backend | Python, FastAPI, XGBoost, SHAP, NumPy |
| Frontend | Next.js 16, React 19, Tailwind CSS 4, lightweight-charts |
| Privacy | MagicBlock Private Ephemeral Rollups (Intel TDX TEE) |
| Blockchain | Solana |
| Data | Birdeye OHLCV, Jupiter/CoinGecko Price API |
