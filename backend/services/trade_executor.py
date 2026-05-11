"""Private trade executor -- orchestrates the full MEV-protected trading pipeline."""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from config import get_settings
from models.pipeline import PipelineStep, PipelineResult
from .market_data import market_data_service
from .feature_engine import feature_engine, FeatureVector
from .prediction_service import prediction_service, Prediction
from .risk_guardian import risk_guardian
from .magicblock_client import magicblock_client

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_POSITION_SIZE_PCT = 0.03
ENTRY_CONFIDENCE_THRESHOLD = float(get_settings().prediction_threshold)


@dataclass
class TradeRecord:
    trade_id: str
    timestamp: float
    direction: str
    confidence: float
    position_size_pct: float
    price: float
    risk_score: float
    executed: bool
    private: bool
    tx_signature: str = ""
    reject_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "trade_id": self.trade_id,
            "timestamp": self.timestamp,
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "position_size_pct": round(self.position_size_pct, 4),
            "price": round(self.price, 4),
            "risk_score": round(self.risk_score, 4),
            "executed": self.executed,
            "private": self.private,
            "tx_signature": self.tx_signature,
            "reject_reason": self.reject_reason,
        }


class PrivateTradeExecutor:
    AUTO_TRADE_INTERVAL = 90  # seconds between auto-trades

    def __init__(self):
        self.trade_history: list[TradeRecord] = []
        self.latest_pipeline: Optional[PipelineResult] = None
        self._auto_running = False
        self._auto_task: Optional[asyncio.Task] = None

    async def start_auto_trading(self) -> None:
        if self._auto_running:
            return
        self._auto_running = True
        self._auto_task = asyncio.create_task(self._auto_trade_loop())
        logger.info("Auto-trading started (interval: %ds)", self.AUTO_TRADE_INTERVAL)

    async def stop_auto_trading(self) -> None:
        self._auto_running = False
        if self._auto_task:
            self._auto_task.cancel()
            self._auto_task = None
        logger.info("Auto-trading stopped")

    async def _auto_trade_loop(self) -> None:
        while self._auto_running:
            try:
                await self.execute_pipeline()
            except Exception as e:
                logger.error("Auto-trade cycle failed: %s", e)
            await asyncio.sleep(self.AUTO_TRADE_INTERVAL)

    async def execute_pipeline(self) -> PipelineResult:
        """Run one full private trading cycle."""
        pipeline_start = time.time()
        steps: list[PipelineStep] = []
        trade_id = str(uuid.uuid4())[:8]

        # Step 1: Market Data (public)
        step = PipelineStep(name="market_data", status="running")
        t0 = time.time()
        try:
            candles = await market_data_service.get_recent_candles(150)
            price = market_data_service.latest_price
            if not candles or price <= 0:
                step.fail("No market data available")
                steps.append(step)
                return self._finalize(steps, pipeline_start, trade_id, executed=False)

            step.complete(
                {"price": round(price, 4), "candles": len(candles)},
                is_private=False,
            )
            step.duration_ms = (time.time() - t0) * 1000
        except Exception as e:
            step.fail(str(e))
            step.duration_ms = (time.time() - t0) * 1000
            steps.append(step)
            return self._finalize(steps, pipeline_start, trade_id, executed=False)
        steps.append(step)

        # Step 2: Feature Computation (private -- off-chain)
        step = PipelineStep(name="features", status="running")
        t0 = time.time()
        try:
            features = await feature_engine.compute_features(candles)
            if features is None:
                step.fail("Insufficient data for feature computation")
                step.duration_ms = (time.time() - t0) * 1000
                steps.append(step)
                return self._finalize(steps, pipeline_start, trade_id, executed=False)

            step.complete(
                {
                    "count": 14,
                    "rsi": round(features.rsi, 2),
                    "volatility": round(features.volatility, 6),
                    "momentum": round(features.momentum, 6),
                },
                is_private=True,
            )
            step.duration_ms = (time.time() - t0) * 1000
        except Exception as e:
            step.fail(str(e))
            step.duration_ms = (time.time() - t0) * 1000
            steps.append(step)
            return self._finalize(steps, pipeline_start, trade_id, executed=False)
        steps.append(step)

        # Step 3: ML Prediction (private -- off-chain)
        step = PipelineStep(name="prediction", status="running")
        t0 = time.time()
        prediction = prediction_service.predict(features)
        if prediction is None:
            step.fail("Model not loaded")
            step.duration_ms = (time.time() - t0) * 1000
            steps.append(step)
            return self._finalize(steps, pipeline_start, trade_id, executed=False)

        step.complete(
            {
                "direction": prediction.direction,
                "confidence": round(prediction.confidence, 4),
                "shap_explanation": prediction.shap_explanation,
            },
            is_private=True,
        )
        step.duration_ms = (time.time() - t0) * 1000
        steps.append(step)

        # Step 4: Risk Check (private -- off-chain)
        step = PipelineStep(name="risk_check", status="running")
        t0 = time.time()
        position_size = risk_guardian.calculate_position_size(
            BASE_POSITION_SIZE_PCT, features.volatility
        )
        action = "BUY" if prediction.direction == "UP" else "SELL"
        risk_result = risk_guardian.check_trade(action, position_size, 0.0)

        step.complete(
            {
                "can_trade": risk_result.can_trade,
                "risk_score": round(risk_result.risk_score, 4),
                "position_size_pct": round(position_size, 4),
                "violations": risk_result.violations,
                "action": action,
            },
            is_private=True,
        )
        step.duration_ms = (time.time() - t0) * 1000
        steps.append(step)

        # Gate: confidence + risk check
        if not risk_result.can_trade:
            step = PipelineStep(name="private_execution", status="rejected")
            step.reject("Risk check failed: " + "; ".join(risk_result.violations))
            steps.append(step)
            self._record_trade(
                trade_id, prediction, position_size, price,
                risk_result.risk_score, executed=False,
                reject_reason="; ".join(risk_result.violations),
            )
            return self._finalize(steps, pipeline_start, trade_id, executed=False)

        if prediction.confidence < ENTRY_CONFIDENCE_THRESHOLD:
            step = PipelineStep(name="private_execution", status="rejected")
            step.reject(
                f"Confidence {prediction.confidence:.2%} below threshold {ENTRY_CONFIDENCE_THRESHOLD:.0%}"
            )
            steps.append(step)
            self._record_trade(
                trade_id, prediction, position_size, price,
                risk_result.risk_score, executed=False,
                reject_reason=f"Low confidence: {prediction.confidence:.2%}",
            )
            return self._finalize(steps, pipeline_start, trade_id, executed=False)

        # Step 5: Private Execution via MagicBlock PER
        # Full lifecycle: deposit -> private swap -> withdraw
        step = PipelineStep(name="private_execution", status="running")
        t0 = time.time()
        try:
            input_mint = settings.usdc_mint if action == "BUY" else settings.sol_mint
            output_mint = settings.sol_mint if action == "BUY" else settings.usdc_mint

            amount_usd = settings.initial_capital * position_size
            if action == "BUY":
                amount_raw = int(amount_usd * 1_000_000)
            else:
                amount_raw = int((amount_usd / price) * 1_000_000_000)

            # 5a: Deposit tokens into ephemeral rollup
            deposit_result = await magicblock_client.deposit(input_mint, amount_raw)

            # 5b: Execute private swap inside PER
            quote = await magicblock_client.get_swap_quote(input_mint, output_mint, amount_raw)
            swap_result = await magicblock_client.execute_private_swap(quote)

            # 5c: Withdraw output tokens back to mainnet
            withdraw_result = await magicblock_client.withdraw(output_mint, quote.out_amount)

            if swap_result.success:
                step.complete(
                    {
                        "action": action,
                        "input_mint": input_mint[:8] + "...",
                        "output_mint": output_mint[:8] + "...",
                        "in_amount": quote.in_amount,
                        "out_amount": quote.out_amount,
                        "lifecycle": {
                            "deposit": deposit_result.signature,
                            "swap": swap_result.signature,
                            "withdraw": withdraw_result.signature,
                        },
                        "visibility": "private",
                        "execution_layer": "MagicBlock PER (TEE)",
                    },
                    is_private=True,
                )
                risk_guardian.record_trade()
            else:
                step.fail(f"Swap failed: {swap_result.error}")

            step.duration_ms = (time.time() - t0) * 1000

        except Exception as e:
            step.fail(str(e))
            step.duration_ms = (time.time() - t0) * 1000

        steps.append(step)

        executed = step.status == "completed"

        # Step 6: Settlement with MEV comparison
        step = PipelineStep(name="settlement", status="running")
        if executed:
            mev_estimate = self._estimate_mev_loss(price, position_size)
            step.complete(
                {
                    "settled_to": "Solana Mainnet",
                    "mev_protected": True,
                    "mev_savings": mev_estimate,
                    "note": "Only final settlement visible on-chain",
                },
                is_private=False,
            )
        else:
            step.status = "skipped"
            step.data = {"reason": "Trade not executed"}
        steps.append(step)

        self._record_trade(
            trade_id, prediction, position_size, price,
            risk_result.risk_score, executed=executed,
            tx_signature=steps[-2].data.get("tx_signature", "") if executed and len(steps) >= 2 else "",
        )

        return self._finalize(steps, pipeline_start, trade_id, executed=executed)

    def _finalize(
        self,
        steps: list[PipelineStep],
        start_time: float,
        trade_id: str,
        executed: bool,
    ) -> PipelineResult:
        result = PipelineResult(
            steps=steps,
            executed=executed,
            trade_id=trade_id,
            total_duration_ms=(time.time() - start_time) * 1000,
        )
        self.latest_pipeline = result
        return result

    def _record_trade(
        self,
        trade_id: str,
        prediction: Prediction,
        position_size: float,
        price: float,
        risk_score: float,
        executed: bool,
        tx_signature: str = "",
        reject_reason: str = "",
    ):
        record = TradeRecord(
            trade_id=trade_id,
            timestamp=time.time(),
            direction=prediction.direction,
            confidence=prediction.confidence,
            position_size_pct=position_size,
            price=price,
            risk_score=risk_score,
            executed=executed,
            private=True,
            tx_signature=tx_signature,
            reject_reason=reject_reason,
        )
        self.trade_history.append(record)
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]

    @staticmethod
    def _estimate_mev_loss(price: float, position_size_pct: float) -> dict:
        """Estimate MEV loss if this trade were executed on public mainnet."""
        trade_value_usd = settings.initial_capital * position_size_pct
        sandwich_slippage_bps = 30
        frontrun_slippage_bps = 15
        estimated_loss_usd = trade_value_usd * (sandwich_slippage_bps + frontrun_slippage_bps) / 10_000

        return {
            "without_per": {
                "sandwich_attack_bps": sandwich_slippage_bps,
                "frontrun_slippage_bps": frontrun_slippage_bps,
                "estimated_loss_usd": round(estimated_loss_usd, 4),
            },
            "with_per": {
                "mev_exposure_bps": 0,
                "estimated_loss_usd": 0.0,
            },
            "savings_usd": round(estimated_loss_usd, 4),
        }

    def get_status(self) -> dict:
        total = len(self.trade_history)
        executed = sum(1 for t in self.trade_history if t.executed)
        total_savings = sum(
            t.to_dict().get("mev_savings", 0)
            for t in self.trade_history if t.executed
        )
        return {
            "total_trades": total,
            "executed_trades": executed,
            "rejected_trades": total - executed,
            "auto_trading": self._auto_running,
            "auto_interval_seconds": self.AUTO_TRADE_INTERVAL,
            "latest_pipeline": self.latest_pipeline.to_dict() if self.latest_pipeline else None,
        }


trade_executor = PrivateTradeExecutor()
