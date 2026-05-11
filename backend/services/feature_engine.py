"""Feature engine -- computes technical indicators from candle data."""

import numpy as np
from dataclasses import dataclass
from typing import Optional

from .market_data import CandleData, market_data_service
from core.indicators import compute_all_features, MIN_CANDLES


@dataclass
class FeatureVector:
    timestamp: int
    price: float

    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    ema_ratio: float
    volatility: float
    volume_spike: float
    momentum: float
    bollinger_position: float

    adx: float = 25.0
    atr: float = 0.0
    volatility_regime: float = 0.5
    price_acceleration: float = 0.0
    range_position: float = 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "price": self.price,
            "rsi": round(self.rsi, 2),
            "macd": round(self.macd, 6),
            "macd_signal": round(self.macd_signal, 6),
            "macd_histogram": round(self.macd_histogram, 6),
            "ema_ratio": round(self.ema_ratio, 4),
            "volatility": round(self.volatility, 6),
            "volume_spike": round(self.volume_spike, 4),
            "momentum": round(self.momentum, 6),
            "bollinger_position": round(self.bollinger_position, 4),
            "adx": round(self.adx, 2),
            "atr": round(self.atr, 4),
            "volatility_regime": round(self.volatility_regime, 4),
            "price_acceleration": round(self.price_acceleration, 6),
            "range_position": round(self.range_position, 4),
        }

    @classmethod
    def from_dict(cls, data: dict, timestamp: int) -> "FeatureVector":
        return cls(
            timestamp=timestamp,
            price=data["price"],
            rsi=data["rsi"],
            macd=data["macd"],
            macd_signal=data["macd_signal"],
            macd_histogram=data["macd_histogram"],
            ema_ratio=data["ema_ratio"],
            volatility=data["volatility"],
            volume_spike=data["volume_spike"],
            momentum=data["momentum"],
            bollinger_position=data["bollinger_position"],
            adx=data.get("adx", 25.0),
            atr=data.get("atr", 0.0),
            volatility_regime=data.get("volatility_regime", 0.5),
            price_acceleration=data.get("price_acceleration", 0.0),
            range_position=data.get("range_position", 0.0),
        )


class FeatureEngine:
    def __init__(self):
        self.latest_features: Optional[FeatureVector] = None

    async def compute_features(self, candles: list[CandleData] = None) -> Optional[FeatureVector]:
        if candles is None:
            candles = await market_data_service.get_recent_candles(limit=150)

        if len(candles) < MIN_CANDLES:
            return None

        closes = np.array([c.close for c in candles])
        highs = np.array([c.high for c in candles])
        lows = np.array([c.low for c in candles])
        volumes = np.array([c.volume for c in candles])

        features_dict = compute_all_features(
            closes, volumes, highs, lows, include_regime=True
        )

        features = FeatureVector.from_dict(features_dict, timestamp=candles[-1].close_time)
        self.latest_features = features
        return features


feature_engine = FeatureEngine()
