import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { ArrowUpRight, ArrowDownRight, Flame, TrendingUp, TrendingDown, ChevronRight } from 'lucide-react';
import { Company } from '@/types';

interface MarketMoversTableProps {
  stocks: Company[];
}

type TabType = 'active' | 'gainers' | 'losers';
type FilterType = 'all' | 'kse100' | 'islamic';

export const MarketMoversTable: React.FC<MarketMoversTableProps> = ({ stocks = [] }) => {
  const [activeTab, setActiveTab] = useState<TabType>('active');
  const [filter, setFilter] = useState<FilterType>('kse100');
  const navigate = useNavigate();

  // 1. Filter stocks by universe
  let filtered = stocks.filter(s => {
    if (filter === 'kse100') return s.is_kse100;
    if (filter === 'islamic') return s.is_shariah;
    return true;
  });

  // 2. Sort by tab mode
  if (activeTab === 'active') {
    filtered.sort((a, b) => (b.volume || 0) - (a.volume || 0));
  } else if (activeTab === 'gainers') {
    filtered.sort((a, b) => (b.pct_change || 0) - (a.pct_change || 0));
  } else if (activeTab === 'losers') {
    filtered.sort((a, b) => (a.pct_change || 0) - (b.pct_change || 0));
  }

  const displayedStocks = filtered.slice(0, 8);

  const formatVolume = (vol?: number) => {
    if (!vol) return '0';
    if (vol >= 1000000) return `${(vol / 1000000).toFixed(2)}M`;
    if (vol >= 1000) return `${(vol / 1000).toFixed(1)}K`;
    return vol.toLocaleString();
  };

  return (
    <Card className="p-5 flex flex-col justify-between">
      {/* Table Header Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4 mb-4">
        {/* Pill Tabs: Most Active / Gainers / Losers */}
        <div className="flex items-center gap-1 bg-bg-elevated p-1 rounded-xl border border-border self-start">
          <button
            onClick={() => setActiveTab('active')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'active'
                ? 'bg-brand-500 text-white shadow-sm'
                : 'text-fg-muted hover:text-fg hover:bg-bg-card'
            }`}
          >
            <Flame className="w-3.5 h-3.5" />
            <span>Most Active</span>
          </button>
          <button
            onClick={() => setActiveTab('gainers')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'gainers'
                ? 'bg-bull text-white shadow-sm'
                : 'text-fg-muted hover:text-fg hover:bg-bg-card'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Gainers</span>
          </button>
          <button
            onClick={() => setActiveTab('losers')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === 'losers'
                ? 'bg-bear text-white shadow-sm'
                : 'text-fg-muted hover:text-fg hover:bg-bg-card'
            }`}
          >
            <TrendingDown className="w-3.5 h-3.5" />
            <span>Losers</span>
          </button>
        </div>

        {/* Filter Chips: KSE 100 / All / Islamic */}
        <div className="flex items-center gap-1.5 self-start sm:self-auto">
          {(['kse100', 'all', 'islamic'] as FilterType[]).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2.5 py-1 rounded-full text-xs font-semibold border transition-colors ${
                filter === f
                  ? 'border-brand-500 bg-brand-500/10 text-brand-600 dark:text-brand-400'
                  : 'border-border text-fg-subtle hover:text-fg hover:border-fg-subtle/50'
              }`}
            >
              {f === 'kse100' ? 'KSE 100' : f === 'all' ? 'All Stocks' : 'Islamic'}
            </button>
          ))}
        </div>
      </div>

      {/* Responsive Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead>
            <tr className="border-b border-border text-fg-subtle text-[11px] font-semibold uppercase tracking-wider">
              <th className="pb-2.5 pl-1">Symbol & Company</th>
              <th className="pb-2.5 text-right">Price (PKR)</th>
              <th className="pb-2.5 text-right">Change</th>
              <th className="pb-2.5 text-right pr-1">Volume</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/40">
            {displayedStocks.map(stock => {
              const isBull = (stock.pct_change || 0) >= 0;
              return (
                <tr
                  key={stock.symbol}
                  onClick={() => navigate(`/analysis/${stock.symbol}`)}
                  className="group hover:bg-bg-elevated/70 cursor-pointer transition-colors"
                >
                  {/* Stock Symbol & Company Badge */}
                  <td className="py-2.5 pl-1">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center font-mono font-bold text-xs text-brand-600 dark:text-brand-400 group-hover:scale-105 transition-transform">
                        {stock.symbol.slice(0, 3)}
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono font-bold text-fg group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
                            {stock.symbol}
                          </span>
                          {stock.is_shariah && (
                            <span className="text-[9px] px-1 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 font-medium">
                              Shariah
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-fg-subtle line-clamp-1 max-w-[140px] sm:max-w-[200px]">
                          {stock.company_name}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Price */}
                  <td className="py-2.5 text-right font-mono font-bold text-fg text-sm">
                    {stock.close ? stock.close.toFixed(2) : '--'}
                  </td>

                  {/* Change % Pill */}
                  <td className="py-2.5 text-right">
                    <span
                      className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded-md font-mono text-xs font-bold ${
                        isBull ? 'bg-bull-bg text-bull' : 'bg-bear-bg text-bear'
                      }`}
                    >
                      {isBull ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      <span>{isBull ? '+' : ''}{(stock.pct_change || 0).toFixed(2)}%</span>
                    </span>
                  </td>

                  {/* Volume */}
                  <td className="py-2.5 text-right pr-1 font-mono text-fg-muted">
                    {formatVolume(stock.volume)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer link to full screener */}
      <div className="pt-3 mt-2 border-t border-border flex items-center justify-between text-xs">
        <span className="text-fg-subtle text-[11px]">Real-time EOD tick feed</span>
        <button
          onClick={() => navigate('/screener')}
          className="flex items-center gap-1 font-semibold text-brand-600 dark:text-brand-400 hover:underline"
        >
          <span>View All PSX Stocks</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </Card>
  );
};
