import React from 'react';
import { Card } from '@/components/common/Card';
import { BarChart2, TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface MarketBreadthBarProps {
  advances: number;
  declines: number;
  unchanged: number;
  total?: number;
}

export const MarketBreadthBar: React.FC<MarketBreadthBarProps> = ({
  advances = 178,
  declines = 285,
  unchanged = 38,
  total,
}) => {
  const sum = total || (advances + declines + unchanged) || 1;
  const advPct = ((advances / sum) * 100).toFixed(1);
  const decPct = ((declines / sum) * 100).toFixed(1);
  const unchPct = ((unchanged / sum) * 100).toFixed(1);

  return (
    <Card className="p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart2 className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">Market Breadth</span>
        </div>
        <span className="text-xs font-mono text-fg-subtle">
          Total Traded: <strong className="text-fg">{sum}</strong>
        </span>
      </div>

      {/* Proportional Segmented Bar */}
      <div className="w-full h-3 rounded-full bg-bg-elevated overflow-hidden flex border border-border">
        <div
          style={{ width: `${advPct}%` }}
          className="h-full bg-bull transition-all duration-500"
          title={`Advances: ${advances} (${advPct}%)`}
        />
        <div
          style={{ width: `${decPct}%` }}
          className="h-full bg-bear transition-all duration-500"
          title={`Declines: ${declines} (${decPct}%)`}
        />
        <div
          style={{ width: `${unchPct}%` }}
          className="h-full bg-fg-subtle/40 transition-all duration-500"
          title={`Unchanged: ${unchanged} (${unchPct}%)`}
        />
      </div>

      {/* Segment Legend Counters */}
      <div className="grid grid-cols-3 gap-2 text-center text-xs pt-1">
        <div className="p-2 rounded-xl bg-bull-bg border border-bull/20 flex flex-col items-center">
          <div className="flex items-center gap-1 text-bull font-bold font-mono">
            <TrendingUp className="w-3.5 h-3.5" />
            <span>{advances}</span>
          </div>
          <span className="text-[10px] text-fg-subtle mt-0.5">Advances ({advPct}%)</span>
        </div>

        <div className="p-2 rounded-xl bg-bear-bg border border-bear/20 flex flex-col items-center">
          <div className="flex items-center gap-1 text-bear font-bold font-mono">
            <TrendingDown className="w-3.5 h-3.5" />
            <span>{declines}</span>
          </div>
          <span className="text-[10px] text-fg-subtle mt-0.5">Declines ({decPct}%)</span>
        </div>

        <div className="p-2 rounded-xl bg-bg-elevated border border-border flex flex-col items-center">
          <div className="flex items-center gap-1 text-fg-muted font-bold font-mono">
            <Minus className="w-3.5 h-3.5" />
            <span>{unchanged}</span>
          </div>
          <span className="text-[10px] text-fg-subtle mt-0.5">Unchanged ({unchPct}%)</span>
        </div>
      </div>
    </Card>
  );
};
