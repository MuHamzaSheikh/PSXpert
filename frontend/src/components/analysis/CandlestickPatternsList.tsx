import React, { useState } from 'react';
import { Card } from '@/components/common/Card';
import { Pattern } from '@/types';
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  Calendar,
  Filter,
  Crosshair,
  ShieldCheck,
  Zap,
} from 'lucide-react';

interface CandlestickPatternsListProps {
  patterns: Pattern[];
  onSelectPattern?: (date: string) => void;
  selectedDate?: string | null;
}

/**
 * Visual SVG Candlestick Pattern Depiction Component
 * Renders authentic graphical diagrams of classic candlestick formations
 */
export const PatternSvgVisual: React.FC<{ name: string; type: 'BULLISH' | 'BEARISH' | 'NEUTRAL' }> = ({
  name,
  type,
}) => {
  const norm = name.toUpperCase();
  const bullColor = '#287A50';
  const bearColor = '#C64C4C';
  const neutralColor = '#B88732';

  // 1. Hammer (Small body at top, very long lower shadow)
  if (norm.includes('HAMMER') && !norm.includes('INVERTED')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="20" y1="8" x2="20" y2="10" stroke={bullColor} strokeWidth="2" strokeLinecap="round" />
        <rect x="14" y="10" width="12" height="9" fill={bullColor} rx="1" />
        <line x1="20" y1="19" x2="20" y2="34" stroke={bullColor} strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  // 2. Inverted Hammer (Long upper shadow, small body at bottom)
  if (norm.includes('INVERTED HAMMER')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="20" y1="6" x2="20" y2="21" stroke={bullColor} strokeWidth="2" strokeLinecap="round" />
        <rect x="14" y="21" width="12" height="9" fill={bullColor} rx="1" />
        <line x1="20" y1="30" x2="20" y2="33" stroke={bullColor} strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  // 3. Shooting Star (Long upper shadow, small body at bottom after rally)
  if (norm.includes('SHOOTING STAR')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="20" y1="6" x2="20" y2="22" stroke={bearColor} strokeWidth="2" strokeLinecap="round" />
        <rect x="14" y="22" width="12" height="9" fill={bearColor} rx="1" />
        <line x1="20" y1="31" x2="20" y2="33" stroke={bearColor} strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  // 4. Hanging Man (Small body at top, long lower shadow after rally)
  if (norm.includes('HANGING MAN')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="20" y1="7" x2="20" y2="9" stroke={bearColor} strokeWidth="2" strokeLinecap="round" />
        <rect x="14" y="9" width="12" height="9" fill={bearColor} rx="1" />
        <line x1="20" y1="18" x2="20" y2="33" stroke={bearColor} strokeWidth="2" strokeLinecap="round" />
      </svg>
    );
  }

  // 5. Bullish Engulfing (Small red candle swallowed by tall green candle)
  if (norm.includes('ENGULFING') && norm.includes('BULLISH')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        {/* Day 1: Red inside */}
        <line x1="12" y1="13" x2="12" y2="27" stroke={bearColor} strokeWidth="1.5" />
        <rect x="8" y="16" width="8" height="8" fill={bearColor} rx="1" />
        {/* Day 2: Tall Green engulfing */}
        <line x1="26" y1="6" x2="26" y2="34" stroke={bullColor} strokeWidth="2" />
        <rect x="20" y="10" width="12" height="20" fill={bullColor} rx="1.5" />
      </svg>
    );
  }

  // 6. Bearish Engulfing (Small green candle swallowed by tall red candle)
  if (norm.includes('ENGULFING') && norm.includes('BEARISH')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        {/* Day 1: Green inside */}
        <line x1="12" y1="13" x2="12" y2="27" stroke={bullColor} strokeWidth="1.5" />
        <rect x="8" y="16" width="8" height="8" fill={bullColor} rx="1" />
        {/* Day 2: Tall Red engulfing */}
        <line x1="26" y1="6" x2="26" y2="34" stroke={bearColor} strokeWidth="2" />
        <rect x="20" y="10" width="12" height="20" fill={bearColor} rx="1.5" />
      </svg>
    );
  }

  // 7. Morning Star (Tall red, gap down small star, tall green)
  if (norm.includes('MORNING STAR')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        {/* Bar 1: Red */}
        <line x1="8" y1="6" x2="8" y2="28" stroke={bearColor} strokeWidth="1.5" />
        <rect x="5" y="10" width="6" height="14" fill={bearColor} rx="1" />
        {/* Bar 2: Star gap down */}
        <line x1="20" y1="26" x2="20" y2="36" stroke={neutralColor} strokeWidth="1.5" />
        <rect x="17" y="28" width="6" height="4" fill={neutralColor} rx="0.5" />
        {/* Bar 3: Green rally */}
        <line x1="32" y1="8" x2="32" y2="30" stroke={bullColor} strokeWidth="1.5" />
        <rect x="29" y="12" width="6" height="14" fill={bullColor} rx="1" />
      </svg>
    );
  }

  // 8. Evening Star (Tall green, gap up small star, tall red)
  if (norm.includes('EVENING STAR')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        {/* Bar 1: Green */}
        <line x1="8" y1="12" x2="8" y2="34" stroke={bullColor} strokeWidth="1.5" />
        <rect x="5" y="16" width="6" height="14" fill={bullColor} rx="1" />
        {/* Bar 2: Star gap up */}
        <line x1="20" y1="4" x2="20" y2="14" stroke={neutralColor} strokeWidth="1.5" />
        <rect x="17" y="6" width="6" height="4" fill={neutralColor} rx="0.5" />
        {/* Bar 3: Red reversal */}
        <line x1="32" y1="10" x2="32" y2="32" stroke={bearColor} strokeWidth="1.5" />
        <rect x="29" y="14" width="6" height="14" fill={bearColor} rx="1" />
      </svg>
    );
  }

  // 9. Three White Soldiers (3 consecutive rising green candles)
  if (norm.includes('THREE WHITE SOLDIERS') || norm.includes('WHITE SOLDIERS')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="8" y1="22" x2="8" y2="36" stroke={bullColor} strokeWidth="1.5" />
        <rect x="5" y="24" width="6" height="10" fill={bullColor} rx="1" />

        <line x1="20" y1="14" x2="20" y2="28" stroke={bullColor} strokeWidth="1.5" />
        <rect x="17" y="16" width="6" height="10" fill={bullColor} rx="1" />

        <line x1="32" y1="6" x2="32" y2="20" stroke={bullColor} strokeWidth="1.5" />
        <rect x="29" y="8" width="6" height="10" fill={bullColor} rx="1" />
      </svg>
    );
  }

  // 10. Three Black Crows (3 consecutive falling red candles)
  if (norm.includes('THREE BLACK CROWS') || norm.includes('BLACK CROWS')) {
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="8" y1="6" x2="8" y2="20" stroke={bearColor} strokeWidth="1.5" />
        <rect x="5" y="8" width="6" height="10" fill={bearColor} rx="1" />

        <line x1="20" y1="14" x2="20" y2="28" stroke={bearColor} strokeWidth="1.5" />
        <rect x="17" y="16" width="6" height="10" fill={bearColor} rx="1" />

        <line x1="32" y1="22" x2="32" y2="36" stroke={bearColor} strokeWidth="1.5" />
        <rect x="29" y="24" width="6" height="10" fill={bearColor} rx="1" />
      </svg>
    );
  }

  // 11. Doji / Dragonfly / Gravestone (Cross or T-shape)
  if (norm.includes('DOJI')) {
    const isDragonfly = norm.includes('DRAGONFLY');
    const isGravestone = norm.includes('GRAVESTONE');
    const yCross = isDragonfly ? 12 : isGravestone ? 28 : 20;

    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <line x1="20" y1="6" x2="20" y2="34" stroke={neutralColor} strokeWidth="2" strokeLinecap="round" />
        <line x1="10" y1={yCross} x2="30" y2={yCross} stroke={neutralColor} strokeWidth="3" strokeLinecap="round" />
      </svg>
    );
  }

  // 12. Marubozu (Solid full-body candle without shadows)
  if (norm.includes('MARUBOZU')) {
    const color = type === 'BULLISH' ? bullColor : bearColor;
    return (
      <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
        <rect x="12" y="6" width="16" height="28" fill={color} rx="1.5" />
      </svg>
    );
  }

  // Default Fallback Candle
  const color = type === 'BULLISH' ? bullColor : type === 'BEARISH' ? bearColor : neutralColor;
  return (
    <svg className="w-10 h-10 flex-shrink-0" viewBox="0 0 40 40">
      <line x1="20" y1="6" x2="20" y2="34" stroke={color} strokeWidth="1.5" strokeLinecap="round" />
      <rect x="13" y="12" width="14" height="16" fill={color} rx="1" />
    </svg>
  );
};

