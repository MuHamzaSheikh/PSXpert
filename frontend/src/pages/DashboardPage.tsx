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
          api.getStocks(undefined, undefined, 100),
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
  const kseChange = summary?.point_change || -1223.41;
  const ksePct = summary?.pct_change || -0.69;
  const isKseUp = kseChange >= 0;

  // Day Range percentage
  const dayLow = summary?.low || 176053.64;
  const dayHigh = summary?.high || 177719.05;
  const dayProgress = Math.min(100, Math.max(0, ((kseClose - dayLow) / (dayHigh - dayLow || 1)) * 100));

  // 52-Week Range percentage
  const low52 = summary?.low_52w || 144119.44;
  const high52 = summary?.high_52w || 191022.73;
  const range52Progress = Math.min(100, Math.max(0, ((kseClose - low52) / (high52 - low52 || 1)) * 100));

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 1. Header Title & Quick Action Strip */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-fg">
              Pakistan Stock Exchange (PSX) Today
            </h1>
            {isMockData && <DemoBadge label="Demo Feed" />}
          </div>
          <p className="text-xs sm:text-sm text-fg-muted mt-1">
            Live KSE-100 index performance, market breadth, corporate disclosures, and FinBERT AI sentiment.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start md:self-auto">
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold border border-border bg-bg-card hover:bg-bg-elevated text-fg-muted hover:text-fg transition-all"
            title="Refresh latest prices and news"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-brand-600' : ''}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => navigate('/screener')}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600 shadow-sm transition-all"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span>Open Screener</span>
          </button>
        </div>
      </div>

      {/* 2. Top Indices Performance Row */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {MOCK_INDICES.map(idx => {
          const isUp = idx.pct >= 0;
          return (
            <Card
              key={idx.symbol}
              onClick={() => navigate('/analysis/KSE100')}
              className="p-3.5 cursor-pointer hover:border-brand-500/50 hover:shadow-card transition-all flex flex-col justify-between space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-xs text-fg">{idx.symbol}</span>
                <span
                  className={`inline-flex items-center text-[11px] font-mono font-bold px-1.5 py-0.2 rounded ${
                    isUp ? 'text-bull bg-bull-bg' : 'text-bear bg-bear-bg'
                  }`}
                >
                  {isUp ? '+' : ''}{idx.pct.toFixed(2)}%
                </span>
              </div>

              <div className="text-base sm:text-lg font-mono font-extrabold text-fg tracking-tight">
                {idx.current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>

              <div className="flex items-center justify-between text-[10px] text-fg-subtle font-mono">
                <span className={isUp ? 'text-bull' : 'text-bear'}>
                  {isUp ? '+' : ''}{idx.change.toFixed(2)}
                </span>
                <span>Vol: {idx.volume}</span>
              </div>
            </Card>
          );
        })}
      </div>

      {/* 3. Hero Section: KSE-100 Chart & Comprehensive Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Left: Interactive TradingView Chart */}
        <Card className="lg:col-span-8 p-5 flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base text-fg">KSE-100 Benchmark Index</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  Primary Market Indicator
                </span>
              </div>
              <div className="flex items-baseline gap-2.5 mt-1">
                <span className="text-2xl sm:text-3xl font-extrabold font-mono text-fg tracking-tight">
                  {kseClose.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <span
                  className={`inline-flex items-center gap-1 font-mono text-sm font-bold px-2 py-0.5 rounded-lg ${
                    isKseUp ? 'bg-bull-bg text-bull' : 'bg-bear-bg text-bear'
                  }`}
                >
                  {isKseUp ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                  <span>{isKseUp ? '+' : ''}{kseChange.toFixed(2)} ({isKseUp ? '+' : ''}{ksePct.toFixed(2)}%)</span>
                </span>
              </div>
            </div>

            <div className="text-right text-xs text-fg-subtle">
              <div>Session: {summary?.trading_date || '2026-11-18'}</div>
              <div className="font-mono text-fg-muted">DPS Official Feeds</div>
            </div>
          </div>

          {/* Canvas Chart */}
          <div className="flex-1 min-h-[380px] w-full mt-2">
            {ohlcv ? (
              <TradingViewChart
                candles={ohlcv.candles}
                symbol="KSE100"
                height={380}
                showVolume
                showEMAs
              />
            ) : (
              <div className="h-full flex items-center justify-center text-fg-subtle">
                Loading KSE-100 candlestick telemetry...
              </div>
            )}
          </div>
        </Card>

        {/* Right: Index Key Statistics Sidebar */}
        <Card className="lg:col-span-4 p-5 flex flex-col justify-between space-y-4">
          <div className="border-b border-border pb-3">
            <span className="font-semibold text-sm text-fg">KSE-100 Index Stats</span>
            <div className="text-xs text-fg-subtle mt-0.5">Summary of trading session metrics</div>
          </div>

          <div className="space-y-3.5 text-xs">
            <div className="flex items-center justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Trading Volume</span>
              <span className="font-mono font-bold text-fg">173.65 Million shares</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Traded Value</span>
              <span className="font-mono font-bold text-fg">PKR 13.77 Billion</span>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Previous Close</span>
              <span className="font-mono font-bold text-fg">
                {(kseClose - kseChange).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            {/* Day Range Slider */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs text-fg-muted">
                <span>Day Range</span>
                <span className="font-mono text-[11px]">
                  {dayLow.toLocaleString()} - {dayHigh.toLocaleString()}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-bg-elevated overflow-hidden border border-border relative">
                <div
                  style={{ width: `${dayProgress}%` }}
                  className="h-full bg-brand-500 rounded-full transition-all duration-300"
                />
              </div>
              <div className="flex items-center justify-between text-[10px] text-fg-subtle font-mono">
                <span>Low: {dayLow.toLocaleString()}</span>
                <span>High: {dayHigh.toLocaleString()}</span>
              </div>
            </div>

            {/* 52-Week Range Slider */}
            <div className="space-y-1.5 pt-1">
              <div className="flex items-center justify-between text-xs text-fg-muted">
                <span>52-Week Range</span>
                <span className="font-mono text-[11px]">
                  {low52.toLocaleString()} - {high52.toLocaleString()}
                </span>
              </div>
              <div className="w-full h-2 rounded-full bg-bg-elevated overflow-hidden border border-border relative">
                <div
                  style={{ width: `${range52Progress}%` }}
                  className="h-full bg-brand-500 rounded-full transition-all duration-300"
                />
              </div>
              <div className="flex items-center justify-between text-[10px] text-fg-subtle font-mono">
                <span>52W Low: {low52.toLocaleString()}</span>
                <span>52W High: {high52.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Quick CTA to Analysis */}
          <div className="pt-3 border-t border-border">
            <button
              onClick={() => navigate('/analysis/KSE100')}
              className="w-full py-2.5 px-3 rounded-xl border border-brand-500/30 bg-brand-500/10 hover:bg-brand-500 hover:text-white text-brand-600 dark:text-brand-400 font-semibold text-xs transition-colors flex items-center justify-center gap-1.5"
            >
              <span>Explore Technical Indicators & HMM Regimes</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </Card>
      </div>

      {/* 4. Market Breadth & Sentiment (Fear & Greed) Dual Strip */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-6">
          <MarketBreadthBar
            advances={summary?.breadth?.advances || 178}
            declines={summary?.breadth?.declines || 285}
            unchanged={summary?.breadth?.unchanged || 38}
            total={summary?.breadth?.total || 501}
          />
        </div>
        <div className="lg:col-span-6">
          <FearGreedGauge score={49} />
        </div>
      </div>

      {/* 5. Market Movers Table */}
      <div>
        <MarketMoversTable stocks={stocks} />
      </div>

      {/* 6. Corporate Announcements & Filings */}
      <div>
        <AnnouncementsCard />
      </div>

      {/* 7. Dual Grid: FinBERT News + Forex & Commodities */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-8">
          <NewsSentimentCard news={news} />
        </div>
        <div className="lg:col-span-4 space-y-5">
          <CommoditiesForexCard />

          {/* Quick AI Assistant Card Prompt */}
          <Card className="p-5 bg-gradient-to-br from-brand-900/30 via-bg-card to-bg-card border-brand-500/30 space-y-3">
            <div className="flex items-center gap-2 text-brand-600 dark:text-brand-400 font-bold text-sm">
              <Bot className="w-4 h-4" />
              <span>Ask PSXpert AI Assistant</span>
            </div>
            <p className="text-xs text-fg-muted leading-relaxed">
              Have questions about today&apos;s market movers, earnings filings, or sector regimes? Chat with our RAG research assistant.
            </p>
            <button
              onClick={() => navigate('/assistant')}
              className="w-full py-2 px-3 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Launch Research Assistant</span>
            </button>
          </Card>
        </div>
      </div>
    </div>
  );
};
