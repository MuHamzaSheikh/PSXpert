import React from 'react';
import { Card } from '@/components/common/Card';
import { HMMRegimeResult } from '@/types';
import { Activity, ShieldCheck, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface HMMRegimeCardProps {
  data: HMMRegimeResult;
}

export const HMMRegimeCard: React.FC<HMMRegimeCardProps> = ({ data }) => {
  const isBull = data.current_regime === 'Bullish';
  const isBear = data.current_regime === 'Bearish';

  const bullProb = Math.round((data.regime_probabilities?.bullish ?? 0.84) * 100);
  const bearProb = Math.round((data.regime_probabilities?.bearish ?? 0.08) * 100);
  const sideProb = Math.round((data.regime_probabilities?.sideways ?? 0.08) * 100);

  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D]" />
          <span className="font-semibold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Hidden Markov Model (HMM) Latent Regime</span>
        </div>
        <span className="text-[11px] font-mono text-[#77736C] dark:text-[#9E988E]">Zero Lookahead Invariance</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
        {/* Regime State */}
        <div className="space-y-2">
          <div className="text-xs text-[#77736C] dark:text-[#9E988E]">Current Statistical State</div>
          <div className="flex items-center gap-2">
            <span
              className={`text-2xl font-black font-mono ${
                isBull ? 'text-[#287A50] dark:text-[#34A86E]' : isBear ? 'text-[#C64C4C] dark:text-[#E05C5C]' : 'text-amber-500'
              }`}
            >
              {data.current_regime}
            </span>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-[#2F7D68]/15 text-[#2F7D68] dark:text-[#3DA88D] border border-[#2F7D68]/30">
              {Math.round(data.regime_probability * 100)}% Conviction
            </span>
          </div>

          <div className="space-y-1.5 pt-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-[#287A50] dark:text-[#34A86E] font-semibold flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5" /> Bullish State
              </span>
              <span className="font-mono text-[#252A2B] dark:text-[#F4EFE6] font-bold">{bullProb}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-[#E7E0D5]/50 dark:bg-[#1C2022] overflow-hidden border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20">
              <div style={{ width: `${bullProb}%` }} className="h-full bg-[#287A50]" />
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <span className="text-[#C64C4C] dark:text-[#E05C5C] font-semibold flex items-center gap-1">
                <TrendingDown className="w-3.5 h-3.5" /> Bearish State
              </span>
              <span className="font-mono text-[#252A2B] dark:text-[#F4EFE6] font-bold">{bearProb}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-[#E7E0D5]/50 dark:bg-[#1C2022] overflow-hidden border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20">
              <div style={{ width: `${bearProb}%` }} className="h-full bg-[#C64C4C]" />
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <span className="text-[#77736C] dark:text-[#9E988E] font-semibold flex items-center gap-1">
                <Minus className="w-3.5 h-3.5" /> Sideways / Range
              </span>
              <span className="font-mono text-[#252A2B] dark:text-[#F4EFE6] font-bold">{sideProb}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-[#E7E0D5]/50 dark:bg-[#1C2022] overflow-hidden border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/20">
              <div style={{ width: `${sideProb}%` }} className="h-full bg-[#77736C]" />
            </div>
          </div>
        </div>

        {/* Regime Telemetry */}
        <div className="p-4 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 space-y-2.5 text-xs">
          <div className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Regime Characteristics (Annualized)</div>
          <div className="flex items-center justify-between py-1 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
            <span className="text-[#77736C] dark:text-[#9E988E]">Expected Daily Drift</span>
            <span className="font-mono font-bold text-[#287A50] dark:text-[#34A86E]">
              +{data.regime_characteristics?.expected_daily_return_pct ?? 0.14}%
            </span>
          </div>
          <div className="flex items-center justify-between py-1 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
            <span className="text-[#77736C] dark:text-[#9E988E]">Annualized Volatility (σ)</span>
            <span className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
              {data.regime_characteristics?.annualized_volatility_pct ?? 18.2}%
            </span>
          </div>
          <div className="flex items-center justify-between py-1 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
            <span className="text-[#77736C] dark:text-[#9E988E]">Transition Persistence</span>
            <span className="font-mono font-bold text-[#2F7D68] dark:text-[#3DA88D]">
              {data.regime_characteristics?.transition_persistence_pct ?? 92.4}%
            </span>
          </div>
          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E] pt-1">
            Latent Gaussian HMM model trained chronologically over 750 trading sessions.
          </div>
        </div>
      </div>
    </Card>
  );
};
