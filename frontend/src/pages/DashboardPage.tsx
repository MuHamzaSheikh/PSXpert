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
import { CandlestickPatternsList } from '@/components/analysis/CandlestickPatternsList';
import { api } from '@/api/client';
import { MarketSummary, Company, OHLCVResponse, NewsArticle, Pattern } from '@/types';
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
  Layers,
  Zap,
} from 'lucide-react';

const POPULAR_TICKERS = ['KSE100', 'MEBL', 'OGDC', 'PPL', 'HUBC', 'SYS', 'ENGRO', 'LUCK', 'FFC'];

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();

  const [selectedSymbol, setSelectedSymbol] = useState('KSE100');
  const [summary, setSummary] = useState<MarketSummary | null>(null);
  const [stocks, setStocks] = useState<Company[]>([]);
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [news, setNews] = useState<NewsArticle[]>([]);
  const [loading, setLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isMockData, setIsMockData] = useState(false);
  const [activeTab, setActiveTab] = useState<'patterns' | 'news' | 'announcements'>('patterns');

  // Load primary dashboard data
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

  // When selected symbol changes, fetch that symbol's OHLCV + patterns
  useEffect(() => {
    if (selectedSymbol === 'KSE100' && ohlcv?.symbol === 'KSE100') return;

    async function loadSymbolData() {
      setChartLoading(true);
      try {
        const res = await api.getOHLCV(selectedSymbol, 180);
        setOhlcv(res.data);
      } catch (err) {
        console.error(`Error loading data for ${selectedSymbol}:`, err);
      } finally {
        setChartLoading(false);
      }
    }

    loadSymbolData();
  }, [selectedSymbol]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await api.refreshNews();
    const [sumRes, stockRes, ohlcvRes, newsRes] = await Promise.all([
      api.getMarketSummary(),
      api.getStocks(),
      api.getOHLCV(selectedSymbol, 180),
      api.getLatestSentiment(),
    ]);
    setSummary(sumRes.data);
    setStocks(stockRes.data);
    setOhlcv(ohlcvRes.data);
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

  // Candlestick Pattern Statistics
  const patternsList = ohlcv?.patterns || [];
  const bullishCount = patternsList.filter(p => (p.type || '').toUpperCase() === 'BULLISH').length;
  const bearishCount = patternsList.filter(p => (p.type || '').toUpperCase() === 'BEARISH').length;
  const neutralCount = patternsList.filter(p => (p.type || '').toUpperCase() === 'NEUTRAL').length;

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
            Live KSE-100 index performance, Japanese candlestick pattern recognition, market breadth, and FinBERT AI sentiment.
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
              onClick={() => {
                setSelectedSymbol(idx.symbol === 'KSE100' ? 'KSE100' : 'MEBL');
                window.scrollTo({ top: 320, behavior: 'smooth' });
              }}
              className="p-3.5 cursor-pointer hover:border-brand-500/50 hover:shadow-card transition-all flex flex-col justify-between space-y-1.5 h-full"
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

      {/* 3. Hero Section: Chart with Candlestick Patterns & Key Statistics Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
        {/* Left: Interactive TradingView Chart with Pattern Overlays & Ticker Switcher */}
        <Card className="lg:col-span-8 p-5 flex flex-col justify-between">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-base text-fg">
                  {selectedSymbol === 'KSE100' ? 'KSE-100 Benchmark Index' : `${selectedSymbol} Candlestick Analysis`}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  {selectedSymbol === 'KSE100' ? 'Primary Index' : 'Stock Telemetry'}
                </span>
              </div>

              {/* Price Row */}
              <div className="flex items-baseline gap-2.5 mt-1">
                <span className="text-2xl sm:text-3xl font-extrabold font-mono text-fg tracking-tight">
                  {selectedSymbol === 'KSE100'
                    ? kseClose.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
                    : (ohlcv?.candles[ohlcv.candles.length - 1]?.close || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
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

            {/* Quick Ticker Switcher Toolbar */}
            <div className="flex flex-wrap items-center gap-1 bg-bg-elevated p-1 rounded-xl border border-border">
              {POPULAR_TICKERS.map(sym => (
                <button
                  key={sym}
                  onClick={() => setSelectedSymbol(sym)}
                  className={`px-2 py-1 rounded-lg text-xs font-mono font-bold transition-all ${
                    selectedSymbol === sym
                      ? 'bg-brand-500 text-white shadow-sm'
                      : 'text-fg-muted hover:text-fg hover:bg-bg-card'
                  }`}
                >
                  {sym}
                </button>
              ))}
            </div>
          </div>

          {/* Canvas Chart with Candlestick Pattern Overlay Markers */}
          <div className="flex-1 min-h-[390px] w-full mt-2">
            {chartLoading ? (
              <div className="h-[390px] flex items-center justify-center text-fg-subtle gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-brand-500" />
                <span>Loading {selectedSymbol} candlestick and pattern telemetry...</span>
              </div>
            ) : ohlcv ? (
              <TradingViewChart
                candles={ohlcv.candles}
                patterns={ohlcv.patterns || []}
                symbol={selectedSymbol}
                height={390}
                showVolume
                showEMAs
                showPatterns
              />
            ) : (
              <div className="h-full flex items-center justify-center text-fg-subtle">
                Loading candlestick telemetry...
              </div>
            )}
          </div>
        </Card>

        {/* Right: Key Stats & Detected Formations KPI Card */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Card A: Candlestick Formations Scanner KPI */}
          <Card className="p-5 space-y-3.5 border-brand-500/30 bg-gradient-to-br from-brand-500/5 via-bg-card to-bg-card">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 rounded-lg bg-brand-500/10 text-brand-600 dark:text-brand-400">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <span className="font-bold text-sm text-fg">Detected Formations</span>
                  <div className="text-[11px] text-fg-subtle font-mono">Scanner: {selectedSymbol}</div>
                </div>
              </div>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-md bg-brand-500/10 text-brand-500 border border-brand-500/20">
                180D Window
              </span>
            </div>

            <div className="flex items-baseline justify-between pt-1">
              <div>
                <div className="text-3xl font-extrabold font-mono text-fg tracking-tight">
                  {patternsList.length}
                </div>
                <div className="text-[11px] text-fg-subtle">Total Candlestick Patterns</div>
              </div>

              {/* Breakdown Pills */}
              <div className="flex flex-col items-end gap-1.5 text-xs font-mono">
                <div className="flex items-center gap-1.5">
                  <span className="text-fg-subtle text-[11px]">Bullish:</span>
                  <span className="px-2 py-0.2 rounded font-bold bg-bull-bg text-bull border border-bull/20">
                    {bullishCount}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-fg-subtle text-[11px]">Bearish:</span>
                  <span className="px-2 py-0.2 rounded font-bold bg-bear-bg text-bear border border-bear/20">
                    {bearishCount}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-fg-subtle text-[11px]">Neutral:</span>
                  <span className="px-2 py-0.2 rounded font-bold bg-amber-500/10 text-amber-500 border border-amber-500/20">
                    {neutralCount}
                  </span>
                </div>
              </div>
            </div>

            <button
              onClick={() => {
                setActiveTab('patterns');
                const el = document.getElementById('dashboard-intelligence-section');
                el?.scrollIntoView({ behavior: 'smooth' });
              }}
              className="w-full py-2 px-3 rounded-xl bg-brand-500/10 hover:bg-brand-500 hover:text-white text-brand-600 dark:text-brand-400 font-semibold text-xs transition-colors flex items-center justify-center gap-1.5"
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Explore All {patternsList.length} Formations</span>
            </button>
          </Card>

          {/* Card B: Market Stats & Day/52W Sliders */}
          <Card className="p-5 flex-1 flex flex-col justify-between space-y-3">
            <div className="border-b border-border pb-2.5">
              <span className="font-semibold text-sm text-fg">Trading Range & Liquidity</span>
              <div className="text-xs text-fg-subtle mt-0.5">Session statistics for {selectedSymbol}</div>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex items-center justify-between py-1 border-b border-border/40">
                <span className="text-fg-muted">Trading Volume</span>
                <span className="font-mono font-bold text-fg">
                  {((ohlcv?.stats?.total_volume || 173650000) / 1000000).toFixed(2)}M shares
                </span>
              </div>

              {/* Day Range Slider */}
              <div className="space-y-1">
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
              <div className="space-y-1">
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

            <div className="pt-2 border-t border-border">
              <button
                onClick={() => navigate(`/analysis/${selectedSymbol}`)}
                className="w-full py-2 px-3 rounded-xl border border-border hover:border-brand-500/50 bg-bg-elevated hover:bg-bg-card font-semibold text-xs text-fg transition-colors flex items-center justify-center gap-1.5"
              >
                <span>Deep Quantitative Analysis for {selectedSymbol}</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </Card>
        </div>
      </div>

      {/* 4. Candlestick Formations & Intelligence Workspace Drawer */}
      <div id="dashboard-intelligence-section" className="space-y-3">
        <div className="flex items-center justify-between border-b border-border pb-2">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('patterns')}
              className={`flex items-center gap-2 pb-2 text-sm font-bold border-b-2 transition-all ${
                activeTab === 'patterns'
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-fg-muted hover:text-fg'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              <span>Candlestick Formations ({patternsList.length})</span>
            </button>

            <button
              onClick={() => setActiveTab('news')}
              className={`flex items-center gap-2 pb-2 text-sm font-bold border-b-2 transition-all ${
                activeTab === 'news'
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-fg-muted hover:text-fg'
              }`}
            >
              <Zap className="w-4 h-4" />
              <span>FinBERT Sentiment News</span>
            </button>

            <button
              onClick={() => setActiveTab('announcements')}
              className={`flex items-center gap-2 pb-2 text-sm font-bold border-b-2 transition-all ${
                activeTab === 'announcements'
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-fg-muted hover:text-fg'
              }`}
            >
              <Layers className="w-4 h-4" />
              <span>PSX Official Announcements</span>
            </button>
          </div>

          <span className="text-xs text-fg-subtle hidden sm:inline font-mono">
            Active Ticker: <b className="text-brand-500">{selectedSymbol}</b>
          </span>
        </div>

        {activeTab === 'patterns' && (
          <CandlestickPatternsList
            patterns={patternsList}
            title={`Detected Candlestick Formations for ${selectedSymbol}`}
            onSelectPattern={p => {
              window.scrollTo({ top: 320, behavior: 'smooth' });
            }}
          />
        )}

        {activeTab === 'news' && (
          <NewsSentimentCard news={news} />
        )}

        {activeTab === 'announcements' && (
          <AnnouncementsCard />
        )}
      </div>

      {/* 5. Market Breadth & Sentiment (Fear & Greed) Dual Strip */}
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

      {/* 6. Market Movers Table */}
      <div>
        <MarketMoversTable stocks={stocks} />
      </div>

      {/* 7. Dual Grid: Forex & Commodities + AI Assistant CTA */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-6">
          <CommoditiesForexCard />
        </div>

        <div className="lg:col-span-6">
          <Card className="p-6 bg-gradient-to-br from-brand-900/30 via-bg-card to-bg-card border-brand-500/30 flex flex-col justify-between space-y-4 h-full">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-brand-600 dark:text-brand-400 font-bold text-base">
                <Bot className="w-5 h-5" />
                <span>Ask PSXpert AI Assistant</span>
              </div>
              <p className="text-xs sm:text-sm text-fg-muted leading-relaxed">
                Have questions about candlestick reversals, corporate dividends, walk-forward genetic optimizations, or KSE-100 regimes? Chat with our RAG research assistant.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-2">
              <button
                onClick={() => navigate('/assistant')}
                className="py-2.5 px-4 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors shadow-sm"
              >
                <Sparkles className="w-4 h-4" />
                <span>Launch Research Assistant</span>
              </button>

              <button
                onClick={() => navigate(`/analysis/${selectedSymbol}`)}
                className="py-2.5 px-4 rounded-xl border border-border bg-bg-elevated hover:bg-bg-card text-fg font-semibold text-xs flex items-center justify-center gap-1.5 transition-colors"
              >
                <span>View Full Analysis ({selectedSymbol})</span>
                <ArrowUpRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
