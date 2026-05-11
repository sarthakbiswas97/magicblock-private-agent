"""MagicBlock Private Payments API client.

Handles authentication, deposits, private swaps, and withdrawals
through MagicBlock's Private Ephemeral Rollup infrastructure.
"""

import base64
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SwapQuote:
    input_mint: str
    output_mint: str
    in_amount: int
    out_amount: int
    price_impact: float
    raw: dict = field(default_factory=dict)


@dataclass
class TransactionResult:
    success: bool
    signature: str = ""
    error: str = ""


class MagicBlockClient:
    """Client for MagicBlock Private Payments API."""

    def __init__(self):
        self._base_url = settings.magicblock_api_url
        self._keypair: Optional[Keypair] = None
        self._bearer_token: Optional[str] = None
        self._token_acquired_at: float = 0.0
        self._http: Optional[httpx.AsyncClient] = None
        self._solana_rpc: Optional[AsyncClient] = None
        self._mock_mode = settings.magicblock_mock
        self._authenticated = False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated or self._mock_mode

    @property
    def wallet_address(self) -> str:
        if self._keypair:
            return str(self._keypair.pubkey())
        return ""

    async def initialize(self) -> bool:
        if self._mock_mode:
            logger.info("MagicBlock client running in MOCK mode")
            self._authenticated = True
            return True

        keypair_path = settings.agent_keypair_path
        if not keypair_path:
            logger.warning("No agent_keypair_path configured, running in mock mode")
            self._mock_mode = True
            self._authenticated = True
            return True

        try:
            path = Path(keypair_path).expanduser()
            with open(path) as f:
                secret = json.load(f)
            self._keypair = Keypair.from_bytes(bytes(secret))
            logger.info("Loaded keypair: %s", self._keypair.pubkey())
        except Exception as e:
            logger.error("Failed to load keypair: %s", e)
            self._mock_mode = True
            self._authenticated = True
            return True

        self._http = httpx.AsyncClient(timeout=30.0)
        self._solana_rpc = AsyncClient(settings.solana_rpc_url)

        try:
            await self._authenticate()
            return True
        except Exception as e:
            logger.error("MagicBlock auth failed: %s -- falling back to mock", e)
            self._mock_mode = True
            self._authenticated = True
            return True

    async def close(self):
        if self._http:
            await self._http.aclose()
        if self._solana_rpc:
            await self._solana_rpc.close()

    async def _authenticate(self) -> None:
        """Authenticate with MagicBlock Private Payments API."""
        pubkey = str(self._keypair.pubkey())

        resp = await self._http.get(
            f"{self._base_url}/v1/spl/challenge",
            params={"pubkey": pubkey},
        )
        resp.raise_for_status()
        challenge = resp.json().get("challenge", resp.text)
        if isinstance(challenge, dict):
            challenge = challenge.get("challenge", str(challenge))

        challenge_bytes = challenge.encode("utf-8")
        signature = self._keypair.sign_message(challenge_bytes)
        sig_b64 = base64.b64encode(bytes(signature)).decode("utf-8")

        resp = await self._http.post(
            f"{self._base_url}/v1/spl/login",
            json={
                "pubkey": pubkey,
                "challenge": challenge,
                "signature": sig_b64,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._bearer_token = data.get("token", data.get("access_token", ""))
        self._token_acquired_at = time.time()
        self._authenticated = True
        logger.info("MagicBlock authenticated for %s", pubkey)

    def _auth_headers(self) -> dict:
        if self._bearer_token:
            return {"Authorization": f"Bearer {self._bearer_token}"}
        return {}

    async def _ensure_auth(self) -> None:
        if self._mock_mode:
            return
        elapsed = time.time() - self._token_acquired_at
        if elapsed > 3000:
            await self._authenticate()

    async def get_balance(self) -> dict:
        if self._mock_mode:
            return self._mock_balance()

        await self._ensure_auth()
        resp = await self._http.get(
            f"{self._base_url}/v1/spl/balance",
            params={"pubkey": self.wallet_address},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_private_balance(self) -> dict:
        if self._mock_mode:
            return self._mock_private_balance()

        await self._ensure_auth()
        resp = await self._http.get(
            f"{self._base_url}/v1/spl/private-balance",
            headers=self._auth_headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def deposit(self, mint: str, amount: int) -> TransactionResult:
        """Deposit SPL tokens from Solana mainnet into ephemeral rollup."""
        if self._mock_mode:
            return self._mock_tx_result("deposit")

        await self._ensure_auth()
        resp = await self._http.post(
            f"{self._base_url}/v1/spl/deposit",
            headers=self._auth_headers(),
            json={
                "from": self.wallet_address,
                "mint": mint,
                "amount": amount,
            },
        )
        resp.raise_for_status()
        return await self._sign_and_submit(resp.json())

    async def get_swap_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
    ) -> SwapQuote:
        if self._mock_mode:
            return self._mock_quote(input_mint, output_mint, amount)

        await self._ensure_auth()
        resp = await self._http.get(
            f"{self._base_url}/v1/swap/quote",
            headers=self._auth_headers(),
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return SwapQuote(
            input_mint=input_mint,
            output_mint=output_mint,
            in_amount=int(data.get("inAmount", amount)),
            out_amount=int(data.get("outAmount", 0)),
            price_impact=float(data.get("priceImpact", 0)),
            raw=data,
        )

    async def execute_private_swap(self, quote: SwapQuote) -> TransactionResult:
        """Execute a private swap within the ephemeral rollup."""
        if self._mock_mode:
            return self._mock_tx_result("private_swap")

        await self._ensure_auth()
        resp = await self._http.post(
            f"{self._base_url}/v1/swap",
            headers=self._auth_headers(),
            json={
                "quoteResponse": quote.raw,
                "fromBalance": "ephemeral",
                "visibility": "private",
            },
        )
        resp.raise_for_status()
        return await self._sign_and_submit(resp.json())

    async def withdraw(self, mint: str, amount: int) -> TransactionResult:
        """Withdraw SPL tokens from ephemeral rollup back to Solana mainnet."""
        if self._mock_mode:
            return self._mock_tx_result("withdraw")

        await self._ensure_auth()
        resp = await self._http.post(
            f"{self._base_url}/v1/spl/withdraw",
            headers=self._auth_headers(),
            json={
                "to": self.wallet_address,
                "mint": mint,
                "amount": amount,
            },
        )
        resp.raise_for_status()
        return await self._sign_and_submit(resp.json())

    async def _sign_and_submit(self, tx_response: dict) -> TransactionResult:
        """Sign an unsigned transaction and submit it to the appropriate RPC."""
        try:
            tx_b64 = tx_response.get("transactionBase64", "")
            send_to = tx_response.get("sendTo", "base")

            tx_bytes = base64.b64decode(tx_b64)
            tx = VersionedTransaction.from_bytes(tx_bytes)

            signed_tx = VersionedTransaction(tx.message, [self._keypair])
            raw_tx = bytes(signed_tx)

            if send_to == "ephemeral":
                resp = await self._http.post(
                    f"{self._base_url}/v1/spl/send-transaction",
                    headers=self._auth_headers(),
                    json={"transaction": base64.b64encode(raw_tx).decode()},
                )
                resp.raise_for_status()
                sig = resp.json().get("signature", "ephemeral_tx")
            else:
                result = await self._solana_rpc.send_raw_transaction(raw_tx)
                sig = str(result.value)

            return TransactionResult(success=True, signature=sig)

        except Exception as e:
            logger.error("Transaction failed: %s", e)
            return TransactionResult(success=False, error=str(e))

    def get_status(self) -> dict:
        return {
            "authenticated": self._authenticated,
            "mock_mode": self._mock_mode,
            "wallet": self.wallet_address,
            "api_url": self._base_url,
        }

    # Mock helpers for demo resilience
    def _mock_balance(self) -> dict:
        return {
            "balances": [
                {"mint": settings.sol_mint, "amount": 5_000_000_000, "decimals": 9},
                {"mint": settings.usdc_mint, "amount": 500_000_000, "decimals": 6},
            ]
        }

    def _mock_private_balance(self) -> dict:
        return {
            "balances": [
                {"mint": settings.sol_mint, "amount": 2_000_000_000, "decimals": 9},
                {"mint": settings.usdc_mint, "amount": 200_000_000, "decimals": 6},
            ]
        }

    def _mock_quote(self, input_mint: str, output_mint: str, amount: int) -> SwapQuote:
        if input_mint == settings.sol_mint:
            out_amount = int(amount * 170 / 1e3)
        else:
            out_amount = int(amount * 1e3 / 170)

        return SwapQuote(
            input_mint=input_mint,
            output_mint=output_mint,
            in_amount=amount,
            out_amount=out_amount,
            price_impact=0.001,
            raw={"mock": True},
        )

    def _mock_tx_result(self, tx_type: str) -> TransactionResult:
        mock_sig = f"mock_{tx_type}_{int(time.time())}"
        return TransactionResult(success=True, signature=mock_sig)


magicblock_client = MagicBlockClient()
