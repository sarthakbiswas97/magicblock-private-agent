"""Prediction service -- ML model inference with SHAP explanations."""

import numpy as np
import joblib
import shap
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from .feature_engine import FeatureVector

MODEL_PATH = Path(__file__).parent.parent.parent / "ml" / "models" / "model_bundle_latest.joblib"


@dataclass
class Prediction:
    timestamp: int
    price: float
    direction: str
    confidence: float
    shap_explanation: dict

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "price": self.price,
            "direction": self.direction,
            "confidence": round(self.confidence, 4),
            "shap_explanation": self.shap_explanation,
        }


class PredictionService:
    def __init__(self):
        self.model = None
        self.metadata = None
        self.explainer = None
        self.feature_order: list[str] = []
        self.latest_prediction: Optional[Prediction] = None

    def load_model(self, model_path: Path = MODEL_PATH) -> bool:
        if not model_path.exists():
            print(f"Model not found at {model_path}")
            return False

        try:
            bundle = joblib.load(model_path)
            self.model = bundle["model"]
            self.metadata = bundle["metadata"]
            self.feature_order = self.metadata["features"]
            self.explainer = shap.TreeExplainer(self.model)

            print(f"Model loaded: v{self.metadata['version']}")
            print(f"  Accuracy: {self.metadata['results']['accuracy']:.2%}")
            return True
        except Exception as e:
            print(f"Failed to load model: {e}")
            return False

    def predict(self, features: FeatureVector) -> Optional[Prediction]:
        if self.model is None:
            return None

        feature_values = np.array([[
            features.rsi,
            features.macd,
            features.macd_signal,
            features.macd_histogram,
            features.ema_ratio,
            features.volatility,
            features.volume_spike,
            features.momentum,
            features.bollinger_position,
            features.adx,
            features.atr,
            features.volatility_regime,
            features.price_acceleration,
            features.range_position,
        ]])

        pred_class = self.model.predict(feature_values)[0]
        pred_proba = self.model.predict_proba(feature_values)[0]

        direction = "UP" if pred_class == 1 else "DOWN"
        confidence = float(pred_proba[1] if pred_class == 1 else pred_proba[0])

        shap_values = self.explainer.shap_values(feature_values)[0]
        shap_pairs = list(zip(self.feature_order, shap_values))
        shap_sorted = sorted(shap_pairs, key=lambda x: abs(x[1]), reverse=True)[:3]

        shap_explanation = {
            feat: {
                "value": round(float(shap_val), 4),
                "direction": "pushes UP" if shap_val > 0 else "pushes DOWN",
            }
            for feat, shap_val in shap_sorted
        }

        prediction = Prediction(
            timestamp=features.timestamp,
            price=features.price,
            direction=direction,
            confidence=confidence,
            shap_explanation=shap_explanation,
        )

        self.latest_prediction = prediction
        return prediction

    def get_model_info(self) -> dict:
        if self.metadata is None:
            return {"status": "not_loaded"}

        return {
            "status": "loaded",
            "version": self.metadata["version"],
            "accuracy": self.metadata["results"]["accuracy"],
            "features": self.feature_order,
        }


prediction_service = PredictionService()
