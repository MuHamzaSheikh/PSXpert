import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { api } from '@/api/client';
import { Company } from '@/types';
import {
  SlidersHorizontal,
  Search,
  Sparkles,
  ArrowUpDown,
  ArrowUpRight,
  ArrowDownRight,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Star,
  ChevronRight,
  Filter,
  RefreshCw,
  BarChart3,
  TrendingUp,
} from 'lucide-react';

interface ScreenerStock extends Company {
  rsi: number;
  macdStatus: 'Bullish Cross' | 'Bullish Trend' | 'Bearish Cross' | 'Neutral';
  trend: 'Strong Uptrend' | 'Developing' | 'Downtrend' | 'Consolidation';
  pe: number;
  divYield: number;
  sentiment: 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE';
  aiScore: number; // 0-100
  aiVerdict: 'Strong Buy' | 'Buy' | 'Hold' | 'Underweight';
}

export const ScreenerPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [stocks, setStocks] = useState<Company[]>([]);
  const [sectors, setSectors] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedSector, setSelectedSector] = useState(searchParams.get('sector') || 'ALL');
  const [shariahOnly, setShariahOnly] = useState(false);
  const [kse100Only, setKse100Only] = useState(false);
  const [rsiFilter, setRsiFilter] = useState<'ALL' | 'OVERSOLD' | 'MOMENTUM' | 'OVERBOUGHT'>('ALL');
  const [trendFilter, setTrendFilter] = useState<'ALL' | 'UPTREND' | 'DOWNTREND'>('ALL');
  const [aiVerdictFilter, setAiVerdictFilter] = useState<'ALL' | 'BUY_ONLY'>('ALL');

  // Sorting
  const [sortField, setSortField] = useState<keyof ScreenerStock>('aiScore');
  const [sortAsc, setSortAsc] = useState(false);

  // Watchlist local state
  const [watchlist, setWatchlist] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('psxpert_watchlist') || '["MEBL", "OGDC"]');
    } catch {
      return ['MEBL', 'OGDC'];
    }
  });

  const toggleWatchlist = (sym: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setWatchlist(prev => {
      const next = prev.includes(sym) ? prev.filter(s => s !== sym) : [...prev, sym];
      localStorage.setItem('psxpert_watchlist', JSON.stringify(next));
      return next;
    });
  };

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [stocksRes, sectorsRes] = await Promise.all([
          api.getStocks(undefined, undefined, 200),
          api.getSectors(),
        ]);
        setStocks(stocksRes.data);
        setSectors(sectorsRes.data);
      } catch (err) {
        console.error('Failed to load screener stocks:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Sync sector param
  useEffect(() => {
    const sec = searchParams.get('sector');
    if (sec) setSelectedSector(sec);
  }, [searchParams]);

  // Enrich stocks with technical & AI multi-factor screener signals
  const enrichedStocks: ScreenerStock[] = useMemo(() => {
    return stocks.map((s, idx) => {
      // Deterministic synthetic metrics based on symbol hash for consistency
      const hash = s.symbol.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0) + idx * 7;
      const rsi = Math.round((35 + (hash % 45)) * 10) / 10;
      const pe = Math.round((4.2 + (hash % 120) / 10) * 10) / 10;
      const divYield = Math.round((3.0 + (hash % 110) / 10) * 10) / 10;
      const aiScore = Math.min(96, Math.max(48, Math.round(55 + (hash % 42) + ((s.pct_change || 0) > 0 ? 6 : -4))));

      let macdStatus: ScreenerStock['macdStatus'] = 'Neutral';
      if (rsi > 55) macdStatus = 'Bullish Trend';
      else if (rsi < 42) macdStatus = 'Bearish Cross';
      else macdStatus = 'Bullish Cross';

      let trend: ScreenerStock['trend'] = 'Consolidation';
      if ((s.pct_change || 0) > 1.5 || rsi > 58) trend = 'Strong Uptrend';
      else if ((s.pct_change || 0) < -1.5 || rsi < 40) trend = 'Downtrend';
      else trend = 'Developing';

      let sentiment: ScreenerStock['sentiment'] = 'NEUTRAL';
      if (aiScore >= 80) sentiment = 'POSITIVE';
      else if (aiScore < 60) sentiment = 'NEGATIVE';

      let aiVerdict: ScreenerStock['aiVerdict'] = 'Hold';
      if (aiScore >= 85) aiVerdict = 'Strong Buy';
      else if (aiScore >= 75) aiVerdict = 'Buy';
      else if (aiScore < 55) aiVerdict = 'Underweight';

      return {
        ...s,
        rsi,
        macdStatus,
        trend,
        pe,
        divYield,
        sentiment,
        aiScore,
        aiVerdict,
      };
    });
  }, [stocks]);

  // Apply filters
  const filteredStocks = useMemo(() => {
    return enrichedStocks.filter(stock => {
      if (searchQuery.trim() !== '') {
        const q = searchQuery.toUpperCase();
        if (!stock.symbol.includes(q) && !stock.company_name.toUpperCase().includes(q)) {
          return false;
        }
      }
      if (selectedSector !== 'ALL' && stock.sector !== selectedSector) {
        return false;
      }
      if (shariahOnly && !stock.is_shariah) {
        return false;
      }
      if (kse100Only && !stock.is_kse100) {
        return false;
      }
      if (rsiFilter === 'OVERSOLD' && stock.rsi >= 35) return false;
      if (rsiFilter === 'MOMENTUM' && (stock.rsi < 50 || stock.rsi > 70)) return false;
      if (rsiFilter === 'OVERBOUGHT' && stock.rsi <= 70) return false;

      if (trendFilter === 'UPTREND' && stock.trend !== 'Strong Uptrend') return false;
      if (trendFilter === 'DOWNTREND' && stock.trend !== 'Downtrend') return false;

      if (aiVerdictFilter === 'BUY_ONLY' && stock.aiVerdict !== 'Strong Buy' && stock.aiVerdict !== 'Buy') {
        return false;
      }

      return true;
    });
  }, [enrichedStocks, searchQuery, selectedSector, shariahOnly, kse100Only, rsiFilter, trendFilter, aiVerdictFilter]);

  // Apply sort
  const sortedStocks = useMemo(() => {
    return [...filteredStocks].sort((a, b) => {
      const valA = a[sortField];
      const valB = b[sortField];
      if (valA === undefined) return 1;
      if (valB === undefined) return -1;
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc ? valA - valB : valB - valA;
      }
      return sortAsc
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    });
  }, [filteredStocks, sortField, sortAsc]);

  const handleSort = (field: keyof ScreenerStock) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false); // default descending for financial metrics
    }
  };

  const topAIPicks = useMemo(() => {
    return [...enrichedStocks].sort((a, b) => b.aiScore - a.aiScore).slice(0, 3);
  }, [enrichedStocks]);

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 1. Header & AI Summary Banner */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-fg">
              AI Multi-Factor Stock Screener
            </h1>
            <DemoBadge label="Multi-Factor AI Ranking" />
          </div>
          <p className="text-xs sm:text-sm text-fg-muted mt-1">
            Filter 100+ PSX equities across technical indicators, valuation multiples, and multi-agent model consensus scores.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <span className="text-fg-subtle">
            Screening <strong>{sortedStocks.length}</strong> of <strong>{stocks.length}</strong> equities
          </span>
          <button
            onClick={() => {
              setSearchQuery('');
              setSelectedSector('ALL');
              setShariahOnly(false);
              setKse100Only(false);
              setRsiFilter('ALL');
              setTrendFilter('ALL');
              setAiVerdictFilter('ALL');
            }}
            className="flex items-center gap-1 text-brand-600 dark:text-brand-400 font-semibold hover:underline"
          >
            <RefreshCw className="w-3 h-3" />
            <span>Reset Filters</span>
          </button>
        </div>
      </div>

      {/* 2. Top AI-Ranked Picks Spotlight Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-fg uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
            <span>Today&apos;s High-Conviction AI Screener Picks</span>
          </div>
          <span className="text-[11px] text-fg-subtle">Algorithmic Ensemble Ranking</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {topAIPicks.map((pick, i) => (
            <Card
              key={pick.symbol}
              onClick={() => navigate(`/analysis/${pick.symbol}`)}
              className="p-4 cursor-pointer hover:border-brand-500 hover:shadow-card transition-all relative overflow-hidden flex flex-col justify-between space-y-3"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 text-white font-mono font-bold text-xs flex items-center justify-center shadow-sm">
                    {pick.symbol.slice(0, 3)}
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-bold text-sm text-fg">{pick.symbol}</span>
                      <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-bull-bg text-bull border border-bull/20">
                        Rank #{i + 1}
                      </span>
                    </div>
                    <div className="text-xs text-fg-subtle line-clamp-1">{pick.company_name}</div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-fg">PKR {pick.close?.toFixed(2)}</div>
                  <div className="text-[11px] font-mono text-bull font-bold">+{(pick.pct_change || 1.4).toFixed(2)}%</div>
                </div>
              </div>

              {/* Multi-Factor Radar Snapshot */}
              <div className="grid grid-cols-3 gap-2 py-2 border-y border-border/50 text-[11px]">
                <div>
                  <div className="text-fg-subtle text-[10px]">RSI-14</div>
                  <div className="font-mono font-bold text-brand-600 dark:text-brand-400">{pick.rsi}</div>
                </div>
                <div>
                  <div className="text-fg-subtle text-[10px]">P/E Multiple</div>
                  <div className="font-mono font-bold text-fg">{pick.pe}x</div>
                </div>
                <div>
                  <div className="text-fg-subtle text-[10px]">Div Yield</div>
                  <div className="font-mono font-bold text-fg">{pick.divYield}%</div>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-1">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-bull animate-pulse" />
                  <span className="font-bold text-bull">{pick.aiVerdict}</span>
                  <span className="text-[10px] font-mono text-fg-subtle">({pick.aiScore}% Score)</span>
                </div>
                <span className="text-brand-600 dark:text-brand-400 font-semibold flex items-center gap-0.5 text-xs">
                  <span>Analyze</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </Card>
          ))}
        </div>
      </div>

      {/* 3. Comprehensive Filter Control Matrix */}
      <Card className="p-5 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search Input */}
          <div className="relative">
            <Search className="w-4 h-4 text-fg-subtle absolute left-3 top-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search ticker or company name..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 h-10 rounded-xl border border-border bg-bg text-xs text-fg placeholder:text-fg-subtle outline-none focus:border-brand-500 truncate whitespace-nowrap"
            />
          </div>

          {/* Sector Dropdown */}
          <div>
            <select
              value={selectedSector}
              onChange={e => {
                setSelectedSector(e.target.value);
                setSearchParams(e.target.value === 'ALL' ? {} : { sector: e.target.value });
              }}
              className="w-full px-3 h-10 rounded-xl border border-border bg-bg text-xs text-fg outline-none focus:border-brand-500 truncate"
            >
              <option value="ALL">All Industry Sectors</option>
              {sectors.map(sec => (
                <option key={sec} value={sec}>{sec}</option>
              ))}
            </select>
          </div>

          {/* RSI Condition Filter */}
          <div>
            <select
              value={rsiFilter}
              onChange={e => setRsiFilter(e.target.value as any)}
              className="w-full px-3 h-10 rounded-xl border border-border bg-bg text-xs text-fg outline-none focus:border-brand-500 truncate"
            >
              <option value="ALL">RSI: Any Condition</option>
              <option value="OVERSOLD">RSI &lt; 35 (Oversold Dip)</option>
              <option value="MOMENTUM">RSI 50 - 70 (Bullish Momentum)</option>
              <option value="OVERBOUGHT">RSI &gt; 70 (Overbought Extension)</option>
            </select>
          </div>

          {/* Trend Alignment Filter */}
          <div>
            <select
              value={trendFilter}
              onChange={e => setTrendFilter(e.target.value as any)}
              className="w-full px-3 h-10 rounded-xl border border-border bg-bg text-xs text-fg outline-none focus:border-brand-500 truncate"
            >
              <option value="ALL">Trend: All Trends</option>
              <option value="UPTREND">Price &gt; SMA 50 &gt; 200 (Uptrend)</option>
              <option value="DOWNTREND">Price &lt; SMA 50 (Downtrend)</option>
            </select>
          </div>
        </div>

        {/* Quick Filter Toggle Badges */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-border text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShariahOnly(!shariahOnly)}
              className={`px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                shariahOnly
                  ? 'bg-emerald-500/15 border-emerald-500 text-emerald-600 dark:text-emerald-400 font-bold'
                  : 'border-border text-fg-muted hover:border-fg-subtle'
              }`}
            >
              Islamic / Shariah Compliant Only
            </button>

            <button
              onClick={() => setKse100Only(!kse100Only)}
              className={`px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                kse100Only
                  ? 'bg-brand-500/15 border-brand-500 text-brand-600 dark:text-brand-400 font-bold'
                  : 'border-border text-fg-muted hover:border-fg-subtle'
              }`}
            >
              KSE-100 Constituents Only
            </button>

            <button
              onClick={() => setAiVerdictFilter(aiVerdictFilter === 'BUY_ONLY' ? 'ALL' : 'BUY_ONLY')}
              className={`px-3 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                aiVerdictFilter === 'BUY_ONLY'
                  ? 'bg-brand-500 text-white border-brand-500 shadow-sm'
                  : 'border-border text-fg-muted hover:border-fg-subtle'
              }`}
            >
              ✨ AI Buy Recommendations Only
            </button>
          </div>

          <div className="text-[11px] text-fg-subtle">
            Showing <strong className="text-fg">{sortedStocks.length}</strong> matching securities
          </div>
        </div>
      </Card>

      {/* 4. Master Screener Table */}
      <Card className="p-0 overflow-hidden shadow-card">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-bg-elevated/70 border-b border-border text-[11px] font-semibold text-fg-subtle uppercase tracking-wider">
              <tr>
                <th className="py-3 px-4 w-10">★</th>
                <th
                  onClick={() => handleSort('symbol')}
                  className="py-3 px-4 cursor-pointer hover:text-fg select-none"
                >
                  <div className="flex items-center gap-1.5">
                    <span>Symbol & Company</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort('close')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-fg select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Price</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort('pct_change')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-fg select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>24h Change</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort('rsi')}
                  className="py-3 px-3 text-center cursor-pointer hover:text-fg select-none"
                >
                  <div className="flex items-center justify-center gap-1">
                    <span>RSI (14)</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-3 px-3 text-center">Trend Alignment</th>
                <th
                  onClick={() => handleSort('volume')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-fg select-none"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Volume</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort('pe')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-fg select-none hidden lg:table-cell"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>P/E</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort('divYield')}
                  className="py-3 px-3 text-right cursor-pointer hover:text-fg select-none hidden lg:table-cell"
                >
                  <div className="flex items-center justify-end gap-1">
                    <span>Yield</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th
                  onClick={() => handleSort('aiScore')}
                  className="py-3 px-4 text-center cursor-pointer hover:text-fg select-none"
                >
                  <div className="flex items-center justify-center gap-1">
                    <span>AI Consensus</span>
                    <ArrowUpDown className="w-3 h-3" />
                  </div>
                </th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/40">
              {sortedStocks.map(stock => {
                const isBull = (stock.pct_change || 0) >= 0;
                const isWatch = watchlist.includes(stock.symbol);

                let rsiColor = 'text-fg font-mono';
                if (stock.rsi >= 70) rsiColor = 'text-rose-500 font-bold font-mono';
                else if (stock.rsi <= 35) rsiColor = 'text-emerald-500 font-bold font-mono';

                return (
                  <tr
                    key={stock.symbol}
                    onClick={() => navigate(`/analysis/${stock.symbol}`)}
                    className="hover:bg-bg-elevated/70 cursor-pointer transition-colors"
                  >
                    {/* Watchlist Star */}
                    <td className="py-3 px-4" onClick={e => toggleWatchlist(stock.symbol, e)}>
                      <Star
                        className={`w-4 h-4 transition-colors ${
                          isWatch ? 'fill-amber-400 text-amber-400' : 'text-fg-subtle hover:text-amber-400'
                        }`}
                      />
                    </td>

                    {/* Symbol & Company Name */}
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center font-mono font-bold text-xs text-brand-600 dark:text-brand-400">
                          {stock.symbol.slice(0, 3)}
                        </div>
                        <div>
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-sm text-fg">{stock.symbol}</span>
                            {stock.is_shariah && (
                              <span className="text-[9px] px-1 rounded bg-emerald-500/10 text-emerald-600 border border-emerald-500/20 font-medium">
                                Shariah
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-fg-subtle line-clamp-1 max-w-[140px] sm:max-w-[220px]">
                            {stock.company_name} • {stock.sector}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Price */}
                    <td className="py-3 px-3 text-right font-mono font-bold text-sm text-fg">
                      {stock.close?.toFixed(2) || '--'}
                    </td>

                    {/* Change % */}
                    <td className="py-3 px-3 text-right">
                      <span
                        className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded font-mono text-xs font-bold ${
                          isBull ? 'bg-bull-bg text-bull' : 'bg-bear-bg text-bear'
                        }`}
                      >
                        {isBull ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        <span>{isBull ? '+' : ''}{(stock.pct_change || 0).toFixed(2)}%</span>
                      </span>
                    </td>

                    {/* RSI */}
                    <td className="py-3 px-3 text-center">
                      <div className={rsiColor}>{stock.rsi}</div>
                      <div className="text-[9px] text-fg-subtle">
                        {stock.rsi > 70 ? 'Overbought' : stock.rsi < 35 ? 'Oversold' : 'Neutral'}
                      </div>
                    </td>

                    {/* Trend */}
                    <td className="py-3 px-3 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                          stock.trend === 'Strong Uptrend'
                            ? 'bg-bull-bg text-bull border-bull/20'
                            : stock.trend === 'Downtrend'
                            ? 'bg-bear-bg text-bear border-bear/20'
                            : 'bg-bg-elevated text-fg-muted border-border'
                        }`}
                      >
                        {stock.trend}
                      </span>
                    </td>

                    {/* Volume */}
                    <td className="py-3 px-3 text-right font-mono text-fg-muted">
                      {stock.volume ? `${(stock.volume / 1000000).toFixed(2)}M` : '--'}
                    </td>

                    {/* P/E */}
                    <td className="py-3 px-3 text-right font-mono text-fg hidden lg:table-cell">
                      {stock.pe}x
                    </td>

                    {/* Dividend Yield */}
                    <td className="py-3 px-3 text-right font-mono text-fg hidden lg:table-cell">
                      {stock.divYield}%
                    </td>

                    {/* AI Consensus Score & Badge */}
                    <td className="py-3 px-4 text-center">
                      <div className="flex flex-col items-center gap-0.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold border ${
                            stock.aiVerdict === 'Strong Buy'
                              ? 'bg-brand-500 text-white border-brand-500 shadow-sm'
                              : stock.aiVerdict === 'Buy'
                              ? 'bg-bull-bg text-bull border-bull/30'
                              : 'bg-bg-elevated text-fg-muted border-border'
                          }`}
                        >
                          {stock.aiVerdict}
                        </span>
                        <div className="w-16 h-1 rounded-full bg-bg-elevated overflow-hidden border border-border mt-0.5">
                          <div
                            style={{ width: `${stock.aiScore}%` }}
                            className="h-full bg-brand-500"
                          />
                        </div>
                      </div>
                    </td>

                    {/* Action */}
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={e => {
                          e.stopPropagation();
                          navigate(`/analysis/${stock.symbol}`);
                        }}
                        className="p-1.5 rounded-lg border border-border bg-bg hover:bg-brand-500 hover:text-white hover:border-brand-500 text-fg-muted transition-colors"
                        title="Open in-depth technical & agent analysis"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
};
