"""Pipeline models for tracking private trade execution steps."""

from dataclasses import dataclass, field
import time


@dataclass
class PipelineStep:
    name: str
    status: str  # pending, running, completed, failed, rejected, skipped
    data: dict = field(default_factory=dict)
    timestamp: float = 0.0
    is_private: bool = False
    duration_ms: float = 0.0

    def complete(self, data: dict = None, is_private: bool = False):
        self.status = "completed"
        self.data = data or self.data
        self.is_private = is_private
        self.timestamp = time.time()

    def fail(self, reason: str):
        self.status = "failed"
        self.data["error"] = reason
        self.timestamp = time.time()

    def reject(self, reason: str):
        self.status = "rejected"
        self.data["reason"] = reason
        self.timestamp = time.time()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "data": self.data,
            "timestamp": self.timestamp,
            "is_private": self.is_private,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class PipelineResult:
    steps: list[PipelineStep] = field(default_factory=list)
    executed: bool = False
    trade_id: str | None = None
    total_duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "executed": self.executed,
            "trade_id": self.trade_id,
            "total_duration_ms": round(self.total_duration_ms, 1),
        }
