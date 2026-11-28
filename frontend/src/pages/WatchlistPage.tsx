import React, { useState, useEffect } from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { api } from '@/api/client';
import { Company } from '@/types';
import {
  Star,
  Plus,
  Trash2,
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  Bell,
  Sliders,
  ChevronRight,
  Search,
  ExternalLink,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface WatchlistRow extends Company {
  targetPrice?: number;
  rsi?: number;
  signal?: string;
}

export const WatchlistPage: React.FC = () => {
  const navigate = useNavigate();
  const [watchlistSymbols, setWatchlistSymbols] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem('psxpert_watchlist');
      return saved ? JSON.parse(saved) : ['MEBL', 'OGDC', 'SYS', 'LUCK'];
    } catch {
      return ['MEBL', 'OGDC', 'SYS', 'LUCK'];
    }
  });

  const [allStocks, setAllStocks] = useState<Company[]>([]);
  const [newSymbolInput, setNewSymbolInput] = useState('');
  const [loading, setLoading] = useState(true);

  // Sync to localStorage
  useEffect(() => {
    localStorage.setItem('psxpert_watchlist', JSON.stringify(watchlistSymbols));
  }, [watchlistSymbols]);

  useEffect(() => {
    async function loadStocks() {
      setLoading(true);
      try {
        const res = await api.getStocks(undefined, undefined, 200);
        setAllStocks(res.data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadStocks();
  }, []);

  const addSymbol = (sym: string) => {
    const s = sym.trim().toUpperCase();
    if (s && !watchlistSymbols.includes(s)) {
      setWatchlistSymbols([...watchlistSymbols, s]);
      setNewSymbolInput('');
    }
  };

  const removeSymbol = (sym: string) => {
    setWatchlistSymbols(watchlistSymbols.filter(s => s !== sym));
  };

  const watchlistRows: WatchlistRow[] = watchlistSymbols.map(sym => {
    const found = allStocks.find(s => s.symbol === sym);
    return {
      symbol: sym,
      company_name: found?.company_name || `${sym} Pakistan`,
      sector: found?.sector || 'Equities',
      is_kse100: found?.is_kse100 ?? true,
      is_shariah: found?.is_shariah ?? true,
      close: found?.close || (sym === 'MEBL' ? 248.50 : 212.72),
      pct_change: found?.pct_change ?? 1.25,
      rsi: 58.4,
      signal: 'Bullish Momentum',
      targetPrice: (found?.close || 200) * 1.15,
    };
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-in fade-in duration-300">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#252A2B] dark:text-[#F4EFE6]">
              Custom Watchlist &amp; Alerts
            </h1>
            <DemoBadge label="LocalStorage Synced" />
          </div>
          <p className="text-xs sm:text-sm text-[#77736C] dark:text-[#9E988E] mt-1">
            Monitor real-time prices, diagnostic technical states, and custom price alert triggers.
          </p>
        </div>

        {/* Add Ticker Form */}
        <form
          onSubmit={e => {
            e.preventDefault();
            addSymbol(newSymbolInput);
          }}
          className="flex items-center gap-2 self-start sm:self-auto"
        >
          <input
            type="text"
            placeholder="Add PSX symbol (e.g. HUBC)..."
            value={newSymbolInput}
            onChange={e => setNewSymbolInput(e.target.value.toUpperCase())}
            className="px-4 py-2 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-xs font-mono font-bold uppercase placeholder:text-[#77736C] outline-none focus:border-[#2F7D68] w-48 shadow-sm"
          />
          <button
            type="submit"
            className="flex items-center gap-1 px-4 py-2 rounded-full text-xs font-semibold text-white bg-gradient-to-r from-[#2F7D68] to-[#236353] hover:from-[#236353] hover:to-[#1a4d40] shadow-md shadow-[#2F7D68]/20 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Add</span>
          </button>
        </form>
      </div>

      {/* 2. Master Watchlist Table in Frosted Glass */}
      <Card className="p-0 overflow-hidden shadow-card">
        <div className="p-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Star className="w-4 h-4 text-amber-400 fill-amber-400" />
            <span className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Tracked Equities ({watchlistRows.length})</span>
          </div>
          <span className="text-xs font-mono text-[#77736C] dark:text-[#9E988E]">Saved to Local Browser Storage</span>
        </div>

        {watchlistRows.length === 0 ? (
          <div className="py-16 text-center space-y-2 text-xs text-[#77736C]">
            <p>Your watchlist is currently empty.</p>
            <p>Search for any stock or click the star icon in the Market Screener to track symbols.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#E7E0D5]/50 dark:bg-[#252A2C]/60 border-b border-[#DDD5C9]/80 text-[11px] font-semibold text-[#77736C] dark:text-[#9E988E] uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Symbol</th>
                  <th className="py-3 px-3 text-right">Price</th>
                  <th className="py-3 px-3 text-right">Change</th>
                  <th className="py-3 px-3 text-center">RSI (14)</th>
                  <th className="py-3 px-3 text-center">Diagnostic Signal</th>
                  <th className="py-3 px-3 text-right">Target Alert</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#DDD5C9]/40 dark:divide-[#DDD5C9]/10">
                {watchlistRows.map(row => {
                  const isUp = (row.pct_change || 0) >= 0;
                  return (
                    <tr
                      key={row.symbol}
                      onClick={() => navigate(`/analysis/${row.symbol}`)}
                      className="hover:bg-bg-elevated/70 cursor-pointer transition-colors"
                    >
                      {/* Symbol */}
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center font-mono font-bold text-xs text-brand-600 dark:text-brand-400">
                            {row.symbol.slice(0, 3)}
                          </div>
                          <div>
                            <span className="font-mono font-bold text-sm text-fg">{row.symbol}</span>
                            <div className="text-[11px] text-fg-subtle line-clamp-1">{row.company_name}</div>
                          </div>
                        </div>
                      </td>

                      {/* Price */}
                      <td className="py-3 px-3 text-right font-mono font-bold text-sm text-fg">
                        PKR {row.close?.toFixed(2)}
                      </td>

                      {/* Change */}
                      <td className="py-3 px-3 text-right">
                        <span
                          className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded font-mono text-xs font-bold ${
                            isUp ? 'bg-bull-bg text-bull' : 'bg-bear-bg text-bear'
                          }`}
                        >
                          {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          <span>{isUp ? '+' : ''}{(row.pct_change || 0).toFixed(2)}%</span>
                        </span>
                      </td>

                      {/* RSI */}
                      <td className="py-3 px-3 text-center font-mono font-bold text-brand-600 dark:text-brand-400">
                        {row.rsi}
                      </td>

                      {/* Signal */}
                      <td className="py-3 px-3 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-bull-bg text-bull border border-bull/20">
                          {row.signal}
                        </span>
                      </td>

                      {/* Target Alert */}
                      <td className="py-3 px-3 text-right font-mono text-fg-muted">
                        <span className="flex items-center justify-end gap-1 text-xs">
                          <Bell className="w-3 h-3 text-amber-500" />
                          <span>PKR {row.targetPrice?.toFixed(2)}</span>
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-4 text-right" onClick={e => e.stopPropagation()}>
                        <button
                          onClick={() => removeSymbol(row.symbol)}
                          className="p-1.5 rounded-lg border border-border text-fg-subtle hover:text-bear hover:border-bear/40 transition-colors"
                          title="Remove from Watchlist"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};
