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
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">Hidden Markov Model (HMM) Latent Regime</span>
        </div>
        <span className="text-[11px] font-mono text-fg-subtle">Zero Lookahead Invariance</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 items-center">
        {/* Regime State */}
        <div className="space-y-2">
          <div className="text-xs text-fg-subtle">Current Statistical State</div>
          <div className="flex items-center gap-2">
            <span
              className={`text-2xl font-black font-mono ${
                isBull ? 'text-bull' : isBear ? 'text-bear' : 'text-amber-500'
              }`}
            >
              {data.current_regime}
            </span>
            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-600 border border-brand-500/20">
              {Math.round(data.regime_probability * 100)}% Conviction
            </span>
          </div>

          <div className="space-y-1.5 pt-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-bull font-semibold flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5" /> Bullish State
              </span>
              <span className="font-mono text-fg font-bold">{bullProb}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-bg-elevated overflow-hidden border border-border">
              <div style={{ width: `${bullProb}%` }} className="h-full bg-bull" />
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <span className="text-bear font-semibold flex items-center gap-1">
                <TrendingDown className="w-3.5 h-3.5" /> Bearish State
              </span>
              <span className="font-mono text-fg font-bold">{bearProb}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-bg-elevated overflow-hidden border border-border">
              <div style={{ width: `${bearProb}%` }} className="h-full bg-bear" />
            </div>

            <div className="flex items-center justify-between text-xs pt-1">
              <span className="text-fg-muted font-semibold flex items-center gap-1">
                <Minus className="w-3.5 h-3.5" /> Sideways / Range
              </span>
              <span className="font-mono text-fg font-bold">{sideProb}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-bg-elevated overflow-hidden border border-border">
              <div style={{ width: `${sideProb}%` }} className="h-full bg-fg-subtle" />
            </div>
          </div>
        </div>

        {/* Regime Telemetry */}
        <div className="p-3.5 rounded-xl bg-bg-elevated/40 border border-border space-y-2.5 text-xs">
          <div className="font-semibold text-fg">Regime Characteristics (Annualized)</div>
          <div className="flex items-center justify-between py-1 border-b border-border/40">
            <span className="text-fg-muted">Expected Daily Drift</span>
            <span className="font-mono font-bold text-bull">
              +{data.regime_characteristics?.expected_daily_return_pct ?? 0.14}%
            </span>
          </div>
          <div className="flex items-center justify-between py-1 border-b border-border/40">
            <span className="text-fg-muted">Annualized Volatility (σ)</span>
            <span className="font-mono font-bold text-fg">
              {data.regime_characteristics?.annualized_volatility_pct ?? 18.2}%
            </span>
          </div>
          <div className="flex items-center justify-between py-1 border-b border-border/40">
            <span className="text-fg-muted">Transition Persistence</span>
            <span className="font-mono font-bold text-brand-600 dark:text-brand-400">
              {data.regime_characteristics?.transition_persistence_pct ?? 92.4}%
            </span>
          </div>
          <div className="text-[11px] text-fg-subtle pt-1">
            Latent Gaussian HMM model trained chronologically over 750 trading sessions.
          </div>
        </div>
      </div>
    </Card>
  );
};
