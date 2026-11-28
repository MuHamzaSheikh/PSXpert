import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { TradingViewChart } from '@/components/charts/TradingViewChart';
import { FearGreedGauge } from '@/components/charts/FearGreedGauge';
import { MarketBreadthBar } from '@/components/charts/MarketBreadthBar';
import { MarketMoversTable } from '@/components/dashboard/MarketMoversTable';
import { CommoditiesForexCard } from '@/components/dashboard/CommoditiesForexCard';
import { AnnouncementsCard } from '@/components/dashboard/AnnouncementsCard';
import { NewsSentimentCard } from '@/components/dashboard/NewsSentimentCard';
import { api } from '@/api/client';
import { MarketSummary, Company, OHLCVResponse, NewsArticle } from '@/types';
import { MOCK_INDICES } from '@/api/mockData';
import {
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  SlidersHorizontal,
  Briefcase,
  Bot,
  Sparkles,
  RefreshCw,
  Calendar,
  Layers,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();

  const [summary, setSummary] = useState<MarketSummary | null>(null);
  const [stocks, setStocks] = useState<Company[]>([]);
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isMockData, setIsMockData] = useState(false);

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      try {
        const [sumRes, stockRes, ohlcvRes, newsRes] = await Promise.all([
          api.getMarketSummary(),
          api.getStocks(undefined, undefined, 600),
          api.getOHLCV('KSE100', 180),
          api.getLatestSentiment('ALL', 'ALL', 10),
        ]);

        setSummary(sumRes.data);
        setStocks(stockRes.data);
        setOhlcv(ohlcvRes.data);
        setNews(newsRes.data);
        setIsMockData(sumRes.isMock);
      } catch (err) {
        console.error('Error loading dashboard data:', err);
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, []);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await api.refreshNews();
    const [sumRes, stockRes, newsRes] = await Promise.all([
      api.getMarketSummary(),
      api.getStocks(),
      api.getLatestSentiment(),
    ]);
    setSummary(sumRes.data);
    setStocks(stockRes.data);
    setNews(newsRes.data);
    setIsRefreshing(false);
  };

  const kseClose = summary?.close || 176294.33;
  const kseChange = summary?.point_change || -1203.41;
  const ksePct = summary?.pct_change || -0.68;
  const isKseUp = kseChange >= 0;

  // Day Range calculation
  const dayLow = summary?.low || 176053.64;
  const dayHigh = summary?.high || 177719.05;
  const dayProgress = Math.min(100, Math.max(0, ((kseClose - dayLow) / (dayHigh - dayLow || 1)) * 100));

  // 52-Week Range calculation
  const low52 = summary?.low_52w || 144119.44;
  const high52 = summary?.high_52w || 191022.73;
  const range52Progress = Math.min(100, Math.max(0, ((kseClose - low52) / (high52 - low52 || 1)) * 100));

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      
      {/* 1. Header Title & Quick Action Strip */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#252A2B] dark:text-[#F4EFE6]">
              Pakistan Stock Exchange (PSX) Today
            </h1>
            {isMockData && <DemoBadge label="Demo Feed" />}
          </div>
          <p className="text-xs sm:text-sm text-[#77736C] dark:text-[#9E988E] mt-1">
            Live KSE-100 index performance, market breadth, corporate disclosures, and FinBERT AI sentiment.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-full text-xs font-semibold border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 hover:bg-[#FFFCF6] text-[#77736C] hover:text-[#252A2B] transition-all shadow-sm"
            title="Refresh latest prices and news"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-[#2F7D68]' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => navigate('/screener')}
            className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-semibold text-white bg-gradient-to-r from-[#2F7D68] to-[#236353] hover:from-[#236353] hover:to-[#1a4d40] shadow-md shadow-[#2F7D68]/20 transition-all"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Open Screener</span>
          </button>
        </div>
      </div>

      {/* 2. Top 6 Major Market Indices in Frosted Glass Cards with Sparklines */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {MOCK_INDICES.map(idx => {
          const isUp = idx.pct >= 0;
          return (
            <Card
              key={idx.symbol}
              onClick={() => navigate('/analysis/KSE100')}
              className="p-3.5 cursor-pointer hover:border-[#694E7A]/40 dark:hover:border-[#694E7A]/40 hover:shadow-lg transition-all duration-200 flex flex-col justify-between space-y-2 h-full group"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-xs text-[#252A2B] dark:text-[#F4EFE6] tracking-tight">
                  {idx.symbol}
                </span>
                <span
                  className={`inline-flex items-center gap-0.5 text-[10px] font-mono font-bold px-2 py-0.5 rounded-full ${
                    isUp 
                      ? 'text-[#287A50] bg-[#287A50]/12 border border-[#287A50]/25' 
                      : 'text-[#C64C4C] bg-[#C64C4C]/12 border border-[#C64C4C]/25'
                  }`}
                >
                  {isUp ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />}
                  <span>{isUp ? '+' : ''}{idx.pct.toFixed(2)}%</span>
                </span>
              </div>

              {/* Price and SVG Sparkline */}
              <div className="flex items-center justify-between gap-1">
                <div className="text-sm sm:text-base font-mono font-extrabold text-[#252A2B] dark:text-[#F4EFE6] tracking-tight">
                  {idx.current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </div>

                {/* Delicate Sparkline SVG */}
                <div className="w-12 h-5 flex-shrink-0">
                  <svg className="w-full h-full overflow-visible" viewBox="0 0 50 20">
                    <path
                      d={isUp 
                        ? "M 0 16 Q 12 14, 20 8 T 35 10 T 50 3" 
                        : "M 0 4 Q 12 6, 20 12 T 35 9 T 50 17"
                      }
                      fill="none"
                      stroke={isUp ? "#287A50" : "#C64C4C"}
                      strokeWidth="1.8"
                      strokeLinecap="round"
                    />
                  </svg>
                </div>
              </div>

              <div className="flex items-center justify-between text-[10px] font-mono pt-0.5 border-t border-[#DDD5C9]/40 dark:border-[#DDD5C9]/10">
                <span className={`font-semibold ${isUp ? 'text-[#287A50]' : 'text-[#C64C4C]'}`}>
                  {isUp ? '▲ +' : '▼ '}{idx.change.toFixed(2)}
                </span>
                <span className="text-[#77736C] dark:text-[#9E988E]">
                  Vol: {idx.volume}
                </span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 3. Hero Section: KSE-100 Chart & Key Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        
        {/* Left: KSE-100 Benchmark Index Interactive Glass Card */}
        <Card className="lg:col-span-8 p-0 flex flex-col justify-between overflow-hidden">
          
          {/* Elegant Top Fluid Wave Ribbon Header */}
          <div className="px-5 pt-4 pb-3 bg-gradient-to-r from-[#2F7D68]/15 via-[#694E7A]/10 to-transparent border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5">
                {/* Circular Indicator Icon */}
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#2F7D68] to-[#1F5C4C] flex items-center justify-center text-white text-xs font-bold shadow-sm">
                  <span>.ii</span>
                </div>
                <div className="flex items-center gap-2">
                  <h2 className="font-bold text-base text-[#252A2B] dark:text-[#F4EFE6]">
                    KSE-100 Benchmark Index
                  </h2>
                  <span className="bg-[#694E7A]/15 text-[#694E7A] dark:text-[#A888BF] text-[10px] font-bold px-2.5 py-0.5 rounded-full border border-[#694E7A]/25">
                    Primary Market Indicator
                  </span>
                </div>
              </div>

              <div className="text-right text-xs text-[#77736C] dark:text-[#9E988E] flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>Session: {summary?.trading_date || '2026-11-18'}</span>
                </div>
                <span>•</span>
                <span className="text-[#287A50] dark:text-[#34A86E] font-semibold">
                  DPS Official Feeds
                </span>
              </div>
            </div>

            {/* Price & Change Pill */}
            <div className="flex items-baseline gap-3 mt-2">
              <span className="text-2xl sm:text-3xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6] tracking-tight">
                {kseClose.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span
                className={`inline-flex items-center gap-1 font-mono text-xs font-bold px-3 py-1 rounded-full ${
                  isKseUp 
                    ? 'bg-[#287A50]/15 text-[#287A50] border border-[#287A50]/30' 
                    : 'bg-[#C64C4C]/15 text-[#C64C4C] border border-[#C64C4C]/30'
                }`}
              >
                {isKseUp ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />}
                <span>{isKseUp ? '+' : ''}{kseChange.toFixed(2)} ({isKseUp ? '+' : ''}{ksePct.toFixed(2)}%)</span>
              </span>
            </div>
          </div>

          {/* Interactive Lightweight TradingView Chart */}
          <div className="p-4 flex-1 min-h-[410px] w-full">
            {ohlcv ? (
              <TradingViewChart
                candles={ohlcv.candles}
                patterns={ohlcv.patterns}
                symbol="KSE100"
                height={410}
                showVolume
                showEMAs
              />
            ) : (
              <div className="h-full flex items-center justify-center text-[#77736C]">
                Loading KSE-100 candlestick telemetry...
              </div>
            )}
          </div>
        </Card>

        {/* Right: KSE-100 Index Stats Sidebar */}
        <Card className="lg:col-span-4 p-5 flex flex-col justify-between space-y-4 relative overflow-hidden">
          
          {/* Subtle Upward Arrow Background Watermark */}
          <div className="absolute top-3 right-3 text-[#2F7D68]/10 pointer-events-none">
            <ArrowUpRight className="w-20 h-20 stroke-[1.2]" />
          </div>

          {/* Header */}
          <div className="flex items-center gap-3 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#2F7D68] to-[#1F5C4C] flex items-center justify-center text-white shadow-sm flex-shrink-0">
              <span className="font-bold text-sm">.ii</span>
            </div>
            <div>
              <h3 className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">
                KSE-100 Index Stats
              </h3>
              <div className="text-xs text-[#77736C] dark:text-[#9E988E]">
                Summary of trading session metrics
              </div>
            </div>
          </div>

          {/* Key Metrics List */}
          <div className="space-y-3.5 text-xs">
            <div className="flex items-center justify-between py-1.5 border-b border-[#DDD5C9]/40 dark:border-[#DDD5C9]/10">
              <span className="text-[#77736C] dark:text-[#9E988E]">Trading Volume</span>
              <span className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                173.65 Million shares
              </span>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-[#DDD5C9]/40 dark:border-[#DDD5C9]/10">
              <span className="text-[#77736C] dark:text-[#9E988E]">Traded Value</span>
              <span className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                PKR 13.77 Billion
              </span>
            </div>

            <div className="flex items-center justify-between py-1.5 border-b border-[#DDD5C9]/40 dark:border-[#DDD5C9]/10">
              <span className="text-[#77736C] dark:text-[#9E988E]">Previous Close</span>
              <span className="font-mono font-bold text-[#252A2B] dark:text-[#F4EFE6]">
                {(kseClose - kseChange).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Day Range Progress Bar */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs text-[#77736C] dark:text-[#9E988E]">
                <span className="font-medium text-[#252A2B] dark:text-[#F4EFE6]">Day Range</span>
              </div>
              <div className="w-full h-2 rounded-full bg-[#E7E0D5]/70 dark:bg-[#252A2C] overflow-hidden border border-[#DDD5C9]/50 relative">
                <div
                  style={{ width: `${dayProgress}%` }}
                  className="h-full bg-gradient-to-r from-[#2F7D68] to-[#3DA88D] rounded-full transition-all duration-300"
                />
              </div>
              <div className="flex items-center justify-between text-[11px] font-mono text-[#77736C] dark:text-[#9E988E]">
                <span>Low: {dayLow.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                <span>High: {dayHigh.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
              </div>
            </div>

            {/* 52-Week Range Progress Bar */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs text-[#77736C] dark:text-[#9E988E]">
                <span className="font-medium text-[#252A2B] dark:text-[#F4EFE6]">52-Week Range</span>
              </div>
              <div className="w-full h-2 rounded-full bg-[#E7E0D5]/70 dark:bg-[#252A2C] overflow-hidden border border-[#DDD5C9]/50 relative">
                <div
                  style={{ width: `${range52Progress}%` }}
                  className="h-full bg-gradient-to-r from-[#694E7A] to-[#8E6DA3] rounded-full transition-all duration-300"
                />
              </div>
              <div className="flex items-center justify-between text-[11px] font-mono text-[#77736C] dark:text-[#9E988E]">
                <span>52W Low: {low52.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                <span>52W High: {high52.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
              </div>
            </div>
          </div>

          {/* Bottom Wave Ribbon Decoration */}
          <div className="h-6 w-full rounded-xl bg-gradient-to-r from-[#2F7D68]/10 via-[#694E7A]/10 to-[#C47C4F]/10 border border-[#DDD5C9]/40 dark:border-[#DDD5C9]/10" />
        </Card>
      </div>

      {/* 4. Secondary Sections: Sentiment, Movers, Announcements, Forex */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left: News Sentiment & FinBERT Impact */}
        <div className="lg:col-span-6">
          <NewsSentimentCard news={news} />
        </div>

        {/* Right: Market Movers Table (Gainers, Losers, Volume Leaders) */}
        <div className="lg:col-span-6">
          <MarketMoversTable stocks={stocks} />
        </div>
      </div>

      {/* 5. Tertiary Row: Announcements, Commodities, Market Breadth */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        <AnnouncementsCard />
        <CommoditiesForexCard />
        <Card className="p-5 flex flex-col justify-between space-y-4">
          <MarketBreadthBar />
          <FearGreedGauge score={62} />
        </Card>
      </div>
    </div>
  );
};
