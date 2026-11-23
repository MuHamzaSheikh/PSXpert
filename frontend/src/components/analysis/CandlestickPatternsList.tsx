import React from 'react';
import { Card } from '@/components/common/Card';
import { Pattern } from '@/types';
import { Sparkles, TrendingUp, TrendingDown, Minus, Calendar } from 'lucide-react';

interface CandlestickPatternsListProps {
  patterns: Pattern[];
}

export const CandlestickPatternsList: React.FC<CandlestickPatternsListProps> = ({ patterns = [] }) => {
  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">Candlestick Patterns Detected</span>
        </div>
        <span className="text-xs font-mono text-fg-subtle">
          {patterns.length} Recent Patterns
        </span>
      </div>

      {patterns.length === 0 ? (
        <div className="py-8 text-center text-xs text-fg-subtle">
          No distinctive reversal or continuation patterns detected in the current lookback window.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {patterns.map((p, idx) => {
            const isBull = p.type === 'BULLISH';
            const isBear = p.type === 'BEARISH';
            return (
              <div
                key={idx}
                className="p-3 rounded-xl border border-border bg-bg-elevated/40 flex items-start justify-between gap-3 text-xs"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-fg">{p.name}</span>
                    <span
                      className={`text-[10px] px-2 py-0.2 rounded-full font-bold border ${isBull
                        ? 'bg-bull-bg text-bull border-bull/30'
                        : isBear
                          ? 'bg-bear-bg text-bear border-bear/30'
                          : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                        }`}
                    >
                      {p.type}
                    </span>
                  </div>
                  <div className="text-fg-muted text-[11px] leading-relaxed">
                    {p.description || p.signal}
                  </div>
                </div>

                <div className="flex items-center gap-1 text-[10px] font-mono text-fg-subtle flex-shrink-0">
                  <Calendar className="w-3 h-3" />
                  <span>{p.date}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};
