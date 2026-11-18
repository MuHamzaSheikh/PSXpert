import {
  MarketSummary,
  Company,
  OHLCVResponse,
  IndicatorsResponse,
  NewsArticle,
  HMMRegimeResult,
  GAOptimizationResult,
  MultiAgentCommittee,
} from '@/types';
import {
  MOCK_MARKET_SUMMARY,
  MOCK_STOCKS,
  MOCK_SECTORS,
  MOCK_NEWS,
  MOCK_MULTI_AGENT_COMMITTEE,
} from './mockData';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

async function safeFetch<T>(url: string, fallback: T): Promise<{ data: T; isMock: boolean }> {
  try {
    const res = await fetch(`${BASE_URL}${url}`);
    if (!res.ok) {
      console.warn(`API returned ${res.status} for ${url}, using fallback.`);
      return { data: fallback, isMock: true };
    }
    const data = await res.json();
    return { data, isMock: false };
  } catch (err) {
    console.warn(`API fetch failed for ${url}:`, err, 'using fallback.');
    return { data: fallback, isMock: true };
  }
}

export const api = {
  // 1. Market Summary (KSE-100, Market Breadth, Gainers/Losers, Sentiment Summary)
  async getMarketSummary(): Promise<{ data: MarketSummary; isMock: boolean }> {
    return safeFetch<MarketSummary>('/api/market-summary', MOCK_MARKET_SUMMARY);
  },

  // 2. Listed Stocks directory with prices & sectors
  async getStocks(search?: string, sector?: string, limit: number = 100): Promise<{ data: Company[]; isMock: boolean }> {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    if (sector && sector !== 'ALL') params.append('sector', sector);
    params.append('limit', limit.toString());

    const result = await safeFetch<Company[]>(`/api/stocks?${params.toString()}`, MOCK_STOCKS);
    if (result.isMock) {
      // Apply client-side filter to mock stocks
      let filtered = [...MOCK_STOCKS];
      if (search) {
        const q = search.toUpperCase();
        filtered = filtered.filter(s => s.symbol.includes(q) || s.company_name.toUpperCase().includes(q));
      }
      if (sector && sector !== 'ALL') {
        filtered = filtered.filter(s => s.sector === sector);
      }
      return { data: filtered.slice(0, limit), isMock: true };
    }
    return result;
  },

  // 3. PSX Industry Sectors
  async getSectors(): Promise<{ data: string[]; isMock: boolean }> {
    return safeFetch<string[]>('/api/sectors', MOCK_SECTORS);
  },

  // 4. Stock or Index Candlesticks with EMA 20/50/200 and Pattern Detections
  async getOHLCV(symbol: string = 'KSE100', days: number = 180): Promise<{ data: OHLCVResponse; isMock: boolean }> {
    const sym = symbol.toUpperCase();
    const fallback = generateMockOHLCV(sym, days);
    return safeFetch<OHLCVResponse>(`/api/ohlcv/${sym}?days=${days}`, fallback);
  },

  // 5. 8 Core Technical Indicators + Plain-English Diagnostics
  async getIndicators(symbol: string = 'KSE100', days: number = 180): Promise<{ data: IndicatorsResponse; isMock: boolean }> {
    const sym = symbol.toUpperCase();
    const fallback = generateMockIndicators(sym, days);
    return safeFetch<IndicatorsResponse>(`/api/indicators/${sym}?days=${days}`, fallback);
  },

  // 6. FinBERT Scored News Feed with Industry Impacts
  async getLatestSentiment(category?: string, symbol?: string, limit: number = 35): Promise<{ data: NewsArticle[]; isMock: boolean }> {
    const params = new URLSearchParams();
    if (category && category !== 'ALL') params.append('category', category);
    if (symbol && symbol !== 'ALL') params.append('symbol', symbol);
    params.append('limit', limit.toString());

    const result = await safeFetch<NewsArticle[]>(`/api/sentiment/latest?${params.toString()}`, MOCK_NEWS);
    if (result.isMock) {
      let filtered = [...MOCK_NEWS];
      if (category && category !== 'ALL') {
        filtered = filtered.filter(n => n.category === category);
      }
      if (symbol && symbol !== 'ALL') {
        filtered = filtered.filter(n =>
          n.symbols_mentioned?.includes(symbol) ||
          n.impacted_stocks?.includes(symbol)
        );
      }
      return { data: filtered.slice(0, limit), isMock: true };
    }
    return result;
  },

  // 7. Refresh Live RSS News Stream
  async refreshNews(): Promise<any> {
    try {
      const res = await fetch(`${BASE_URL}/api/news/refresh`, { method: 'POST' });
      return await res.json();
    } catch (err) {
      return { status: 'mock', message: 'Triggered simulated news refresh' };
    }
  },

  // 8. HMM Market Regime Detection
  async getHMMRegime(symbol: string = 'KSE100', days: number = 750): Promise<{ data: HMMRegimeResult; isMock: boolean }> {
    const sym = symbol.toUpperCase();
    const fallback: HMMRegimeResult = {
      symbol: sym,
      current_regime: 'Bullish',
      regime_probability: 0.84,
      regime_probabilities: {
        bullish: 0.84,
        bearish: 0.08,
        sideways: 0.08,
      },
      regime_characteristics: {
        expected_daily_return_pct: 0.14,
        annualized_volatility_pct: 18.2,
        transition_persistence_pct: 92.4,
      },
    };
    return safeFetch<HMMRegimeResult>(`/api/quantitative/hmm?symbol=${sym}&days=${days}&states=3`, fallback);
  },

  // 9. Genetic Algorithm Walk-Forward Optimization
  async getGAOptimization(symbol: string = 'KSE100', days: number = 750): Promise<{ data: GAOptimizationResult; isMock: boolean }> {
    const sym = symbol.toUpperCase();
    const fallback: GAOptimizationResult = {
      symbol: sym,
      best_parameters: {
        rsi_period: 14,
        rsi_oversold: 32,
        rsi_overbought: 68,
        macd_fast: 12,
        macd_slow: 26,
        macd_signal: 9,
        bb_period: 20,
        bb_std: 2.1,
      },
      walk_forward_metrics: {
        train_sharpe: 1.84,
        val_sharpe: 1.62,
        out_of_sample_sharpe: 1.55,
        annualized_return_pct: 26.4,
        max_drawdown_pct: -11.2,
        win_rate_pct: 64.8,
        overfitting_ratio: 0.96,
      },
    };
    return safeFetch<GAOptimizationResult>(`/api/quantitative/ga/optimize?symbol=${sym}&days=${days}`, fallback);
  },

  // 10. Multi-Agent Analysis Committee (Mock until backend agent framework is deployed)
  async getMultiAgentAnalysis(symbol: string = 'MEBL'): Promise<{ data: MultiAgentCommittee; isMock: boolean }> {
    const mockCopy = JSON.parse(JSON.stringify(MOCK_MULTI_AGENT_COMMITTEE)) as MultiAgentCommittee;
    mockCopy.symbol = symbol.toUpperCase();
    return { data: mockCopy, isMock: true };
  },
};

