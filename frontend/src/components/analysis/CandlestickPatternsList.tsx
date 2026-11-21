import React, { useState } from 'react';
import { Card } from '@/components/common/Card';
import { Pattern } from '@/types';
import { Sparkles, TrendingUp, TrendingDown, Minus, Calendar, Filter, Search, ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface CandlestickPatternsListProps {
  patterns: Pattern[];
  onSelectPattern?: (pattern: Pattern) => void;
  title?: string;
  compact?: boolean;
}

export const CandlestickPatternsList: React.FC<CandlestickPatternsListProps> = ({
  patterns = [],
  onSelectPattern,
  title = 'Candlestick Formations Detected',
  compact = false,
}) => {
  const [filterType, setFilterType] = useState<'ALL' | 'BULLISH' | 'BEARISH' | 'NEUTRAL'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  // Normalize patterns to ensure newest patterns appear first
  const sortedPatterns = React.useMemo(() => {
    return [...patterns].sort((a, b) => b.date.localeCompare(a.date));
  }, [patterns]);

  const filteredPatterns = React.useMemo(() => {
    return sortedPatterns.filter(p => {
      const pType = (p.type || 'NEUTRAL').toUpperCase();
      if (filterType !== 'ALL' && pType !== filterType) return false;

      const name = (p.name || p.pattern || '').toLowerCase();
      const desc = (p.description || p.signal || '').toLowerCase();
      const q = searchQuery.toLowerCase();
      if (q && !name.includes(q) && !desc.includes(q)) return false;

      return true;
    });
  }, [sortedPatterns, filterType, searchQuery]);

  const bullishCount = patterns.filter(p => (p.type || '').toUpperCase() === 'BULLISH').length;
  const bearishCount = patterns.filter(p => (p.type || '').toUpperCase() === 'BEARISH').length;
  const neutralCount = patterns.filter(p => (p.type || '').toUpperCase() === 'NEUTRAL').length;

  return (
    <Card className="p-5 space-y-4">
      {/* Header & Stats Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <span className="font-semibold text-sm text-fg">{title}</span>
            <div className="text-[11px] text-fg-subtle">
              Classical rule-based Japanese candlestick recognition engine
            </div>
          </div>
        </div>

        {/* Breakdown Badges */}
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <span className="px-2 py-0.5 rounded-md bg-bull-bg text-bull font-bold border border-bull/20">
            {bullishCount} Bullish
          </span>
          <span className="px-2 py-0.5 rounded-md bg-bear-bg text-bear font-bold border border-bear/20">
            {bearishCount} Bearish
          </span>
          <span className="px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-500 font-bold border border-amber-500/20">
            {neutralCount} Neutral
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-1 bg-bg-elevated p-0.5 rounded-lg border border-border">
          {(['ALL', 'BULLISH', 'BEARISH', 'NEUTRAL'] as const).map(type => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-colors ${
                filterType === type
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-fg-muted hover:text-fg hover:bg-bg-card'
              }`}
            >
              {type === 'ALL' ? `All (${patterns.length})` : type}
            </button>
          ))}
        </div>

        {!compact && (
          <div className="relative min-w-[180px]">
            <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-subtle" />
            <input
              type="text"
              placeholder="Search formation..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1 bg-bg-elevated border border-border rounded-lg text-xs text-fg placeholder:text-fg-subtle focus:outline-none focus:border-brand-500 transition-colors"
            />
          </div>
        )}
      </div>

      {/* Patterns Grid */}
      {filteredPatterns.length === 0 ? (
        <div className="py-10 text-center space-y-2">
          <div className="w-8 h-8 rounded-full bg-bg-elevated mx-auto flex items-center justify-center text-fg-subtle">
            <Filter className="w-4 h-4" />
          </div>
          <div className="text-xs text-fg-subtle">
            {patterns.length === 0
              ? 'No qualifying non-flat candlestick formations detected in this timeframe.'
              : 'No formations matched your filter criteria.'}
          </div>
        </div>
      ) : (
        <div className={`grid grid-cols-1 ${compact ? 'gap-2.5 max-h-[420px] overflow-y-auto pr-1' : 'md:grid-cols-2 gap-3'}`}>
          {filteredPatterns.map((p, idx) => {
            const isBull = (p.type || '').toUpperCase() === 'BULLISH';
            const isBear = (p.type || '').toUpperCase() === 'BEARISH';
            const patternTitle = p.name || p.pattern || 'Pattern Formation';

            return (
              <div
                key={`${p.date}-${idx}`}
                onClick={() => onSelectPattern?.(p)}
                className={`p-3.5 rounded-xl border border-border bg-bg-elevated/40 hover:bg-bg-elevated hover:border-brand-500/40 transition-all flex flex-col justify-between gap-2.5 text-xs ${
                  onSelectPattern ? 'cursor-pointer' : ''
                }`}
              >
                {/* Top Row: Title, Bias Badge, and Date */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-fg text-sm">{patternTitle}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold border flex items-center gap-1 ${
                        isBull
                          ? 'bg-bull-bg text-bull border-bull/30'
                          : isBear
                          ? 'bg-bear-bg text-bear border-bear/30'
                          : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                      }`}
                    >
                      {isBull && <ArrowUpRight className="w-3 h-3" />}
                      {isBear && <ArrowDownRight className="w-3 h-3" />}
                      {!isBull && !isBear && <Minus className="w-3 h-3" />}
                      <span>{p.type || 'NEUTRAL'}</span>
                    </span>
                  </div>

                  <div className="flex items-center gap-1 text-[11px] font-mono text-fg-subtle flex-shrink-0">
                    <Calendar className="w-3 h-3" />
                    <span>{p.date}</span>
                  </div>
                </div>

                {/* Middle Row: Description / Tactical Meaning */}
                <div className="text-fg-muted text-[11px] leading-relaxed">
                  {p.description || p.signal || 'Reversal or continuation structure identified by automated candle scan.'}
                </div>

                {/* Bottom Row: Close Price & Meta Details */}
                <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[10px] text-fg-subtle font-mono">
                  <div>
                    {p.close !== undefined && (
                      <span>Close: <strong className="text-fg">PKR {p.close.toLocaleString()}</strong></span>
                    )}
                    {p.symbol && <span className="ml-2 font-bold text-brand-600 dark:text-brand-400">[{p.symbol}]</span>}
                  </div>

                  <span className="text-[10px] text-brand-500 hover:underline">
                    View on Chart &rarr;
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};
