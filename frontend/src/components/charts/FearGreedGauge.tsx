import React from 'react';
import { Card } from '@/components/common/Card';
import { TrendingUp, Activity, AlertCircle } from 'lucide-react';

interface FearGreedGaugeProps {
  score?: number; // 0 to 100
  history?: { label: string; score: number }[];
}

export const FearGreedGauge: React.FC<FearGreedGaugeProps> = ({
  score = 49,
  history = [
    { label: 'Previous Close', score: 56.5 },
    { label: '1 Week Ago', score: 61.0 },
    { label: '1 Month Ago', score: 61.1 },
    { label: '1 Year Ago', score: 29.7 },
  ],
}) => {
  // Determine state based on score
  let label = 'NEUTRAL';
  let badgeColor = 'text-amber-500 bg-amber-500/10 border-amber-500/20';

  if (score < 25) {
    label = 'EXTREME FEAR';
    badgeColor = 'text-rose-500 bg-rose-500/10 border-rose-500/20';
  } else if (score < 45) {
    label = 'FEAR';
    badgeColor = 'text-orange-500 bg-orange-500/10 border-orange-500/20';
  } else if (score <= 55) {
    label = 'NEUTRAL';
    badgeColor = 'text-amber-500 bg-amber-500/10 border-amber-500/20';
  } else if (score <= 75) {
    label = 'GREED';
    badgeColor = 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20';
  } else {
    label = 'EXTREME GREED';
    badgeColor = 'text-brand-500 bg-brand-500/10 border-brand-500/20';
  }

  // Calculate needle angle (-90deg to +90deg for semi-circle)
  // Score 0 -> -90 deg, 50 -> 0 deg, 100 -> +90 deg
  const needleAngle = -90 + (score / 100) * 180;

  return (
    <Card className="p-5 flex flex-col justify-between">
      <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">PSX Market Sentiment</span>
        </div>
        <span className="text-[11px] font-semibold text-fg-subtle uppercase tracking-wider">
          Fear & Greed Index
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
        {/* Left: Semi-circle SVG needle gauge */}
        <div className="flex flex-col items-center justify-center relative">
          <svg viewBox="0 0 200 115" className="w-48 sm:w-56 overflow-visible">
            <defs>
              <linearGradient id="gaugeGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#f43f5e" />
                <stop offset="25%" stopColor="#fb923c" />
                <stop offset="50%" stopColor="#facc15" />
                <stop offset="75%" stopColor="#34d399" />
                <stop offset="100%" stopColor="#238989" />
              </linearGradient>
            </defs>

            {/* Gauge Background Arc (Radius 80, stroke 14) */}
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke="var(--theme-border)"
              strokeWidth="14"
              strokeLinecap="round"
            />

            {/* Colored Active Arc */}
            <path
              d="M 20 100 A 80 80 0 0 1 180 100"
              fill="none"
              stroke="url(#gaugeGradient)"
              strokeWidth="14"
              strokeLinecap="round"
              strokeDasharray="251.2"
              strokeDashoffset="0"
              opacity="0.9"
            />

            {/* Pivot Center Point */}
            <circle cx="100" cy="100" r="7" fill="var(--theme-fg)" />

            {/* Needle */}
            <g transform={`rotate(${needleAngle} 100 100)`}>
              <line
                x1="100"
                y1="100"
                x2="100"
                y2="30"
                stroke="var(--theme-fg)"
                strokeWidth="3.5"
                strokeLinecap="round"
              />
            </g>
          </svg>

          {/* Score & Label badge under needle */}
          <div className="text-center mt-1">
            <div className="text-3xl font-extrabold font-mono text-fg">{score}</div>
            <div className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-bold border mt-1 ${badgeColor}`}>
              {label}
            </div>
          </div>
        </div>

        {/* Right: Historical timeline telemetry */}
        <div className="space-y-2.5 border-t md:border-t-0 md:border-l border-border md:pl-5 pt-3 md:pt-0">
          <div className="text-xs font-medium text-fg-subtle mb-1">Historical Comparison</div>
          {history.map(item => {
            let itemColor = 'text-amber-500';
            if (item.score < 45) itemColor = 'text-rose-500';
            else if (item.score > 55) itemColor = 'text-emerald-500';

            return (
              <div key={item.label} className="flex items-center justify-between text-xs py-1 border-b border-border/40 last:border-0">
                <span className="text-fg-muted">{item.label}</span>
                <div className="flex items-center gap-2">
                  <span className={`font-mono font-bold ${itemColor}`}>{item.score.toFixed(1)}</span>
                  <span className="text-[10px] text-fg-subtle">
                    {item.score < 45 ? 'Fear' : item.score > 55 ? 'Greed' : 'Neutral'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between text-[11px] text-fg-subtle">
        <span>Computed from Market Breadth, Volatility & FinBERT sentiment</span>
        <span className="font-mono">Updated EOD</span>
      </div>
    </Card>
  );
};
