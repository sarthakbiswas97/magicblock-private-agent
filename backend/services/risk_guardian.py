"""Risk Guardian -- validates trades against risk limits. In-memory state."""

import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

from models.risk import RiskState, RiskCheckResult
from config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


@dataclass
class RiskConfig:
    max_position_size_pct: float = 0.05
    max_total_exposure_pct: float = 0.10
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    circuit_breaker_drawdown_pct: float = 0.08
    min_trade_interval_seconds: int = 60
    max_trades_per_day: int = 50
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    max_position_age_seconds: int = 1800
    target_volatility: float = 0.02
    atr_stop_multiplier: float = 2.0
    max_stop_loss_pct: float = 0.03


class RiskGuardian:
    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig(
            max_position_size_pct=settings.max_position_size,
            max_daily_loss_pct=settings.max_daily_loss,
            max_drawdown_pct=settings.max_drawdown,
            min_trade_interval_seconds=settings.trade_interval_seconds,
        )
        self._state = RiskState()
        self._circuit_breaker_active = False

    @property
    def state(self) -> RiskState:
        return self._state

    @property
    def is_trading_enabled(self) -> bool:
        return self._state.trading_enabled and not self._circuit_breaker_active

    def check_trade(
        self,
        action: str,
        position_size_pct: float,
        current_exposure_pct: float,
    ) -> RiskCheckResult:
        checks = {}
        violations = []

        checks["circuit_breaker"] = not self._circuit_breaker_active
        if self._circuit_breaker_active:
            violations.append(f"Circuit breaker active: {self._state.circuit_breaker_reason}")

        checks["trading_enabled"] = self._state.trading_enabled
        if not self._state.trading_enabled:
            violations.append("Trading is disabled")

        checks["position_size"] = position_size_pct <= self.config.max_position_size_pct
        if not checks["position_size"]:
            violations.append(
                f"Position size {position_size_pct:.1%} exceeds limit {self.config.max_position_size_pct:.1%}"
            )

        if action == "BUY":
            new_exposure = current_exposure_pct + position_size_pct
            checks["total_exposure"] = new_exposure <= self.config.max_total_exposure_pct
            if not checks["total_exposure"]:
                violations.append(
                    f"New exposure {new_exposure:.1%} would exceed limit {self.config.max_total_exposure_pct:.1%}"
                )
        else:
            checks["total_exposure"] = True

        checks["daily_loss"] = self._state.daily_pnl_pct >= -self.config.max_daily_loss_pct
        if not checks["daily_loss"]:
            violations.append(
                f"Daily loss {self._state.daily_pnl_pct:.1%} exceeds limit -{self.config.max_daily_loss_pct:.1%}"
            )

        checks["drawdown"] = self._state.current_drawdown_pct <= self.config.max_drawdown_pct
        if not checks["drawdown"]:
            violations.append(
                f"Drawdown {self._state.current_drawdown_pct:.1%} exceeds limit {self.config.max_drawdown_pct:.1%}"
            )

        checks["cooldown"] = self._check_cooldown()
        if not checks["cooldown"]:
            violations.append(
                f"Trade cooldown not met ({self.config.min_trade_interval_seconds}s required)"
            )

        checks["trade_count"] = self._state.trades_today < self.config.max_trades_per_day
        if not checks["trade_count"]:
            violations.append(f"Daily trade limit reached ({self.config.max_trades_per_day})")

        risk_factors = [
            current_exposure_pct / self.config.max_total_exposure_pct,
            abs(self._state.daily_pnl_pct) / self.config.max_daily_loss_pct,
            self._state.current_drawdown_pct / self.config.max_drawdown_pct,
            self._state.trades_today / self.config.max_trades_per_day,
        ]
        risk_score = min(1.0, max(risk_factors))

        can_trade = all(checks.values())

        if can_trade:
            return RiskCheckResult.passed(risk_score, checks)
        return RiskCheckResult.failed(violations, checks)

    def _check_cooldown(self) -> bool:
        if self._state.last_trade_timestamp is None:
            return True

        now = datetime.now(timezone.utc)
        last = self._state.last_trade_timestamp
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        elapsed = (now - last).total_seconds()
        return elapsed >= self.config.min_trade_interval_seconds

    def get_throttle_factor(self) -> float:
        dd = self._state.current_drawdown_pct
        if dd < 0.02:
            return 1.0
        elif dd < 0.04:
            return 0.75
        elif dd < 0.06:
            return 0.50
        elif dd < 0.08:
            return 0.25
        return 0.0

    def calculate_position_size(
        self,
        base_size_pct: float,
        current_volatility: float,
    ) -> float:
        vol_scalar = self.config.target_volatility / max(current_volatility, 0.005)
        vol_scalar = min(max(vol_scalar, 0.5), 2.0)

        throttle = self.get_throttle_factor()
        adjusted_size = base_size_pct * vol_scalar * throttle

        return min(adjusted_size, self.config.max_position_size_pct)

    def calculate_stop_loss_price(self, entry_price: float, atr: float) -> float:
        atr_stop_distance = atr * self.config.atr_stop_multiplier
        max_stop_distance = entry_price * self.config.max_stop_loss_pct
        stop_distance = min(atr_stop_distance, max_stop_distance)
        return entry_price - stop_distance

    def record_trade(self, pnl: float = 0.0):
        now = datetime.now(timezone.utc)
        self._state.last_trade_timestamp = now
        self._state.trades_today += 1
        if pnl != 0.0:
            self._state.daily_pnl_pct += pnl

    def update_equity(self, current_capital: float):
        if self._state.peak_capital <= 0:
            self._state.peak_capital = current_capital

        if current_capital > self._state.peak_capital:
            self._state.peak_capital = current_capital

        if self._state.peak_capital > 0:
            self._state.current_drawdown_pct = (
                (self._state.peak_capital - current_capital) / self._state.peak_capital
            )
            self._state.max_drawdown_pct = max(
                self._state.max_drawdown_pct, self._state.current_drawdown_pct
            )

        if self._state.current_drawdown_pct >= self.config.circuit_breaker_drawdown_pct:
            self._trigger_circuit_breaker(
                f"Drawdown {self._state.current_drawdown_pct:.1%} exceeded "
                f"{self.config.circuit_breaker_drawdown_pct:.0%} limit"
            )

    def _trigger_circuit_breaker(self, reason: str):
        self._circuit_breaker_active = True
        self._state.trading_enabled = False
        self._state.circuit_breaker_reason = reason
        logger.warning("CIRCUIT BREAKER TRIGGERED: %s", reason)

    def reset_circuit_breaker(self):
        self._circuit_breaker_active = False
        self._state.trading_enabled = True
        self._state.circuit_breaker_reason = None

    def get_risk_status(self) -> dict:
        return {
            "drawdown": {
                "current_pct": round(self._state.current_drawdown_pct * 100, 2),
                "max_pct": round(self._state.max_drawdown_pct * 100, 2),
                "peak_capital": round(self._state.peak_capital, 2),
            },
            "throttle": {
                "factor": self.get_throttle_factor(),
            },
            "circuit_breaker": {
                "active": self._circuit_breaker_active,
                "reason": self._state.circuit_breaker_reason,
            },
            "daily": {
                "pnl_pct": round(self._state.daily_pnl_pct * 100, 2),
                "trades": self._state.trades_today,
            },
            "trading_enabled": self.is_trading_enabled,
        }

    def get_config(self) -> dict:
        return {
            "max_position_size_pct": self.config.max_position_size_pct,
            "max_total_exposure_pct": self.config.max_total_exposure_pct,
            "max_daily_loss_pct": self.config.max_daily_loss_pct,
            "max_drawdown_pct": self.config.max_drawdown_pct,
            "circuit_breaker_drawdown_pct": self.config.circuit_breaker_drawdown_pct,
            "min_trade_interval_seconds": self.config.min_trade_interval_seconds,
            "max_trades_per_day": self.config.max_trades_per_day,
        }


risk_guardian = RiskGuardian()
