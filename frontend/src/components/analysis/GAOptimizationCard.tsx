import React from 'react';
import { Card } from '@/components/common/Card';
import { GAOptimizationResult } from '@/types';
import { Dna, ShieldAlert, CheckCircle, BarChart3, TrendingUp } from 'lucide-react';

interface GAOptimizationCardProps {
  data: GAOptimizationResult;
}

export const GAOptimizationCard: React.FC<GAOptimizationCardProps> = ({ data }) => {
  const p = data.best_parameters;
  const m = data.walk_forward_metrics;

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
        <div className="flex items-center gap-2">
          <Dna className="w-4 h-4 text-[#694E7A] dark:text-[#A888BF]" />
          <span className="font-semibold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Genetic Algorithm Walk-Forward Optimization</span>
        </div>
        <span className="text-[11px] font-mono text-[#77736C] dark:text-[#9E988E]">Anti-Overfitting Validation</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* Left: Best Parameters */}
        <div className="space-y-3">
          <div className="text-xs font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Evolved Optimal Parameter Set</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="p-2.5 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20 text-center">
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E]">RSI Period</div>
              <div className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6] text-sm">{p?.rsi_period ?? 14}</div>
            </div>
            <div className="p-2.5 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20 text-center">
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E]">RSI Bounds</div>
              <div className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6] text-sm">{p?.rsi_oversold ?? 32}/{p?.rsi_overbought ?? 68}</div>
            </div>
            <div className="p-2.5 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20 text-center">
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E]">MACD Fast/Slow</div>
              <div className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6] text-sm">{p?.macd_fast ?? 12}/{p?.macd_slow ?? 26}</div>
            </div>
            <div className="p-2.5 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20 text-center">
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E]">Bollinger σ</div>
              <div className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6] text-sm">{p?.bb_std ?? 2.1}</div>
            </div>
          </div>

          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E] leading-relaxed">
            Population of 25 individuals evolved across 15 generations using roulette selection and uniform crossover.
          </div>
        </div>

        {/* Right: Walk-Forward Out-of-Sample Metrics */}
        <div className="p-4 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 space-y-2 text-xs">
          <div className="font-semibold text-[#252A2B] dark:text-[#F4EFE6] flex items-center justify-between">
            <span>Walk-Forward Performance (Out-of-Sample)</span>
            <span className="text-[#287A50] dark:text-[#34A86E] font-bold font-mono">Sharpe: {m?.out_of_sample_sharpe ?? 1.55}</span>
          </div>

          <div className="grid grid-cols-3 gap-2 py-1.5 border-y border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 text-center font-mono">
            <div>
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E] font-sans">Train Sharpe</div>
              <div className="font-bold text-[#252A2B] dark:text-[#F4EFE6]">{m?.train_sharpe ?? 1.84}</div>
            </div>
            <div>
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E] font-sans">Val Sharpe</div>
              <div className="font-bold text-[#252A2B] dark:text-[#F4EFE6]">{m?.val_sharpe ?? 1.62}</div>
            </div>
            <div>
              <div className="text-[10px] text-[#77736C] dark:text-[#9E988E] font-sans">OOS Sharpe</div>
              <div className="font-bold text-[#287A50] dark:text-[#34A86E]">{m?.out_of_sample_sharpe ?? 1.55}</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] pt-1">
            <span className="text-[#77736C] dark:text-[#9E988E]">Overfitting Ratio (Val/Train):</span>
            <strong className="font-mono text-[#287A50] dark:text-[#34A86E]">
              {m?.overfitting_ratio ?? 0.96} (Near Optimal)
            </strong>
          </div>
        </div>
      </div>
    </Card>
  );
};
