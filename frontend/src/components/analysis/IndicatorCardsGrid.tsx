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
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <Gauge className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>RSI (14)</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
              rsi > 70
                ? 'bg-[#C64C4C]/15 text-[#C64C4C] dark:text-[#E05C5C] border-[#C64C4C]/30'
                : rsi < 35
                ? 'bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border-[#287A50]/30'
                : 'bg-[#2F7D68]/15 text-[#2F7D68] dark:text-[#3DA88D] border-[#2F7D68]/30'
            }`}
          >
            {rsi > 70 ? 'Overbought' : rsi < 35 ? 'Oversold' : 'Momentum Bull'}
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6]">{rsi.toFixed(1)}</div>
          {/* Progress bar with 30 and 70 thresholds */}
          <div className="w-full h-2 rounded-full bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 overflow-hidden border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20 relative">
            <div
              style={{ width: `${Math.min(100, Math.max(0, rsi))}%` }}
              className="h-full bg-gradient-to-r from-[#2F7D68] to-[#236353] rounded-full"
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-[#77736C] dark:text-[#9E988E] font-mono">
            <span>30 (Oversold)</span>
            <span>70 (Overbought)</span>
          </div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.rsi_condition?.explanation || 'Momentum sits in healthy constructive territory.'}
        </p>
      </Card>

      {/* 2. MACD (12, 26, 9) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <TrendingUp className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>MACD (12, 26, 9)</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
              macdDiff >= 0
                ? 'bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border-[#287A50]/30'
                : 'bg-[#C64C4C]/15 text-[#C64C4C] dark:text-[#E05C5C] border-[#C64C4C]/30'
            }`}
          >
            {macdDiff >= 0 ? 'Bullish Expansion' : 'Bearish Divergence'}
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className={`text-2xl font-extrabold font-mono ${macdDiff >= 0 ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#C64C4C] dark:text-[#E05C5C]'}`}>
              {macdDiff >= 0 ? '+' : ''}{macdDiff.toFixed(2)}
            </span>
            <span className="text-[11px] font-mono text-[#77736C] dark:text-[#9E988E]">Histogram</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-[#77736C] dark:text-[#9E988E] pt-1">
            <div>Line: <strong className="text-[#252A2B] dark:text-[#F4EFE6]">{macdLine.toFixed(2)}</strong></div>
            <div>Signal: <strong className="text-[#252A2B] dark:text-[#F4EFE6]">{macdSignal.toFixed(2)}</strong></div>
          </div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.macd_condition?.explanation || 'MACD trades above signal line with positive histogram.'}
        </p>
      </Card>

      {/* 3. Bollinger Bands (20, 2.0) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <Layers className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>Bollinger Bands</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 text-[#77736C] dark:text-[#9E988E] border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20">
            %B: {bbPctB.toFixed(2)}
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6]">{bbWidth.toFixed(1)}%</div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">Bandwidth Expansion</div>
          <div className="flex items-center justify-between text-[10px] font-mono text-[#77736C] dark:text-[#9E988E] pt-1">
            <span>Low: {bbLower.toFixed(1)}</span>
            <span>Up: {bbUpper.toFixed(1)}</span>
          </div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.bollinger_condition?.explanation || 'Price maintains posture within the statistical upper envelope.'}
        </p>
      </Card>

      {/* 4. ADX / DMI (14) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <Sliders className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>ADX &amp; Directional (+DI/-DI)</span>
          </div>
          <span
            className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
              adx >= 25
                ? 'bg-[#2F7D68]/15 text-[#2F7D68] dark:text-[#3DA88D] border-[#2F7D68]/30'
                : 'bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 text-[#77736C] dark:text-[#9E988E] border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20'
            }`}
          >
            {adx >= 25 ? 'Trending Strong' : 'Consolidating'}
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6]">{adx.toFixed(1)}</span>
            <span className="text-xs font-bold text-[#287A50] dark:text-[#34A86E]">+DI &gt; -DI</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px] font-mono pt-1">
            <span className="text-[#287A50] dark:text-[#34A86E]">+DI: {dmiPlus.toFixed(1)}</span>
            <span className="text-[#C64C4C] dark:text-[#E05C5C]">-DI: {dmiMinus.toFixed(1)}</span>
          </div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.trend_strength?.explanation || 'Bullish buyers maintain directional control.'}
        </p>
      </Card>

      {/* 5. ATR Volatility (14) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <Activity className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>Average True Range (ATR)</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 text-[#77736C] dark:text-[#9E988E] border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20">
            {atrPct.toFixed(1)}% of Price
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6]">PKR {atrPkr.toFixed(2)}</div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">Average daily session price swing</div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.volatility?.explanation || 'Typical daily volatility defines healthy risk boundaries.'}
        </p>
      </Card>

      {/* 6. Stochastic (14, 3, 3) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <BarChart2 className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>Stochastic (14, 3, 3)</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 text-[#77736C] dark:text-[#9E988E] border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20">
            Expansion Zone
          </span>
        </div>

        <div className="space-y-1">
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6]">%K {stochK.toFixed(1)}</span>
            <span className="text-xs font-mono text-[#77736C] dark:text-[#9E988E]">%D {stochD.toFixed(1)}</span>
          </div>
          <div className="w-full h-2 rounded-full bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 overflow-hidden border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20">
            <div style={{ width: `${stochK}%` }} className="h-full bg-gradient-to-r from-[#2F7D68] to-[#236353] rounded-full" />
          </div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.stochastic_cycle?.explanation || 'Fast Stochastic remains in healthy expansion zone.'}
        </p>
      </Card>

      {/* 7. On-Balance Volume (OBV) Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <DollarSign className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>On-Balance Volume (OBV)</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border border-[#287A50]/30">
            Accumulation
          </span>
        </div>

        <div className="space-y-1">
          <div className="text-2xl font-extrabold font-mono text-[#2F7D68] dark:text-[#3DA88D]">
            +{(obv / 1000000).toFixed(1)}M
          </div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">Price-Volume cumulative flow above 20 EMA</div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.volume_flow?.explanation || 'Cumulative volume flow confirms institutional buying.'}
        </p>
      </Card>

      {/* 8. Moving Average Alignment Card */}
      <Card className="p-4 space-y-3 flex flex-col justify-between h-full">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">
            <Maximize2 className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
            <span>MA Trend Alignment</span>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border border-[#287A50]/30">
            Bullish Stack
          </span>
        </div>

        <div className="space-y-1 text-xs font-mono">
          <div className="text-sm font-bold text-[#287A50] dark:text-[#34A86E]">Price &gt; SMA 50 &gt; SMA 200</div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">Golden Cross regime confirmed</div>
        </div>

        <p className="text-[11px] text-[#77736C] dark:text-[#9E988E] line-clamp-2 leading-relaxed pt-2 mt-auto border-t border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15">
          {diagnostics?.trend_alignment?.explanation || 'Hierarchical moving average order establishes primary uptrend.'}
        </p>
      </Card>
    </div>
  );
};
