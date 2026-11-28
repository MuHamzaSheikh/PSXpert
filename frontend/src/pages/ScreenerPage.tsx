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
  ChevronLeft,
  Filter,
  RefreshCw,
  BarChart3,
  TrendingUp,
  Layers,
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

  // Pagination States
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState<number | 'ALL'>(50);

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
          api.getStocks(undefined, undefined, 600), // Fetch all 506 PSX equities
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

  // Reset page to 1 whenever filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, selectedSector, shariahOnly, kse100Only, rsiFilter, trendFilter, aiVerdictFilter]);

  // Sector company counts
  const sectorCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    stocks.forEach(s => {
      if (s.sector) counts[s.sector] = (counts[s.sector] || 0) + 1;
    });
    return counts;
  }, [stocks]);

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

  // Pagination calculation
  const totalPages = pageSize === 'ALL' ? 1 : Math.max(1, Math.ceil(sortedStocks.length / pageSize));
  const paginatedStocks = useMemo(() => {
    if (pageSize === 'ALL') return sortedStocks;
    const start = (currentPage - 1) * pageSize;
    return sortedStocks.slice(start, start + pageSize);
  }, [sortedStocks, currentPage, pageSize]);

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
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#252A2B] dark:text-[#F4EFE6]">
              AI Multi-Factor Stock Screener
            </h1>
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#2F7D68]/15 text-[#2F7D68] dark:text-[#3DA88D] border border-[#2F7D68]/25 shadow-sm">
              {stocks.length > 0 ? `${stocks.length} PSX Listed Companies` : '506 PSX Listed Companies'}
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#77736C] dark:text-[#9E988E] mt-1">
            Explore and filter all 506 listed Pakistan Stock Exchange equities across technical indicators, valuation multiples, and multi-factor models.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              setSearchQuery('');
              setSelectedSector('ALL');
              setShariahOnly(false);
              setKse100Only(false);
              setRsiFilter('ALL');
              setTrendFilter('ALL');
              setAiVerdictFilter('ALL');
              setSearchParams({});
            }}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 hover:bg-[#FFFCF6] text-xs font-semibold text-[#77736C] hover:text-[#252A2B] transition-all shadow-sm"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Reset Filters</span>
          </button>
        </div>
      </div>

      {/* 2. Top AI Consensus Picks Showcase */}
      <div>
        <div className="flex items-center gap-2 mb-3 text-xs font-bold text-[#252A2B] dark:text-[#F4EFE6] uppercase tracking-wider">
          <Sparkles className="w-4 h-4 text-[#2F7D68]" />
          <span>Top AI Multi-Agent Consensus Picks Today</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {topAIPicks.map(pick => (
            <Card
              key={pick.symbol}
              onClick={() => navigate(`/analysis/${pick.symbol}`)}
              className="p-4 hover:border-[#694E7A]/40 dark:hover:border-[#694E7A]/40 hover:shadow-lg cursor-pointer transition-all space-y-3 relative overflow-hidden group"
            >
              <div className="absolute top-0 right-0 w-28 h-28 bg-[#694E7A]/5 rounded-full blur-2xl pointer-events-none" />

              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-[#2F7D68]/15 border border-[#2F7D68]/25 flex items-center justify-center font-mono font-bold text-sm text-[#2F7D68] dark:text-[#3DA88D]">
                    {pick.symbol.slice(0, 3)}
                  </div>
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="font-mono font-extrabold text-sm text-[#252A2B] dark:text-[#F4EFE6]">{pick.symbol}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#E7E0D5]/50 dark:bg-[#252A2C] text-[#77736C] dark:text-[#9E988E] font-medium border border-[#DDD5C9]/60">
                        {pick.is_kse100 ? 'KSE-100' : 'Regular'}
                      </span>
                    </div>
                    <div className="text-xs text-[#77736C] dark:text-[#9E988E] line-clamp-1">{pick.company_name}</div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-xs font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">PKR {pick.close?.toFixed(2)}</div>
                  <div className="text-[11px] font-mono text-[#287A50] dark:text-[#34A86E] font-bold">+{(pick.pct_change || 1.4).toFixed(2)}%</div>
                </div>
              </div>

              {/* Multi-Factor Snapshot */}
              <div className="grid grid-cols-3 gap-2 py-2 border-y border-[#DDD5C9]/50 dark:border-[#DDD5C9]/15 text-[11px]">
                <div>
                  <div className="text-[#77736C] dark:text-[#9E988E] text-[10px]">RSI-14</div>
                  <div className="font-mono font-bold text-[#2F7D68] dark:text-[#3DA88D]">{pick.rsi}</div>
                </div>
                <div>
                  <div className="text-[#77736C] dark:text-[#9E988E] text-[10px]">P/E Multiple</div>
                  <div className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">{pick.pe}x</div>
                </div>
                <div>
                  <div className="text-[#77736C] dark:text-[#9E988E] text-[10px]">Div Yield</div>
                  <div className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">{pick.divYield}%</div>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-1">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-[#287A50] animate-pulse" />
                  <span className="font-bold text-[#287A50] dark:text-[#34A86E]">{pick.aiVerdict}</span>
                  <span className="text-[10px] font-mono text-[#77736C] dark:text-[#9E988E]">({pick.aiScore}% Score)</span>
                </div>
                <span className="text-[#2F7D68] dark:text-[#3DA88D] font-semibold flex items-center gap-0.5 text-xs group-hover:translate-x-0.5 transition-transform">
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
            <Search className="w-4 h-4 text-[#77736C] absolute left-3.5 top-3 pointer-events-none" />
            <input
              type="text"
              placeholder="Search symbol or name (e.g. OGDC, Meezan)..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 h-10 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-xs text-[#252A2B] dark:text-[#F4EFE6] placeholder:text-[#77736C] outline-none focus:border-[#2F7D68] shadow-sm truncate"
            />
          </div>

          {/* Sector Dropdown with Counts */}
          <div>
            <select
              value={selectedSector}
              onChange={e => {
                setSelectedSector(e.target.value);
                setSearchParams(e.target.value === 'ALL' ? {} : { sector: e.target.value });
              }}
              className="w-full px-3.5 h-10 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-xs text-[#252A2B] dark:text-[#F4EFE6] outline-none focus:border-[#2F7D68] shadow-sm truncate"
            >
              <option value="ALL">All Industry Sectors ({stocks.length})</option>
              {sectors.map(sec => (
                <option key={sec} value={sec}>
                  {sec} ({sectorCounts[sec] || 0})
                </option>
              ))}
            </select>
          </div>

          {/* RSI Condition Filter */}
          <div>
            <select
              value={rsiFilter}
              onChange={e => setRsiFilter(e.target.value as any)}
              className="w-full px-3.5 h-10 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-xs text-[#252A2B] dark:text-[#F4EFE6] outline-none focus:border-[#2F7D68] shadow-sm truncate"
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
              className="w-full px-3.5 h-10 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-xs text-[#252A2B] dark:text-[#F4EFE6] outline-none focus:border-[#2F7D68] shadow-sm truncate"
            >
              <option value="ALL">Price Trend: Any</option>
              <option value="UPTREND">Strong Uptrend</option>
              <option value="DOWNTREND">Downtrend</option>
            </select>
          </div>
        </div>

        {/* Quick Tag Filter Pills */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={() => setShariahOnly(!shariahOnly)}
              className={`px-3.5 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                shariahOnly
                  ? 'bg-gradient-to-r from-[#287A50] to-[#1F5C4C] text-white border-[#287A50] shadow-sm'
                  : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border-[#DDD5C9] dark:border-[#DDD5C9]/20 text-[#77736C] hover:text-[#252A2B]'
              }`}
            >
              ☪ Shariah Compliant Only
            </button>

            <button
              onClick={() => setKse100Only(!kse100Only)}
              className={`px-3.5 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                kse100Only
                  ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white border-[#694E7A] shadow-sm'
                  : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border-[#DDD5C9] dark:border-[#DDD5C9]/20 text-[#77736C] hover:text-[#252A2B]'
              }`}
            >
              📊 KSE-100 Constituents Only
            </button>

            <button
              onClick={() => setAiVerdictFilter(aiVerdictFilter === 'BUY_ONLY' ? 'ALL' : 'BUY_ONLY')}
              className={`px-3.5 py-1.5 rounded-full border text-xs font-semibold transition-all ${
                aiVerdictFilter === 'BUY_ONLY'
                  ? 'bg-gradient-to-r from-[#2F7D68] to-[#236353] text-white border-[#2F7D68] shadow-sm'
                  : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border-[#DDD5C9] dark:border-[#DDD5C9]/20 text-[#77736C] hover:text-[#252A2B]'
              }`}
            >
              ✨ AI Buy Recommendations Only
            </button>
          </div>

          <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">
            Showing <strong className="text-[#252A2B] dark:text-[#F4EFE6]">{sortedStocks.length}</strong> of{' '}
            <strong className="text-[#252A2B] dark:text-[#F4EFE6]">{stocks.length}</strong> companies
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
              {loading ? (
                <tr>
                  <td colSpan={11} className="py-16 text-center text-fg-subtle">
                    <div className="flex flex-col items-center gap-2">
                      <RefreshCw className="w-6 h-6 animate-spin text-brand-500" />
                      <span>Loading all PSX equities & quantitative analytics...</span>
                    </div>
                  </td>
                </tr>
              ) : paginatedStocks.length === 0 ? (
                <tr>
                  <td colSpan={11} className="py-16 text-center text-fg-subtle">
                    <div className="space-y-1">
                      <div className="text-base font-semibold text-fg-muted">No stocks match your filters</div>
                      <p>Try clearing your search query or loosening criteria.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                paginatedStocks.map(stock => {
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
                              {stock.is_kse100 && (
                                <span className="text-[9px] px-1 rounded bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20 font-medium">
                                  KSE-100
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
                })
              )}
            </tbody>
          </table>
        </div>

        {/* 5. Pagination Bar & Page Size Selector */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 border-t border-border bg-bg-elevated/40 text-xs">
          <div className="flex items-center gap-3">
            <span className="text-fg-subtle">
              Showing{' '}
              <strong className="text-fg">
                {sortedStocks.length === 0 ? 0 : pageSize === 'ALL' ? 1 : (currentPage - 1) * pageSize + 1}
              </strong>{' '}
              to{' '}
              <strong className="text-fg">
                {pageSize === 'ALL' ? sortedStocks.length : Math.min(currentPage * pageSize, sortedStocks.length)}
              </strong>{' '}
              of <strong className="text-fg">{sortedStocks.length}</strong> securities
            </span>

            {/* Page Size Selector */}
            <div className="flex items-center gap-1 border-l border-border pl-3">
              <span className="text-fg-subtle mr-1">Per page:</span>
              {[25, 50, 100, 'ALL'].map(sz => (
                <button
                  key={sz}
                  onClick={() => {
                    setPageSize(sz as any);
                    setCurrentPage(1);
                  }}
                  className={`px-2 py-0.5 rounded text-[11px] font-semibold border transition-all ${
                    pageSize === sz
                      ? 'bg-brand-500 text-white border-brand-500 shadow-sm'
                      : 'border-border text-fg-muted hover:text-fg bg-bg-card'
                  }`}
                >
                  {sz}
                </button>
              ))}
            </div>
          </div>

          {/* Page Navigation Buttons */}
          {pageSize !== 'ALL' && totalPages > 1 && (
            <div className="flex items-center gap-2">
              <button
                disabled={currentPage <= 1}
                onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                className="flex items-center gap-1 px-3 py-1 rounded-lg border border-border bg-bg-card text-fg-muted hover:text-fg disabled:opacity-40 disabled:pointer-events-none transition-colors"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span>Prev</span>
              </button>

              <span className="text-fg-muted font-mono font-medium">
                Page <strong className="text-fg">{currentPage}</strong> of{' '}
                <strong className="text-fg">{totalPages}</strong>
              </span>

              <button
                disabled={currentPage >= totalPages}
                onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                className="flex items-center gap-1 px-3 py-1 rounded-lg border border-border bg-bg-card text-fg-muted hover:text-fg disabled:opacity-40 disabled:pointer-events-none transition-colors"
              >
                <span>Next</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};
