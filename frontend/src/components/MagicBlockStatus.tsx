"use client";

import { Lock, Wifi, WifiOff, TestTube } from "lucide-react";
import type { MagicBlockStatus as MBStatus } from "@/lib/types";

interface Props {
  status: MBStatus | null;
}

export default function MagicBlockStatus({ status }: Props) {
  if (!status) return null;

  const connected = status.authenticated;
  const isMock = status.mock_mode;

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
      <div className="flex items-center gap-2 mb-3">
        <Lock size={14} className="text-amber-400" />
        <h2 className="text-sm font-semibold text-gray-200">MagicBlock PER</h2>
        <span
          className={`ml-auto flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border ${
            connected
              ? "bg-emerald-950/30 text-emerald-400 border-emerald-500/20"
              : "bg-red-950/30 text-red-400 border-red-500/20"
          }`}
        >
          {connected ? <Wifi size={10} /> : <WifiOff size={10} />}
          {connected ? "Connected" : "Disconnected"}
        </span>
      </div>

      <div className="space-y-2 text-[11px]">
        {isMock && (
          <div className="flex items-center gap-1.5 text-amber-400/80 bg-amber-950/20 border border-amber-500/15 rounded-lg px-3 py-1.5">
            <TestTube size={11} />
            Running in mock mode (no keypair configured)
          </div>
        )}

        {status.wallet && (
          <div className="flex justify-between">
            <span className="text-gray-500">Wallet</span>
            <span className="text-gray-300 font-mono text-[10px]">
              {status.wallet.slice(0, 6)}...{status.wallet.slice(-4)}
            </span>
          </div>
        )}

        <div className="flex justify-between">
          <span className="text-gray-500">API</span>
          <span className="text-gray-400 text-[10px]">{status.api_url}</span>
        </div>

        {status.private_balance?.balances && (
          <div className="mt-2 pt-2 border-t border-gray-800">
            <div className="text-[10px] text-gray-500 mb-1.5">Ephemeral Balance</div>
            {status.private_balance.balances.map((b) => (
              <div key={b.mint} className="flex justify-between text-[10px]">
                <span className="text-gray-400 font-mono">
                  {b.mint.slice(0, 6)}...
                </span>
                <span className="text-gray-300">
                  {(b.amount / Math.pow(10, b.decimals)).toFixed(b.decimals > 6 ? 4 : 2)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
