import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { TradingViewChart } from '@/components/charts/TradingViewChart';
import { IndicatorCardsGrid } from '@/components/analysis/IndicatorCardsGrid';
import { MultiAgentCommitteePanel } from '@/components/analysis/MultiAgentCommitteePanel';
import { HMMRegimeCard } from '@/components/analysis/HMMRegimeCard';
import { GAOptimizationCard } from '@/components/analysis/GAOptimizationCard';
import { CandlestickPatternsList } from '@/components/analysis/CandlestickPatternsList';
import { CompanyFundamentalsTab } from '@/components/analysis/CompanyFundamentalsTab';
import { AnnouncementsCard } from '@/components/dashboard/AnnouncementsCard';
import { api } from '@/api/client';
import {
  OHLCVResponse,
  IndicatorsResponse,
  HMMRegimeResult,
  GAOptimizationResult,
  MultiAgentCommittee,
} from '@/types';
import {
  TrendingUp,
  ArrowUpRight,
  ArrowDownRight,
  SlidersHorizontal,
  Bot,
  Star,
  Layers,
  FileSpreadsheet,
  Activity,
  Dna,
  PieChart,
  Users,
  Search,
} from 'lucide-react';

type TabType = 'technicals' | 'agents' | 'regimes' | 'fundamentals' | 'filings';

