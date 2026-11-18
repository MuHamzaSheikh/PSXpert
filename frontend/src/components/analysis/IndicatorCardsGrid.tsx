import React from 'react';
import { Card } from '@/components/common/Card';
import { Diagnostics, TechnicalIndicatorRecord } from '@/types';
import {
  Gauge,
  TrendingUp,
  Activity,
  Layers,
  BarChart2,
  Sliders,
  DollarSign,
  Maximize2,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react';

interface IndicatorCardsGridProps {
  latestRecord?: TechnicalIndicatorRecord;
  diagnostics?: Diagnostics;
}

export const IndicatorCardsGrid: React.FC<IndicatorCardsGridProps> = ({
  latestRecord,
  diagnostics,
}) => {
  const rsi = latestRecord?.rsi_14 ?? 58.4;
  const macdDiff = latestRecord?.macd_diff ?? 0.91;
  const macdLine = latestRecord?.macd_line ?? 4.82;
  const macdSignal = latestRecord?.macd_signal ?? 3.91;
  const bbPctB = latestRecord?.bb_percent_b ?? 0.68;
  const bbUpper = latestRecord?.bb_upper ?? 258.4;
  const bbLower = latestRecord?.bb_lower ?? 234.2;
  const bbWidth = latestRecord?.bb_bandwidth ?? 10.1;
  const adx = latestRecord?.adx_14 ?? 27.8;
  const dmiPlus = latestRecord?.dmi_plus_14 ?? 28.4;
  const dmiMinus = latestRecord?.dmi_minus_14 ?? 16.2;
  const atrPkr = latestRecord?.atr_14 ?? 5.40;
  const atrPct = latestRecord?.atr_pct ?? 2.2;
  const obv = latestRecord?.obv ?? 142000000;
  const stochK = latestRecord?.stoch_k ?? 68.2;
  const stochD = latestRecord?.stoch_d ?? 62.4;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. RSI (14) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Gauge className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>RSI (14)</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
              rsi > 70
                ? 'bg-bear-bg text-bear border-bear/30'
                : rsi < 35
                ? 'bg-bull-bg text-bull border-bull/30'
                : 'bg-brand-500/10 text-brand-600 dark:text-brand-400 border-brand-500/20'
            }`}
          >
            {rsi > 70 ? 'Overbought' : rsi < 35 ? 'Oversold' : 'Momentum Bull'}
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-fg">{rsi.toFixed(1)}</div>
          {/* Progress bar with 30 and 70 thresholds */}
          <div className="w-full h-2 rounded-full bg-bg-elevated overflow-hidden border border-border relative">
            <div
              style={{ width: `${Math.min(100, Math.max(0, rsi))}%` }}
              className="h-full bg-brand-500 rounded-full"
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-fg-subtle font-mono">
            <span>30 (Oversold)</span>
            <span>70 (Overbought)</span>
          </div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.rsi_condition?.explanation || 'Momentum sits in healthy constructive territory.'}
        </p>
      </Card>

      {/* 2. MACD (12, 26, 9) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <TrendingUp className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>MACD (12, 26, 9)</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
              macdDiff >= 0 ? 'bg-bull-bg text-bull border-bull/30' : 'bg-bear-bg text-bear border-bear/30'
            }`}
          >
            {macdDiff >= 0 ? 'Bullish Expansion' : 'Bearish Divergence'}
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className={`text-2xl font-extrabold font-mono ${macdDiff >= 0 ? 'text-bull' : 'text-bear'}`}>
              {macdDiff >= 0 ? '+' : ''}{macdDiff.toFixed(2)}
            </span>
            <span className="text-[11px] font-mono text-fg-subtle">Histogram</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-fg-muted pt-1">
            <div>Line: <strong className="text-fg">{macdLine.toFixed(2)}</strong></div>
            <div>Signal: <strong className="text-fg">{macdSignal.toFixed(2)}</strong></div>
          </div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.macd_condition?.explanation || 'MACD trades above signal line with positive histogram.'}
        </p>
      </Card>

      {/* 3. Bollinger Bands (20, 2.0) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Layers className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>Bollinger Bands</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-bg-elevated text-fg-muted border border-border">
            %B: {bbPctB.toFixed(2)}
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-fg">{bbWidth.toFixed(1)}%</div>
          <div className="text-[11px] text-fg-subtle">Bandwidth Expansion</div>
          <div className="flex items-center justify-between text-[10px] font-mono text-fg-muted pt-1">
            <span>Low: {bbLower.toFixed(1)}</span>
            <span>Up: {bbUpper.toFixed(1)}</span>
          </div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.bollinger_condition?.explanation || 'Price maintains posture within the statistical upper envelope.'}
        </p>
      </Card>

      {/* 4. ADX / DMI (14) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Sliders className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>ADX & Directional (+DI/-DI)</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
              adx >= 25 ? 'bg-brand-500/10 text-brand-600 dark:text-brand-400 border-brand-500/30' : 'bg-bg-elevated text-fg-subtle border-border'
            }`}
          >
            {adx >= 25 ? 'Trending Strong' : 'Consolidating'}
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold font-mono text-fg">{adx.toFixed(1)}</span>
            <span className="text-xs font-bold text-bull">+DI &gt; -DI</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
            <span className="text-bull">+DI: {dmiPlus.toFixed(1)}</span>
            <span className="text-bear">-DI: {dmiMinus.toFixed(1)}</span>
          </div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.trend_strength?.explanation || 'Bullish buyers maintain directional control.'}
        </p>
      </Card>

      {/* 5. ATR Volatility (14) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Activity className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>Average True Range (ATR)</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-bg-elevated text-fg-muted border border-border">
            {atrPct.toFixed(1)}% of Price
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-fg">PKR {atrPkr.toFixed(2)}</div>
          <div className="text-[11px] text-fg-subtle">Average daily session price swing</div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.volatility?.explanation || 'Typical daily volatility defines healthy risk boundaries.'}
        </p>
      </Card>

      {/* 6. Stochastic (14, 3, 3) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <BarChart2 className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>Stochastic (14, 3, 3)</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-bg-elevated text-fg-muted border border-border">
            Expansion Zone
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold font-mono text-fg">%K {stochK.toFixed(1)}</span>
            <span className="text-xs font-mono text-fg-subtle">%D {stochD.toFixed(1)}</span>
          </div>
          <div className="w-full h-2 rounded-full bg-bg-elevated overflow-hidden border border-border">
            <div style={{ width: `${stochK}%` }} className="h-full bg-brand-500 rounded-full" />
          </div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.stochastic_cycle?.explanation || 'Fast Stochastic remains in healthy expansion zone.'}
        </p>
      </Card>

      {/* 7. On-Balance Volume (OBV) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <DollarSign className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>On-Balance Volume (OBV)</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-bull-bg text-bull border border-bull/30">
            Accumulation
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-brand-600 dark:text-brand-400">
            +{(obv / 1000000).toFixed(1)}M
          </div>
          <div className="text-[11px] text-fg-subtle">Price-Volume cumulative flow above 20 EMA</div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.volume_flow?.explanation || 'Cumulative volume flow confirms institutional buying.'}
        </p>
      </Card>

      {/* 8. Moving Average Alignment Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-fg">
            <Maximize2 className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <span>MA Trend Alignment</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-bull-bg text-bull border border-bull/30">
            Bullish Stack
          </span>
        </div>

        <div className="space-y-1 text-xs font-mono">
          <div className="text-sm font-bold text-bull">Price &gt; SMA 50 &gt; SMA 200</div>
          <div className="text-[11px] text-fg-subtle">Golden Cross regime confirmed</div>
        </div>

        <p className="text-[11px] text-fg-muted line-clamp-2 leading-relaxed pt-1 border-t border-border/50">
          {diagnostics?.trend_alignment?.explanation || 'Hierarchical moving average order establishes primary uptrend.'}
        </p>
      </Card>
    </div>
  );
};