// Realistic mock generator for OHLCV candlestick data
function generateMockOHLCV(symbol: string, days: number): OHLCVResponse {
  let basePrice = symbol === 'KSE100' ? 176294.33 : (symbol === 'MEBL' ? 248.50 : 212.72);
  const candles = [];
  const now = new Date();

  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    // skip weekends
    if (d.getDay() === 0 || d.getDay() === 6) continue;

    const dateStr = d.toISOString().split('T')[0];
    const volatility = basePrice * 0.015;
    const change = (Math.random() - 0.48) * volatility;
    const open = Math.round((basePrice) * 100) / 100;
    const close = Math.round((open + change) * 100) / 100;
    const high = Math.round((Math.max(open, close) + Math.random() * volatility * 0.5) * 100) / 100;
    const low = Math.round((Math.min(open, close) - Math.random() * volatility * 0.5) * 100) / 100;
    const volume = Math.round(1000000 + Math.random() * 8000000);

    candles.push({
      time: dateStr,
      open,
      high,
      low,
      close,
      volume,
      ema20: Math.round((close * 0.99) * 100) / 100,
      ema50: Math.round((close * 0.97) * 100) / 100,
      ema200: Math.round((close * 0.92) * 100) / 100,
    });
    basePrice = close;
  }

  return {
    symbol,
    company: {
      symbol,
      name: symbol === 'KSE100' ? 'KSE-100 Benchmark Index' : `${symbol} Pakistan Corporation`,
      sector: symbol === 'KSE100' ? 'Benchmark Market Index' : 'Commercial Banking',
      is_kse100: true,
      is_shariah: true,
    },
    total_bars: candles.length,
    candles,
    patterns: [
      {
        index: candles.length - 2,
        date: candles[candles.length - 2]?.time || '2026-11-17',
        name: 'Bullish Engulfing',
        type: 'BULLISH',
        signal: 'Strong Bullish Reversal Confirmation',
        description: 'Green real body completely engulfs prior session with expanding volume.',
      },
      {
        index: candles.length - 8,
        date: candles[candles.length - 8]?.time || '2026-11-10',
        name: 'Hammer',
        type: 'BULLISH',
        signal: 'Bottoming Support Test',
        description: 'Long lower shadow rejected intraday lows near moving average support.',
      },
    ],
    stats: {
      latest_close: candles[candles.length - 1]?.close || basePrice,
      period_high: Math.max(...candles.map(c => c.high)),
      period_low: Math.min(...candles.map(c => c.low)),
      total_volume: candles.reduce((acc, c) => acc + c.volume, 0),
      bullish_patterns_count: 5,
      bearish_patterns_count: 2,
      neutral_patterns_count: 3,
    },
  };
}

