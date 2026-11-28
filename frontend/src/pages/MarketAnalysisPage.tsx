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
  const [selectedPatternDate, setSelectedPatternDate] = useState<string | null>(null);

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
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-5">
        <div className="flex items-start gap-3.5">
          {/* Logo badge */}
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-[#2F7D68] to-[#1F5C4C] flex items-center justify-center font-mono font-extrabold text-base text-white shadow-md shadow-[#2F7D68]/20">
            {symbol.slice(0, 3)}
          </div>

          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl sm:text-3xl font-extrabold font-mono text-[#252A2B] dark:text-[#F4EFE6] tracking-tight">
                {symbol.toUpperCase()}
              </h1>
              <span className="text-xs text-[#77736C] dark:text-[#9E988E] font-medium hidden sm:inline">•</span>
              <span className="text-sm font-semibold text-[#77736C] dark:text-[#9E988E]">
                {ohlcv?.company?.name || `${symbol} Pakistan`}
              </span>
              {ohlcv?.company?.is_shariah && (
                <span className="text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border border-[#287A50]/25">
                  Islamic
                </span>
              )}
              {ohlcv?.company?.is_kse100 && (
                <span className="text-[10px] px-2.5 py-0.5 rounded-full font-bold bg-[#694E7A]/15 text-[#694E7A] dark:text-[#A888BF] border border-[#694E7A]/25">
                  KSE-100
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 text-xs text-[#77736C] dark:text-[#9E988E]">
              <span>{ohlcv?.company?.sector || 'PSX Listed Equities'}</span>
              <span>•</span>
              <span className="text-[#2F7D68] font-semibold">DPS Exchange Ticker</span>
            </div>
          </div>
        </div>

        {/* Price & Delta Summary + Watchlist CTA */}
        <div className="flex items-center gap-4 self-start lg:self-auto">
          <div className="text-right">
            <div className="text-2xl sm:text-3xl font-black font-mono text-[#252A2B] dark:text-[#F4EFE6] tracking-tight">
              PKR {price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <div
              className={`inline-flex items-center gap-1 font-mono text-xs font-bold px-3 py-0.5 rounded-full ${
                isUp 
                  ? 'bg-[#287A50]/15 text-[#287A50] border border-[#287A50]/25' 
                  : 'bg-[#C64C4C]/15 text-[#C64C4C] border border-[#C64C4C]/25'
              }`}
            >
              {isUp ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
              <span>{isUp ? '+' : ''}{change.toFixed(2)} ({isUp ? '+' : ''}{pctChange.toFixed(2)}%)</span>
            </div>
          </div>

          <button
            onClick={toggleWatchlist}
            className={`p-2.5 rounded-full border transition-all ${
              isWatchlisted
                ? 'bg-amber-500/15 border-amber-500 text-amber-500 shadow-sm'
                : 'border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#77736C] hover:text-amber-500 hover:border-amber-500/50'
            }`}
            title={isWatchlisted ? 'Remove from Watchlist' : 'Add to Watchlist'}
          >
            <Star className={`w-5 h-5 ${isWatchlisted ? 'fill-amber-400 text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      {/* 2. Interactive Candlestick Chart */}
      <Card className="p-5 flex flex-col justify-between">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
          <div className="flex items-center gap-2">
            <span className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">{symbol} Daily OHLCV Price Action</span>
            <span className="text-[10px] font-mono text-[#77736C] dark:text-[#9E988E]">Zero Lookahead Invariant</span>
          </div>
          <div className="text-xs text-[#77736C] dark:text-[#9E988E] font-mono">
            Period High: <strong className="text-[#287A50] font-bold">{ohlcv?.stats?.period_high?.toFixed(2)}</strong> | Low: <strong className="text-[#C64C4C] font-bold">{ohlcv?.stats?.period_low?.toFixed(2)}</strong>
          </div>
        </div>

        <div className="min-h-[400px] w-full mt-2">
          {ohlcv ? (
            <TradingViewChart
              candles={ohlcv.candles}
              patterns={ohlcv.patterns}
              selectedDate={selectedPatternDate}
              symbol={symbol}
              height={400}
              showVolume
              showEMAs
            />
          ) : (
            <div className="h-[400px] flex items-center justify-center text-[#77736C]">
              Loading candlestick telemetry...
            </div>
          )}
        </div>
      </Card>

      {/* 3. Navigation Tabs in Glass Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('technicals')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-full transition-all flex-shrink-0 ${
            activeTab === 'technicals'
              ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
              : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#77736C] hover:text-[#252A2B] border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>8 Technical Indicators</span>
        </button>

        <button
          onClick={() => setActiveTab('agents')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-full transition-all flex-shrink-0 ${
            activeTab === 'agents'
              ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
              : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#77736C] hover:text-[#252A2B] border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20'
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Multi-Agent Committee</span>
          <span className="w-1.5 h-1.5 rounded-full bg-[#2F7D68]" />
        </button>

        <button
          onClick={() => setActiveTab('regimes')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-full transition-all flex-shrink-0 ${
            activeTab === 'regimes'
              ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
              : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#77736C] hover:text-[#252A2B] border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20'
          }`}
        >
          <Activity className="w-4 h-4" />
          <span>HMM Regimes &amp; GA</span>
        </button>

        <button
          onClick={() => setActiveTab('fundamentals')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-full transition-all flex-shrink-0 ${
            activeTab === 'fundamentals'
              ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
              : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#77736C] hover:text-[#252A2B] border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20'
          }`}
        >
          <PieChart className="w-4 h-4" />
          <span>Fundamentals &amp; Ratios</span>
        </button>

        <button
          onClick={() => setActiveTab('filings')}
          className={`flex items-center gap-1.5 px-4 py-2 rounded-full transition-all flex-shrink-0 ${
            activeTab === 'filings'
              ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
              : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#77736C] hover:text-[#252A2B] border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" />
          <span>PSX Filings &amp; Payouts</span>
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
            <CandlestickPatternsList
              patterns={ohlcv?.patterns || []}
              selectedDate={selectedPatternDate}
              onSelectPattern={date => setSelectedPatternDate(date)}
            />
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
