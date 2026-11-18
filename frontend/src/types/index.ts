// Core TypeScript Type Definitions for PSXpert

export interface Company {
  symbol: string;
  company_name: string;
  sector: string;
  is_kse100: boolean;
  is_shariah: boolean;
  close?: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
  pct_change?: number;
  latest_date?: string | null;
}

export interface MarketSummary {
  index_symbol: string;
  name: string;
  trading_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  point_change: number;
  pct_change: number;
  high_52w: number;
  low_52w: number;
  breadth: {
    advances: number;
    declines: number;
    unchanged: number;
    total: number;
  };
  top_gainers: {
    symbol: string;
    company_name: string;
    sector: string;
    close: number;
    pct_change: number;
    volume: number;
  }[];
  top_losers: {
    symbol: string;
    company_name: string;
    sector: string;
    close: number;
    pct_change: number;
    volume: number;
  }[];
  sentiment_summary: {
    positive: number;
    negative: number;
    neutral: number;
  };
}

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema20?: number | null;
  ema50?: number | null;
  ema200?: number | null;
  pattern?: string | null;
  pattern_type?: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | null;
  pattern_signal?: string | null;
}

export interface Pattern {
  index: number;
  date: string;
  name: string;
  type: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  signal: string;
  description?: string;
}

export interface OHLCVResponse {
  symbol: string;
  company: {
    symbol: string;
    name: string;
    sector: string;
    is_kse100?: boolean;
    is_shariah?: boolean;
  };
  total_bars: number;
  candles: Candle[];
  patterns: Pattern[];
  stats: {
    latest_close: number;
    period_high: number;
    period_low: number;
    total_volume: number;
    bullish_patterns_count: number;
    bearish_patterns_count: number;
    neutral_patterns_count: number;
  };
}

export interface TechnicalIndicatorRecord {
  trading_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  sma_20?: number | null;
  sma_50?: number | null;
  sma_200?: number | null;
  ema_12?: number | null;
  ema_26?: number | null;
  ema_20?: number | null;
  ema_50?: number | null;
  ema_200?: number | null;
  rsi_14?: number | null;
  macd_line?: number | null;
  macd_signal?: number | null;
  macd_diff?: number | null;
  bb_middle?: number | null;
  bb_upper?: number | null;
  bb_lower?: number | null;
  bb_bandwidth?: number | null;
  bb_percent_b?: number | null;
  dmi_plus_14?: number | null;
  dmi_minus_14?: number | null;
  adx_14?: number | null;
  atr_14?: number | null;
  atr_pct?: number | null;
  obv?: number | null;
  stoch_k?: number | null;
  stoch_d?: number | null;
}

export interface Diagnostics {
  rsi_condition: {
    status: 'OVERSOLD' | 'OVERBOUGHT' | 'NEUTRAL' | 'BULLISH_MOMENTUM' | 'BEARISH_MOMENTUM';
    value: number;
    explanation: string;
  };
  macd_condition: {
    status: 'BULLISH_CROSS' | 'BEARISH_CROSS' | 'BULLISH_ACCELERATING' | 'BEARISH_ACCELERATING' | 'NEUTRAL';
    explanation: string;
  };
  bollinger_condition: {
    status: 'UPPER_EXTREME' | 'LOWER_EXTREME' | 'VOLATILITY_SQUEEZE' | 'EXPANSION' | 'NORMAL';
    explanation: string;
  };
  trend_alignment: {
    status: 'STRONG_UPTREND' | 'STRONG_DOWNTREND' | 'PULLBACK' | 'CONSOLIDATION' | 'MIXED';
    explanation: string;
  };
  trend_strength: {
    status: 'STRONG_TREND' | 'DEVELOPING_TREND' | 'WEAK_ABSENT_TREND';
    adx_value: number;
    dominant_direction: 'BULLS_DOMINANT' | 'BEARS_DOMINANT' | 'BALANCED';
    explanation: string;
  };
  volatility: {
    atr_pkr: number;
    atr_pct: number;
    status: 'HIGH_VOLATILITY' | 'MODERATE_VOLATILITY' | 'LOW_VOLATILITY';
    explanation: string;
  };
  volume_flow: {
    status: 'ACCUMULATION' | 'DISTRIBUTION' | 'NEUTRAL';
    explanation: string;
  };
  stochastic_cycle: {
    status: 'OVERBOUGHT' | 'OVERSOLD' | 'NEUTRAL';
    explanation: string;
  };
}