// Realistic mock generator for technical indicators
function generateMockIndicators(symbol: string, days: number): IndicatorsResponse {
  const ohlcv = generateMockOHLCV(symbol, days);
  const records = ohlcv.candles.map(c => ({
    trading_date: c.time,
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
    volume: c.volume,
    sma_20: c.ema20,
    sma_50: c.ema50,
    sma_200: c.ema200,
    ema_12: c.close * 1.002,
    ema_26: c.close * 0.998,
    ema_20: c.ema20,
    ema_50: c.ema50,
    ema_200: c.ema200,
    rsi_14: 58.4,
    macd_line: 4.82,
    macd_signal: 3.91,
    macd_diff: 0.91,
    bb_middle: c.close * 0.99,
    bb_upper: c.close * 1.04,
    bb_lower: c.close * 0.94,
    bb_bandwidth: 10.1,
    bb_percent_b: 0.68,
    dmi_plus_14: 28.4,
    dmi_minus_14: 16.2,
    adx_14: 27.8,
    atr_14: c.close * 0.022,
    atr_pct: 2.2,
    obv: 142000000,
    stoch_k: 68.2,
    stoch_d: 62.4,
  }));

  return {
    symbol,
    total_bars: records.length,
    indicators: records,
    latest_diagnostics: {
      rsi_condition: {
        status: 'BULLISH_MOMENTUM',
        value: 58.4,
        explanation: 'RSI-14 indicates solid positive velocity (58.4) with ample room before overbought territory (70.0).',
      },
      macd_condition: {
        status: 'BULLISH_ACCELERATING',
        explanation: 'MACD line trades above signal line with widening positive histogram (+0.91), indicating bullish momentum.',
      },
      bollinger_condition: {
        status: 'NORMAL',
        explanation: 'Price resides comfortably in the upper half of Bollinger envelope (%B = 0.68) without extreme extension.',
      },
      trend_alignment: {
        status: 'STRONG_UPTREND',
        explanation: 'Price maintains hierarchical ordering above SMA-20, SMA-50, and SMA-200 moving averages.',
      },
      trend_strength: {
        status: 'STRONG_TREND',
        adx_value: 27.8,
        dominant_direction: 'BULLS_DOMINANT',
        explanation: 'ADX-14 sits at 27.8 (trending) with +DI (28.4) maintaining dominance over -DI (16.2).',
      },
      volatility: {
        atr_pkr: 5.40,
        atr_pct: 2.2,
        status: 'MODERATE_VOLATILITY',
        explanation: 'Expected typical trading volatility is 2.2% of price per session.',
      },
      volume_flow: {
        status: 'ACCUMULATION',
        explanation: 'On-Balance Volume (OBV) continues upwards trend above 20-day EMA, confirming institutional participation.',
      },
      stochastic_cycle: {
        status: 'NEUTRAL',
        explanation: 'Fast Stochastic %K (68.2) remains in healthy expansion zone.',
      },
    },
  };
}
