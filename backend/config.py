from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    solana_rpc_url: str = "https://api.devnet.solana.com"
    agent_keypair_path: str = ""

    jupiter_api_url: str = "https://api.jup.ag"
    sol_mint: str = "So11111111111111111111111111111111111111112"
    usdc_mint: str = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    magicblock_api_url: str = "https://payments.magicblock.app"
    magicblock_mock: bool = False

    birdeye_api_key: str = ""

    agent_name: str = "Phantom-Alpha"
    initial_capital: float = 1000.0
    max_position_size: float = 0.05
    max_daily_loss: float = 0.03
    max_drawdown: float = 0.10
    trade_interval_seconds: int = 60

    prediction_threshold: float = 0.50
    confidence_threshold: float = 0.55

    api_host: str = "0.0.0.0"
    api_port: int = 8001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        protected_namespaces = ("settings_",)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
