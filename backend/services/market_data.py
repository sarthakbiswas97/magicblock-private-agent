"""Market data service -- in-memory candle storage, no DB/Redis."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import aiohttp

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SOLUSDC_PAIR = "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2"


@dataclass
class CandleData:
    symbol: str
    interval: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    num_trades: int
    is_closed: bool


class MarketDataService:
    BIRDEYE_BASE_URL = "https://public-api.birdeye.so"
    JUPITER_PRICE_URL = "https://api.jup.ag/price/v2"
    COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"

    def __init__(self, symbol: str = "SOLUSDC"):
        self.symbol = symbol
        self._running = False
        self._http_session: aiohttp.ClientSession | None = None

        self.latest_price: float = 0.0
        self.latest_candle: CandleData | None = None
        self._candles: deque[CandleData] = deque(maxlen=500)

        self._current_candle_start: int = 0
        self._current_open: float = 0.0
        self._current_high: float = 0.0
        self._current_low: float = 0.0
        self._current_close: float = 0.0
        self._current_volume: float = 0.0
        self._current_trades: int = 0

    async def start(self) -> None:
        logger.info("Starting MarketDataService for %s", self.symbol)
        self._http_session = aiohttp.ClientSession()
        await self._fetch_historical_candles(days=7)
        self._running = True
        asyncio.create_task(self._price_poll_loop())
        logger.info("MarketDataService started (%d candles loaded)", len(self._candles))

    async def stop(self) -> None:
        self._running = False
        if self._http_session:
            await self._http_session.close()
            self._http_session = None

    async def get_recent_candles(self, limit: int = 100) -> list[CandleData]:
        closed = [c for c in self._candles if c.is_closed]
        return closed[-limit:]

    async def _fetch_historical_candles(self, days: int = 7) -> None:
        logger.info("Fetching %d days of historical candles from Birdeye...", days)
        if not self._http_session:
            return

        now = int(datetime.now(tz=timezone.utc).timestamp())
        start = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())
        headers = self._birdeye_headers()
        current_start = start

        while current_start < now:
            url = f"{self.BIRDEYE_BASE_URL}/defi/ohlcv"
            params = {
                "address": _SOLUSDC_PAIR,
                "type": "1m",
                "time_from": current_start,
                "time_to": min(current_start + 86400, now),
            }

            try:
                async with self._http_session.get(url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        logger.warning("Birdeye API error %d", resp.status)
                        break

                    body = await resp.json()
                    items = body.get("data", {}).get("items", [])

                    if not items:
                        current_start += 86400
                        continue

                    for item in items:
                        open_time_ms = int(item["unixTime"]) * 1000
                        candle = CandleData(
                            symbol=self.symbol,
                            interval="1m",
                            open_time=open_time_ms,
                            close_time=open_time_ms + 59999,
                            open=float(item["o"]),
                            high=float(item["h"]),
                            low=float(item["l"]),
                            close=float(item["c"]),
                            volume=float(item.get("v", 0)),
                            quote_volume=float(item.get("v", 0)),
                            num_trades=0,
                            is_closed=True,
                        )
                        self._candles.append(candle)

                    last_ts = int(items[-1]["unixTime"])
                    current_start = last_ts + 60

            except Exception as e:
                logger.error("Error fetching Birdeye candles: %s", e)
                break

            await asyncio.sleep(0.2)

        if not self._candles:
            logger.info("No historical candles -- generating synthetic data for demo")
            await self._generate_synthetic_candles()

        if self._candles:
            self.latest_price = self._candles[-1].close

    async def _generate_synthetic_candles(self) -> None:
        """Generate realistic synthetic 1m candles for demo when no API key."""
        import random
        random.seed(42)

        base_price = 170.0
        now_ms = int(time.time() * 1000)
        num_candles = 200

        price = base_price
        for i in range(num_candles):
            candle_time = now_ms - (num_candles - i) * 60_000
            change_pct = random.gauss(0, 0.002)
            price *= (1 + change_pct)

            high = price * (1 + abs(random.gauss(0, 0.001)))
            low = price * (1 - abs(random.gauss(0, 0.001)))
            open_price = price * (1 + random.gauss(0, 0.0005))
            volume = random.uniform(50_000, 500_000)

            candle = CandleData(
                symbol=self.symbol,
                interval="1m",
                open_time=candle_time,
                close_time=candle_time + 59999,
                open=open_price,
                high=max(high, open_price, price),
                low=min(low, open_price, price),
                close=price,
                volume=volume,
                quote_volume=volume,
                num_trades=random.randint(10, 200),
                is_closed=True,
            )
            self._candles.append(candle)

        self.latest_price = price
        logger.info("Generated %d synthetic candles (price ~$%.2f)", num_candles, price)

    async def _price_poll_loop(self) -> None:
        poll_interval = 5
        reconnect_delay = 1

        while self._running:
            try:
                await self._poll_price()
                reconnect_delay = 1
                await asyncio.sleep(poll_interval)
            except Exception as e:
                logger.error("Price poll error: %s", e)
                if self._running:
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 60)

    async def _poll_price(self) -> None:
        if not self._http_session:
            return

        price = await self._fetch_jupiter_price()
        if price is None:
            price = await self._fetch_coingecko_price()
        if price is None:
            return

        now_ms = int(time.time() * 1000)
        self.latest_price = price
        self._accumulate_candle(price, now_ms)

    async def _fetch_jupiter_price(self) -> float | None:
        try:
            params = {"ids": settings.sol_mint}
            async with self._http_session.get(self.JUPITER_PRICE_URL, params=params) as resp:
                if resp.status != 200:
                    return None
                body = await resp.json()
                sol_data = body.get("data", {}).get(settings.sol_mint)
                if not sol_data:
                    return None
                return float(sol_data["price"])
        except Exception:
            return None

    async def _fetch_coingecko_price(self) -> float | None:
        try:
            params = {"ids": "solana", "vs_currencies": "usd"}
            async with self._http_session.get(self.COINGECKO_PRICE_URL, params=params) as resp:
                if resp.status != 200:
                    return None
                body = await resp.json()
                return float(body.get("solana", {}).get("usd", 0))
        except Exception:
            return None

    def _accumulate_candle(self, price: float, now_ms: int) -> None:
        minute_start = (now_ms // 60_000) * 60_000

        if minute_start != self._current_candle_start:
            if self._current_candle_start > 0:
                closed_candle = CandleData(
                    symbol=self.symbol,
                    interval="1m",
                    open_time=self._current_candle_start,
                    close_time=self._current_candle_start + 59999,
                    open=self._current_open,
                    high=self._current_high,
                    low=self._current_low,
                    close=self._current_close,
                    volume=self._current_volume,
                    quote_volume=self._current_volume,
                    num_trades=self._current_trades,
                    is_closed=True,
                )
                self._candles.append(closed_candle)
                self.latest_candle = closed_candle

            self._current_candle_start = minute_start
            self._current_open = price
            self._current_high = price
            self._current_low = price
            self._current_close = price
            self._current_volume = 0.0
            self._current_trades = 0
        else:
            self._current_high = max(self._current_high, price)
            self._current_low = min(self._current_low, price)
            self._current_close = price
            self._current_trades += 1

    def _birdeye_headers(self) -> dict[str, str]:
        headers = {"accept": "application/json"}
        if settings.birdeye_api_key:
            headers["X-API-KEY"] = settings.birdeye_api_key
        return headers


market_data_service = MarketDataService()