export const CandlestickPatternsList: React.FC<CandlestickPatternsListProps> = ({
  patterns = [],
  onSelectPattern,
  selectedDate,
}) => {
  const [filter, setFilter] = useState<'ALL' | 'BULLISH' | 'BEARISH'>('ALL');

  const filteredPatterns = patterns.filter(p => {
    if (filter === 'ALL') return true;
    return p.type === filter;
  });

  return (
    <Card className="p-5 space-y-4">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-xl bg-[#2F7D68]/15 text-[#2F7D68] dark:text-[#3DA88D]">
            <Sparkles className="w-4 h-4" />
          </div>
          <div>
            <h3 className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Candlestick Pattern Recognition Engine</h3>
            <p className="text-[11px] text-[#77736C] dark:text-[#9E988E]">
              Authentic multi-candle formations detected by PSXpert quantitative engine
            </p>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1 bg-[#E7E0D5]/50 dark:bg-[#1C2022]/70 p-1 rounded-full border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20 text-xs">
          <button
            onClick={() => setFilter('ALL')}
            className={`px-3 py-1 rounded-full font-semibold transition-all ${
              filter === 'ALL'
                ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-sm'
                : 'text-[#77736C] hover:text-[#252A2B] dark:hover:text-[#F4EFE6]'
            }`}
          >
            All ({patterns.length})
          </button>
          <button
            onClick={() => setFilter('BULLISH')}
            className={`px-3 py-1 rounded-full font-semibold transition-all ${
              filter === 'BULLISH'
                ? 'bg-gradient-to-r from-[#287A50] to-[#1F5C4C] text-white shadow-sm'
                : 'text-[#77736C] hover:text-[#287A50]'
            }`}
          >
            Bullish ({patterns.filter(p => p.type === 'BULLISH').length})
          </button>
          <button
            onClick={() => setFilter('BEARISH')}
            className={`px-3 py-1 rounded-full font-semibold transition-all ${
              filter === 'BEARISH'
                ? 'bg-gradient-to-r from-[#C64C4C] to-[#A03838] text-white shadow-sm'
                : 'text-[#77736C] hover:text-[#C64C4C]'
            }`}
          >
            Bearish ({patterns.filter(p => p.type === 'BEARISH').length})
          </button>
        </div>
      </div>

      {/* Pattern Cards List */}
      {filteredPatterns.length === 0 ? (
        <div className="py-12 text-center text-xs text-[#77736C] dark:text-[#9E988E] space-y-1">
          <div className="text-base font-semibold text-[#252A2B] dark:text-[#F4EFE6]">No patterns in selected category</div>
          <p>Try switching to "All" to inspect other detected formations in this lookback window.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredPatterns.map((p, idx) => {
            const isBull = p.type === 'BULLISH';
            const isBear = p.type === 'BEARISH';
            const isSelected = selectedDate === p.date;

            // Compute confidence/strength badge
            let strengthText = 'High Probability';
            if (p.name.includes('Star') || p.name.includes('Engulfing') || p.name.includes('Soldiers') || p.name.includes('Crows')) {
              strengthText = 'Strong Reversal (3-Star)';
            } else if (p.name.includes('Hammer') || p.name.includes('Harami') || p.name.includes('Marubozu')) {
              strengthText = 'Moderate Reversal (2-Star)';
            } else {
              strengthText = 'Indecision / Pivot';
            }

            return (
              <div
                key={`${p.name}-${p.date}-${idx}`}
                onClick={() => onSelectPattern?.(p.date)}
                className={`p-3.5 rounded-2xl border transition-all cursor-pointer flex items-start gap-3 text-xs ${
                  isSelected
                    ? 'border-[#694E7A] bg-[#694E7A]/10 shadow-sm ring-1 ring-[#694E7A]/30'
                    : 'border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 hover:bg-[#FFFCF6]'
                }`}
              >
                {/* SVG Visual Candlestick Representation */}
                <div className="p-1 rounded-xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
                  <PatternSvgVisual name={p.name} type={p.type} />
                </div>

                {/* Pattern Information */}
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-1.5">
                    <span className="font-bold text-[#252A2B] dark:text-[#F4EFE6] text-[13px]">{p.name}</span>
                    <span
                      className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                        isBull
                          ? 'bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border-[#287A50]/30'
                          : isBear
                          ? 'bg-[#C64C4C]/15 text-[#C64C4C] dark:text-[#E05C5C] border-[#C64C4C]/30'
                          : 'bg-[#B88732]/15 text-[#B88732] border-[#B88732]/30'
                      }`}
                    >
                      {p.type} {isBull ? '▲' : isBear ? '▼' : '●'}
                    </span>
                  </div>

                  {/* Signal Strength & Date Badges */}
                  <div className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className="inline-flex items-center gap-1 font-semibold text-[#77736C] dark:text-[#9E988E]">
                      <Zap className="w-3 h-3 text-[#B88732]" />
                      <span>{strengthText}</span>
                    </span>
                    <span className="text-[#DDD5C9]">•</span>
                    <span className="inline-flex items-center gap-1 font-mono text-[#77736C] dark:text-[#9E988E]">
                      <Calendar className="w-3 h-3" />
                      <span>{p.date}</span>
                    </span>
                  </div>

                  {/* Plain-English Explanation */}
                  <p className="text-[#77736C] dark:text-[#9E988E] text-[11px] leading-relaxed line-clamp-2">
                    {p.description || p.signal || 'Reversal pattern indicating potential trend redirection.'}
                  </p>

                  {/* Interactive Chart Focus Button */}
                  {onSelectPattern && (
                    <div className="pt-1 flex items-center justify-between text-[11px]">
                      <span className="text-[#2F7D68] dark:text-[#3DA88D] font-semibold inline-flex items-center gap-1 hover:underline">
                        <Crosshair className="w-3 h-3" />
                        <span>Focus on Chart</span>
                      </span>
                      {isSelected && (
                        <span className="text-[10px] font-bold text-[#694E7A] dark:text-[#A888BF]">
                          Active Selection
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};
