"use client";

import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, IChartApi, ISeriesApi, CandlestickData, Time } from "lightweight-charts";
import type { CandleData } from "@/lib/types";

interface PriceChartProps {
  candles: CandleData[];
  latestPrice: number;
}

export default function PriceChart({ candles, latestPrice }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<typeof CandlestickSeries> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#6b7280",
        fontSize: 10,
      },
      grid: {
        vertLines: { color: "rgba(75, 85, 99, 0.15)" },
        horzLines: { color: "rgba(75, 85, 99, 0.15)" },
      },
      crosshair: {
        vertLine: { color: "rgba(156, 163, 175, 0.3)" },
        horzLine: { color: "rgba(156, 163, 175, 0.3)" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "rgba(75, 85, 99, 0.3)",
      },
      rightPriceScale: {
        borderColor: "rgba(75, 85, 99, 0.3)",
      },
      width: containerRef.current.clientWidth,
      height: 260,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#34d399",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const resizeObserver = new ResizeObserver((entries) => {
      const { width } = entries[0].contentRect;
      chart.applyOptions({ width });
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return;

    const data: CandlestickData<Time>[] = candles.map((c) => ({
      time: (c.open_time / 1000) as Time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/80 p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-gray-200">SOL/USDC</h2>
        <span className="text-sm font-mono text-gray-300">${latestPrice.toFixed(2)}</span>
      </div>
      <div ref={containerRef} />
    </div>
  );
}
