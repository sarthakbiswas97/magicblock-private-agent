"""Phantom Alpha -- Private AI Trading Agent powered by MagicBlock."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from services.market_data import market_data_service
from services.feature_engine import feature_engine
from services.prediction_service import prediction_service
from services.risk_guardian import risk_guardian
from services.magicblock_client import magicblock_client
from services.trade_executor import trade_executor

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s...", settings.agent_name)

    if prediction_service.load_model():
        logger.info("ML model loaded")
    else:
        logger.warning("ML model not found -- predictions unavailable")

    await market_data_service.start()
    await magicblock_client.initialize()

    logger.info("%s ready", settings.agent_name)
    yield

    logger.info("Shutting down...")
    await market_data_service.stop()
    await magicblock_client.close()


app = FastAPI(title="Phantom Alpha", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "agent": settings.agent_name}


@app.get("/agent/status")
async def agent_status():
    return {
        "agent_name": settings.agent_name,
        "status": "running",
        "latest_price": market_data_service.latest_price,
        "symbol": "SOL/USDC",
        "magicblock_connected": magicblock_client.is_authenticated,
        "model_loaded": prediction_service.model is not None,
    }


@app.get("/market/price")
async def market_price():
    return {
        "symbol": "SOL/USDC",
        "price": market_data_service.latest_price,
    }


@app.get("/market/candles")
async def market_candles(limit: int = 100):
    candles = await market_data_service.get_recent_candles(limit)
    return {
        "symbol": "SOL/USDC",
        "interval": "1m",
        "count": len(candles),
        "candles": [
            {
                "open_time": c.open_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ],
    }


@app.get("/predict")
async def predict():
    features = await feature_engine.compute_features()
    if features is None:
        return {"error": "Insufficient market data for prediction"}

    prediction = prediction_service.predict(features)
    if prediction is None:
        return {"error": "Model not loaded"}

    return {
        "prediction": prediction.to_dict(),
        "features": features.to_dict(),
        "model": prediction_service.get_model_info(),
    }


@app.get("/predict/latest")
async def predict_latest():
    p = prediction_service.latest_prediction
    if p is None:
        return {"error": "No prediction available yet"}
    return {"prediction": p.to_dict()}


@app.get("/risk/status")
async def risk_status():
    return risk_guardian.get_risk_status()


@app.get("/risk/config")
async def risk_config():
    return risk_guardian.get_config()


@app.post("/risk/circuit-breaker/reset")
async def reset_circuit_breaker():
    risk_guardian.reset_circuit_breaker()
    return {"status": "reset"}


@app.get("/magicblock/status")
async def magicblock_status():
    status = magicblock_client.get_status()
    try:
        if magicblock_client.is_authenticated:
            status["private_balance"] = await magicblock_client.get_private_balance()
    except Exception as e:
        status["balance_error"] = str(e)
    return status


@app.post("/trade/execute")
async def execute_trade():
    result = await trade_executor.execute_pipeline()
    return result.to_dict()


@app.get("/pipeline/latest")
async def pipeline_latest():
    if trade_executor.latest_pipeline is None:
        return {"steps": [], "executed": False, "trade_id": None, "total_duration_ms": 0}
    return trade_executor.latest_pipeline.to_dict()


@app.get("/trades/history")
async def trades_history(limit: int = 20):
    trades = trade_executor.trade_history[-limit:]
    return {
        "count": len(trades),
        "trades": [t.to_dict() for t in reversed(trades)],
    }


@app.get("/trades/status")
async def trades_status():
    return trade_executor.get_status()


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