export interface IndicatorsResponse {
  symbol: string;
  total_bars: number;
  indicators: TechnicalIndicatorRecord[];
  latest_diagnostics: Diagnostics;
}

export interface NewsArticle {
  article_id: number;
  headline: string;
  summary: string;
  publisher: string;
  url: string;
  published_at: string;
  sentiment_label: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL';
  sentiment_score: number;
  confidence: number;
  symbols_mentioned: string[];
  category: string;
  category_badge: string;
  targeted_industries: string[];
  impacted_stocks: string[];
  impact_analysis: string;
  target_sentiments?: Record<string, { label: string; score: number }>;
}

export interface HMMRegimeResult {
  symbol: string;
  current_regime: 'Bullish' | 'Bearish' | 'Sideways / Consolidation';
  regime_probability: number;
  regime_probabilities: {
    bullish: number;
    bearish: number;
    sideways: number;
  };
  regime_characteristics: {
    expected_daily_return_pct: number;
    annualized_volatility_pct: number;
    transition_persistence_pct: number;
  };
  history?: {
    date: string;
    regime: string;
    close: number;
  }[];
}

export interface GAOptimizationResult {
  symbol: string;
  best_parameters: {
    rsi_period: number;
    rsi_oversold: number;
    rsi_overbought: number;
    macd_fast: number;
    macd_slow: number;
    macd_signal: number;
    bb_period: number;
    bb_std: number;
  };
  walk_forward_metrics: {
    train_sharpe: number;
    val_sharpe: number;
    out_of_sample_sharpe: number;
    annualized_return_pct: number;
    max_drawdown_pct: number;
    win_rate_pct: number;
    overfitting_ratio: number;
  };
}

// Multi-Agent Analysis Types
export interface AgentOutput {
  id: string;
  name: string;
  role: string;
  stance: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  confidence: number; // 0 to 100
  summary: string;
  key_factors: string[];
  evidence_citations?: string[];
  risk_factors?: string[];
}

export interface MultiAgentCommittee {
  symbol: string;
  as_of_date: string;
  overall_verdict: 'STRONG_BUY' | 'MODERATE_BUY' | 'HOLD' | 'MODERATE_SELL' | 'STRONG_SELL';
  consensus_score: number; // 0 to 100
  confidence_calibration: {
    brier_score: number;
    expected_calibration_error: number; // ECE
    calibration_rating: 'WELL_CALIBRATED' | 'MODERATELY_CALIBRATED' | 'UNDERCONFIDENT' | 'OVERCONFIDENT';
  };
  disconfirmation_notes: string; // Red-team / Devil's advocate counter-arguments
  agents: {
    data_agent: AgentOutput;
    technical_agent: AgentOutput;
    fundamental_agent: AgentOutput;
    risk_agent: AgentOutput;
    market_context_agent: AgentOutput;
    disconfirmation_agent: AgentOutput;
  };
}

// Portfolio Types
export interface PortfolioHolding {
  id: string;
  symbol: string;
  company_name: string;
  sector: string;
  shares: number;
  avg_buy_price: number;
  current_price: number;
  total_cost: number;
  current_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  portfolio_weight_pct: number;
}

export interface PortfolioSummary {
  total_portfolio_value: number;
  total_invested_capital: number;
  cash_balance: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  daily_pnl: number;
  daily_pnl_pct: number;
  risk_metrics: {
    portfolio_beta: number;
    sharpe_ratio: number;
    daily_value_at_risk_95_pct: number; // VaR
  };
}

export interface PortfolioTrade {
  id: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  shares: number;
  price: number;
  date: string;
  total_amount: number;
  notes?: string;
}

// Watchlist Types
export interface WatchlistItem {
  symbol: string;
  company_name: string;
  sector: string;
  added_at: string;
  target_price?: number;
  notes?: string;
  alert_on_rsi?: boolean;
}

// AI Assistant Chat Types
export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  timestamp: string;
  text: string;
  evidence?: {
    source: string;
    title: string;
    snippet: string;
    url?: string;
  }[];
  confidence_score?: number;
  disclaimer_required?: boolean;
}
