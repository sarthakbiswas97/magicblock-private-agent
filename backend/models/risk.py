from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class RiskLimits(BaseModel):
    max_position_size_pct: float = 0.05
    max_daily_loss_pct: float = 0.03
    max_drawdown_pct: float = 0.10
    min_trade_interval_seconds: int = 60
    max_trades_per_day: int = 50


class RiskState(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_exposure_pct: float = 0.0
    largest_position_pct: float = 0.0
    daily_pnl_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_capital: float = 0.0
    trades_today: int = 0
    last_trade_timestamp: Optional[datetime] = None
    trading_enabled: bool = True
    circuit_breaker_reason: Optional[str] = None


class RiskCheckResult(BaseModel):
    can_trade: bool
    risk_score: float = Field(ge=0, le=1)
    checks: dict[str, bool] = Field(default_factory=dict)
    violations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def passed(cls, risk_score: float, checks: dict) -> "RiskCheckResult":
        return cls(can_trade=True, risk_score=risk_score, checks=checks, violations=[])

    @classmethod
    def failed(cls, violations: list[str], checks: dict) -> "RiskCheckResult":
        return cls(can_trade=False, risk_score=1.0, checks=checks, violations=violations)