export const MarketAnalysisPage: React.FC = () => {
  const { symbol = 'MEBL' } = useParams<{ symbol?: string }>();
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<TabType>('technicals');
  const [ohlcv, setOhlcv] = useState<OHLCVResponse | null>(null);
  const [indicators, setIndicators] = useState<IndicatorsResponse | null>(null);
  const [hmmData, setHmmData] = useState<HMMRegimeResult | null>(null);
  const [gaData, setGaData] = useState<GAOptimizationResult | null>(null);
  const [agentCommittee, setAgentCommittee] = useState<MultiAgentCommittee | null>(null);
  const [loading, setLoading] = useState(true);

  // Watchlist state
  const [isWatchlisted, setIsWatchlisted] = useState(false);

  useEffect(() => {
    try {
      const list = JSON.parse(localStorage.getItem('psxpert_watchlist') || '[]');
      setIsWatchlisted(list.includes(symbol.toUpperCase()));
    } catch {
      setIsWatchlisted(false);
    }
  }, [symbol]);

  const toggleWatchlist = () => {
    try {
      const list = JSON.parse(localStorage.getItem('psxpert_watchlist') || '[]');
      const sym = symbol.toUpperCase();
      const updated = list.includes(sym) ? list.filter((s: string) => s !== sym) : [...list, sym];
      localStorage.setItem('psxpert_watchlist', JSON.stringify(updated));
      setIsWatchlisted(updated.includes(sym));
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    async function loadAnalysis() {
      setLoading(true);
      const sym = symbol.toUpperCase();
      try {
        const [ohlcvRes, indRes, hmmRes, gaRes, agentRes] = await Promise.all([
          api.getOHLCV(sym, 180),
          api.getIndicators(sym, 180),
          api.getHMMRegime(sym, 750),
          api.getGAOptimization(sym, 750),
          api.getMultiAgentAnalysis(sym),
        ]);

        setOhlcv(ohlcvRes.data);
        setIndicators(indRes.data);
        setHmmData(hmmRes.data);
        setGaData(gaRes.data);
        setAgentCommittee(agentRes.data);
      } catch (err) {
        console.error('Failed to load market analysis:', err);
      } finally {
        setLoading(false);
      }
    }
    loadAnalysis();
  }, [symbol]);

  const latestCandle = ohlcv?.candles?.[ohlcv.candles.length - 1];
  const price = latestCandle?.close || (symbol === 'KSE100' ? 176294.33 : 248.50);
  const open = latestCandle?.open || price * 0.99;
  const change = price - open;
  const pctChange = (change / (open || 1)) * 100;
  const isUp = change >= 0;

  const latestRecord = indicators?.indicators?.[indicators.indicators.length - 1];

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* 1. Stock Header Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-border pb-5">
        <div className="flex items-start gap-3.5">
          {/* Logo badge */}
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center font-mono font-extrabold text-base text-white shadow-md shadow-brand-500/20">
            {symbol.slice(0, 3)}
          </div>

          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold font-mono text-fg tracking-tight">
                {symbol.toUpperCase()}
              </h1>
              <span className="text-xs text-fg-muted font-medium hidden sm:inline">•</span>
              <span className="text-sm font-semibold text-fg-muted">
                {ohlcv?.company?.name || `${symbol} Pakistan`}
              </span>
              {ohlcv?.company?.is_shariah && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                  Islamic
                </span>
              )}
              {ohlcv?.company?.is_kse100 && (
                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  KSE-100
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 text-xs text-fg-subtle">
              <span>{ohlcv?.company?.sector || 'PSX Listed Equities'}</span>
              <span>•</span>
              <span>DPS Exchange Ticker</span>
            </div>
          </div>
        </div>

        {/* Price & Delta Summary + Watchlist CTA */}
        <div className="flex items-center gap-4 self-start lg:self-auto">
          <div className="text-right">
            <div className="text-2xl sm:text-3xl font-black font-mono text-fg tracking-tight">
              PKR {price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div
              className={`inline-flex items-center gap-1 font-mono text-xs font-bold px-2 py-0.5 rounded ${
                isUp ? 'bg-bull-bg text-bull' : 'bg-bear-bg text-bear'
              }`}
            >
              {isUp ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
              <span>{isUp ? '+' : ''}{change.toFixed(2)} ({isUp ? '+' : ''}{pctChange.toFixed(2)}%)</span>
            </div>
          </div>

          <button
            onClick={toggleWatchlist}
            className={`p-2.5 rounded-xl border transition-all ${
              isWatchlisted
                ? 'bg-amber-500/10 border-amber-500 text-amber-500 shadow-sm'
                : 'border-border bg-bg-card text-fg-muted hover:text-amber-500 hover:border-amber-500/50'
            }`}
            title={isWatchlisted ? 'Remove from Watchlist' : 'Add to Watchlist'}
          >
            <Star className={`w-5 h-5 ${isWatchlisted ? 'fill-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* 2. Interactive Candlestick Chart */}
      <Card className="p-5 flex flex-col justify-between">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-fg">{symbol} Daily OHLCV Price Action</span>
            <span className="text-[10px] font-mono text-fg-subtle">Zero Lookahead Invariant</span>
          </div>
          <div className="text-xs text-fg-subtle font-mono">
            Period High: <strong className="text-bull font-bold">{ohlcv?.stats?.period_high?.toFixed(2)}</strong> | Low: <strong className="text-bear font-bold">{ohlcv?.stats?.period_low?.toFixed(2)}</strong>
          </div>
        </div>

        <div className="min-h-[400px] w-full mt-2">
          {ohlcv ? (
            <TradingViewChart
              candles={ohlcv.candles}
              symbol={symbol}
              height={400}
              showVolume
              showEMAs
            />
          ) : (
            <div className="h-[400px] flex items-center justify-center text-fg-subtle">
              Loading candlestick telemetry...
            </div>
          )}
        </div>
      </Card>

      {/* 3. Navigation Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto border-b border-border pb-px text-xs font-semibold">
        <button
          onClick={() => setActiveTab('technicals')}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-all flex-shrink-0 ${
            activeTab === 'technicals'
              ? 'border-brand-500 text-brand-600 dark:text-brand-400 font-bold'
              : 'border-transparent text-fg-muted hover:text-fg'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>8 Technical Indicators</span>
        </button>

        <button
          onClick={() => setActiveTab('agents')}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-all flex-shrink-0 ${
            activeTab === 'agents'
              ? 'border-brand-500 text-brand-600 dark:text-brand-400 font-bold'
              : 'border-transparent text-fg-muted hover:text-fg'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Multi-Agent Committee</span>
          <span className="w-1.5 h-1.5 rounded-full bg-brand-500" />
        </button>

        <button
          onClick={() => setActiveTab('regimes')}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-all flex-shrink-0 ${
            activeTab === 'regimes'
              ? 'border-brand-500 text-brand-600 dark:text-brand-400 font-bold'
              : 'border-transparent text-fg-muted hover:text-fg'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>HMM Regimes & GA</span>
        </button>

        <button
          onClick={() => setActiveTab('fundamentals')}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-all flex-shrink-0 ${
            activeTab === 'fundamentals'
              ? 'border-brand-500 text-brand-600 dark:text-brand-400 font-bold'
              : 'border-transparent text-fg-muted hover:text-fg'
          }`}
        >
          <PieChart className="w-4 h-4" />
          <span>Fundamentals & Ratios</span>
        </button>

        <button
          onClick={() => setActiveTab('filings')}
          className={`flex items-center gap-1.5 px-4 py-2.5 border-b-2 transition-all flex-shrink-0 ${
            activeTab === 'filings'
              ? 'border-brand-500 text-brand-600 dark:text-brand-400 font-bold'
              : 'border-transparent text-fg-muted hover:text-fg'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" />
          <span>PSX Filings & Payouts</span>
        </button>
      </div>

      {/* 4. Tab Content Panels */}
      {activeTab === 'technicals' && (
        <div className="space-y-6">
          {/* 8 Technical Indicator Cards */}
          <div>
            <div className="flex items-center justify-between mb-3 text-xs">
              <span className="font-semibold text-fg uppercase tracking-wider">
                8 Quantitative Indicators Engine (Phase 4)
              </span>
              <span className="text-fg-subtle">Zero Lookahead Bias Verified</span>
            </div>
            <IndicatorCardsGrid
              latestRecord={latestRecord}
              diagnostics={indicators?.latest_diagnostics}
            />
          </div>

          {/* Candlestick Pattern Detections */}
          <div>
            <CandlestickPatternsList patterns={ohlcv?.patterns || []} />
          </div>
        </div>
      )}

      {activeTab === 'agents' && agentCommittee && (
        <div className="space-y-6">
          <MultiAgentCommitteePanel committee={agentCommittee} />
        </div>
      )}

      {activeTab === 'regimes' && (
        <div className="space-y-6">
          {hmmData && <HMMRegimeCard data={hmmData} />}
          {gaData && <GAOptimizationCard data={gaData} />}
        </div>
      )}

      {activeTab === 'fundamentals' && (
        <div className="space-y-6">
          <CompanyFundamentalsTab symbol={symbol} />
        </div>
      )}

      {activeTab === 'filings' && (
        <div className="space-y-6">
          <AnnouncementsCard />
        </div>
      )}
    </div>
  );
};
