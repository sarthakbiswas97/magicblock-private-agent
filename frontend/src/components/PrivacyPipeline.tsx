"use client";

import {
  Database,
  BarChart3,
  Brain,
  ShieldCheck,
  Lock,
  Globe,
  Loader2,
  X,
  Ban,
  SkipForward,
} from "lucide-react";
import type { PipelineStep } from "@/lib/types";

const STEP_META: Record<
  string,
  { label: string; icon: typeof Database; color: string; privacyLabel: string }
> = {
  market_data: {
    label: "Market Data",
    icon: Database,
    color: "gray",
    privacyLabel: "Public",
  },
  features: {
    label: "Feature Engine",
    icon: BarChart3,
    color: "emerald",
    privacyLabel: "Private (off-chain)",
  },
  prediction: {
    label: "AI Prediction",
    icon: Brain,
    color: "emerald",
    privacyLabel: "Private (off-chain)",
  },
  risk_check: {
    label: "Risk Gate",
    icon: ShieldCheck,
    color: "emerald",
    privacyLabel: "Private (off-chain)",
  },
  private_execution: {
    label: "MagicBlock PER",
    icon: Lock,
    color: "amber",
    privacyLabel: "Private (TEE)",
  },
  settlement: {
    label: "Settlement",
    icon: Globe,
    color: "gray",
    privacyLabel: "On-chain",
  },
};

const STATUS_STYLES: Record<string, string> = {
  pending: "border-gray-700 bg-gray-900/50 text-gray-500",
  running: "border-blue-500/50 bg-blue-950/30 text-blue-400 ring-1 ring-blue-500/20",
  completed: "border-emerald-500/40 bg-emerald-950/20 text-emerald-400",
  failed: "border-red-500/40 bg-red-950/20 text-red-400",
  rejected: "border-red-500/40 bg-red-950/20 text-red-400",
  skipped: "border-gray-700 bg-gray-900/30 text-gray-600",
};

function StatusIcon({ status }: { status: string }) {
  if (status === "running") return <Loader2 size={12} className="spin-slow" />;
  if (status === "failed") return <X size={12} />;
  if (status === "rejected") return <Ban size={12} />;
  if (status === "skipped") return <SkipForward size={12} />;
  return null;
}

function PipelineNode({ step, name: nodeName }: { step: PipelineStep | null; name: string }) {
  const name = step?.name ?? nodeName;
  const meta = STEP_META[name] ?? STEP_META.market_data;
  const Icon = meta.icon;
  const status = step?.status ?? "pending";
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.pending;

  const isPrivate = step?.is_private ?? meta.privacyLabel.startsWith("Private");
  const showLock = isPrivate && status === "completed";

  return (
    <div className="flex flex-col items-center gap-1.5 min-w-[100px]">
      <div
        className={`relative flex flex-col items-center gap-1 rounded-lg border px-3 py-2.5 transition-all duration-300 ${style}`}
      >
        <div className="flex items-center gap-1.5">
          <Icon size={16} />
          {showLock && <Lock size={10} className="text-emerald-400" />}
          <StatusIcon status={status} />
        </div>
        <span className="text-[11px] font-medium whitespace-nowrap">{meta.label}</span>

        {step?.duration_ms ? (
          <span className="text-[9px] text-gray-500">{step.duration_ms.toFixed(0)}ms</span>
        ) : null}
      </div>
      <span
        className={`text-[9px] ${
          isPrivate && status !== "pending" ? "text-emerald-500/70" : "text-gray-600"
        }`}
      >
        {meta.privacyLabel}
      </span>
    </div>
  );
}

function Arrow({ active }: { active: boolean }) {
  return (
    <div className="flex items-center px-1 pt-2">
      <div
        className={`h-[2px] w-8 ${active ? "pipeline-line-active" : "pipeline-line"}`}
      />
      <div
        className={`h-0 w-0 border-t-[4px] border-b-[4px] border-l-[6px] border-t-transparent border-b-transparent ${
          active ? "border-l-emerald-400/50" : "border-l-gray-600/40"
        }`}
      />
    </div>
  );
}

interface PrivacyPipelineProps {
  steps: PipelineStep[];
}

const STEP_ORDER = [
  "market_data",
  "features",
  "prediction",
  "risk_check",
  "private_execution",
  "settlement",
];

export default function PrivacyPipeline({ steps }: PrivacyPipelineProps) {
  const stepMap = new Map(steps.map((s) => [s.name, s]));

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
      <div className="flex items-center gap-2 mb-4">
        <Lock size={14} className="text-emerald-400" />
        <h2 className="text-sm font-semibold text-gray-200">Private Trading Pipeline</h2>
        <span className="ml-auto text-[10px] text-gray-500 bg-gray-800/60 px-2 py-0.5 rounded-full">
          MEV Protected
        </span>
      </div>

      <div className="flex items-start justify-center overflow-x-auto pb-2">
        {STEP_ORDER.map((name, i) => {
          const step = stepMap.get(name) ?? null;
          const prevStep = i > 0 ? stepMap.get(STEP_ORDER[i - 1]) : null;
          const arrowActive =
            prevStep?.status === "completed" && step?.status !== "pending";

          return (
            <div key={name} className="flex items-start">
              {i > 0 && <Arrow active={arrowActive} />}
              <PipelineNode step={step} name={name} />
            </div>
          );
        })}
      </div>

      {steps.length > 0 && (
        <div className="mt-3 flex items-center gap-3 text-[10px] text-gray-500">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500/60" />
            Private step
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-gray-500/60" />
            Public step
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-500/60" />
            TEE execution
          </span>
        </div>
      )}
    </div>
  );
}
