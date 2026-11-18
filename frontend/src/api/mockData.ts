import { MarketSummary, Company, OHLCVResponse, IndicatorsResponse, NewsArticle, HMMRegimeResult, GAOptimizationResult, MultiAgentCommittee } from '@/types';

export const MOCK_MARKET_SUMMARY: MarketSummary = {
  index_symbol: "KSE100",
  name: "KSE-100 Index (Pakistan Stock Exchange)",
  trading_date: "2026-11-18",
  open: 177575.21,
  high: 177719.05,
  low: 176053.64,
  close: 176294.33,
  point_change: -1223.41,
  pct_change: -0.69,
  high_52w: 191022.73,
  low_52w: 144119.44,
  breadth: {
    advances: 178,
    declines: 285,
    unchanged: 38,
    total: 501
  },
  top_gainers: [
    { symbol: "PSL", company_name: "Pakistan Services Ltd", sector: "Miscellaneous", close: 19.34, pct_change: 10.00, volume: 102300 },
    { symbol: "CNERGY", company_name: "Cnergyico PK Ltd", sector: "Refinery", close: 11.90, pct_change: 3.93, volume: 68510000 },
    { symbol: "FNEL", company_name: "First National Equities", sector: "Investment Banks", close: 1.28, pct_change: 3.28, volume: 33240000 },
    { symbol: "PTC", company_name: "Pak Telecommunication Co", sector: "Technology & Communication", close: 45.80, pct_change: 3.00, volume: 1050000 },
    { symbol: "PRL", company_name: "Pakistan Refinery Ltd", sector: "Refinery", close: 82.38, pct_change: 3.58, volume: 28000000 },
  ],
  top_losers: [
    { symbol: "HIRAT", company_name: "Hira Textile Mills Ltd", sector: "Textile Spinning", close: 3.03, pct_change: -12.17, volume: 6180000 },
    { symbol: "UNITY", company_name: "Unity Foods Ltd", sector: "Food & Personal Care", close: 8.48, pct_change: -3.20, volume: 11240000 },
    { symbol: "PSMC", company_name: "Pak Suzuki Motors", sector: "Automobile Assembler", close: 1399.03, pct_change: -2.87, volume: 13200 },
    { symbol: "DGKC", company_name: "D.G. Khan Cement", sector: "Cement", close: 78.40, pct_change: -2.65, volume: 4210000 },
    { symbol: "LUCK", company_name: "Lucky Cement Ltd", sector: "Cement", close: 830.24, pct_change: -2.18, volume: 1700000 },
  ],
  sentiment_summary: {
    positive: 78,
    negative: 42,
    neutral: 64
  }
};

export const MOCK_INDICES = [
  { symbol: "KSE100", name: "KSE 100 Index", current: 176294.33, change: -1223.41, pct: -0.69, volume: "173.65M", high: 177719.05, low: 176053.64 },
  { symbol: "KSEALL", name: "KSE All Share Index", current: 105942.87, change: -510.97, pct: -0.48, volume: "738.80M", high: 106619.89, low: 105789.65 },
  { symbol: "KSE30", name: "KSE 30 Index", current: 51393.39, change: -359.67, pct: -0.69, volume: "77.39M", high: 51837.92, low: 51292.16 },
  { symbol: "KMI30", name: "KMI 30 Islamic Index", current: 252609.58, change: -1776.27, pct: -0.70, volume: "94.59M", high: 254717.59, low: 251803.04 },
  { symbol: "KMIALL", name: "KMI All Share Index", current: 68522.72, change: -605.32, pct: -0.88, volume: "301.27M", high: 69057.88, low: 68380.12 },
  { symbol: "PSXDIV20", name: "PSX Dividend 20 Index", current: 31043.67, change: 112.40, pct: 0.36, volume: "14.22M", high: 31150.20, low: 30980.10 },
];

export const MOCK_SECTORS = [
  "Commercial Banks",
  "Oil & Gas Exploration Companies",
  "Cement",
  "Fertilizer",
  "Technology & Communication",
  "Power Generation & Distribution",
  "Refinery",
  "Automobile Assembler",
  "Pharmaceuticals",
  "Textile Composite",
  "Food & Personal Care Products",
  "Chemicals",
  "Insurance"
];

export const MOCK_STOCKS: Company[] = [
  { symbol: "OGDC", company_name: "Oil & Gas Development Co", sector: "Oil & Gas Exploration Companies", is_kse100: true, is_shariah: true, close: 212.72, open: 214.50, high: 215.80, low: 211.20, volume: 8420000, pct_change: -0.83 },
  { symbol: "MEBL", company_name: "Meezan Bank Ltd", sector: "Commercial Banks", is_kse100: true, is_shariah: true, close: 248.50, open: 245.00, high: 249.90, low: 244.20, volume: 5120000, pct_change: 1.43 },
  { symbol: "SYS", company_name: "Systems Ltd", sector: "Technology & Communication", is_kse100: true, is_shariah: true, close: 411.58, open: 405.00, high: 414.00, low: 403.50, volume: 3840000, pct_change: 1.62 },
  { symbol: "LUCK", company_name: "Lucky Cement Ltd", sector: "Cement", is_kse100: true, is_shariah: true, close: 830.24, open: 848.00, high: 852.00, low: 828.00, volume: 1700000, pct_change: -2.18 },
  { symbol: "HUBC", company_name: "Hub Power Company Ltd", sector: "Power Generation & Distribution", is_kse100: true, is_shariah: true, close: 206.05, open: 207.80, high: 208.50, low: 205.10, volume: 6810000, pct_change: -0.84 },
  { symbol: "HBL", company_name: "Habib Bank Ltd", sector: "Commercial Banks", is_kse100: true, is_shariah: false, close: 204.13, open: 202.00, high: 205.50, low: 201.50, volume: 4230000, pct_change: 1.05 },
  { symbol: "MCB", company_name: "MCB Bank Ltd", sector: "Commercial Banks", is_kse100: true, is_shariah: false, close: 306.31, open: 305.00, high: 308.00, low: 304.50, volume: 2950000, pct_change: 0.43 },
  { symbol: "ENGROH", company_name: "Engro Holdings Ltd", sector: "Fertilizer", is_kse100: true, is_shariah: true, close: 271.39, open: 276.00, high: 277.50, low: 270.00, volume: 3100000, pct_change: -1.78 },
  { symbol: "FFC", company_name: "Fauji Fertilizer Co Ltd", sector: "Fertilizer", is_kse100: true, is_shariah: true, close: 368.68, open: 368.00, high: 371.00, low: 366.50, volume: 4610000, pct_change: 0.18 },
  { symbol: "PPL", company_name: "Pakistan Petroleum Ltd", sector: "Oil & Gas Exploration Companies", is_kse100: true, is_shariah: true, close: 222.87, open: 224.50, high: 226.00, low: 221.80, volume: 7350000, pct_change: -0.58 },
  { symbol: "UBL", company_name: "United Bank Ltd", sector: "Commercial Banks", is_kse100: true, is_shariah: false, close: 429.37, open: 424.00, high: 432.00, low: 423.50, volume: 3890000, pct_change: 1.25 },
  { symbol: "BAFL", company_name: "Bank Alfalah Ltd", sector: "Commercial Banks", is_kse100: true, is_shariah: false, close: 59.60, open: 61.00, high: 61.50, low: 59.20, volume: 5430000, pct_change: -2.30 },
  { symbol: "CNERGY", company_name: "Cnergyico PK Ltd", sector: "Refinery", is_kse100: true, is_shariah: false, close: 11.90, open: 11.45, high: 12.08, low: 11.25, volume: 68510000, pct_change: 3.93 },
  { symbol: "WTL", company_name: "Worldcall Telecom Ltd", sector: "Technology & Communication", is_kse100: false, is_shariah: false, close: 1.31, open: 1.35, high: 1.38, low: 1.28, volume: 88850000, pct_change: 0.00 },
  { symbol: "PRL", company_name: "Pakistan Refinery Ltd", sector: "Refinery", is_kse100: true, is_shariah: true, close: 82.38, open: 79.51, high: 83.19, low: 78.77, volume: 28000000, pct_change: 3.58 },
];

export const MOCK_NEWS: NewsArticle[] = [
  {
    article_id: 101,
    headline: "State Bank of Pakistan revises financing framework for builders and developers",
    summary: "SBP has revised guidelines to boost private mortgage creation and housing finance liquidity through scheduled banks.",
    publisher: "Mettis Global",
    url: "https://mettisglobal.news/sbp-revises-guidelines",
    published_at: "2026-11-18T18:24:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.78,
    confidence: 0.92,
    symbols_mentioned: ["HBL", "MEBL", "MCB"],
    category: "BANKING",
    category_badge: "Banking & Credit",
    targeted_industries: ["Commercial Banks", "Cement"],
    impacted_stocks: ["HBL", "MEBL", "LUCK", "DGKC"],
    impact_analysis: "Positive for banking loan book expansion and cement demand elasticity."
  },
  {
    article_id: 102,
    headline: "Meezan Bank 9M profit surges 28% to PKR 68.4bn with 70% interim payout",
    summary: "Pakistan's premier Islamic bank reports record net spread and lower provisions as asset quality holds firm.",
    publisher: "Business Recorder",
    url: "https://brecorder.com/mebl-9m-record-earnings",
    published_at: "2026-11-18T17:10:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.89,
    confidence: 0.96,
    symbols_mentioned: ["MEBL"],
    category: "BANKING",
    category_badge: "Banking & Credit",
    targeted_industries: ["Commercial Banks"],
    impacted_stocks: ["MEBL"],
    impact_analysis: "Reaffirms leadership in Islamic banking spreads with solid dividend yield support."
  },
  {
    article_id: 103,
    headline: "Current account records $289 million surplus in October, highest in 3 years",
    summary: "Robust remittances of $3.05bn and export growth of 11.4% turn Pakistan external account surplus.",
    publisher: "Business Recorder",
    url: "https://brecorder.com/current-account-surplus-oct",
    published_at: "2026-11-18T16:15:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.88,
    confidence: 0.95,
    symbols_mentioned: ["KSE100"],
    category: "MACRO_IMF",
    category_badge: "Macroeconomy",
    targeted_industries: ["All PSX Sectors"],
    impacted_stocks: ["KSE100", "SYS", "MEBL"],
    impact_analysis: "Eases PKR pressure and supports monetary easing trajectory."
  },
  {
    article_id: 104,
    headline: "IMF mission completes initial economic review, commends fiscal consolidation",
    summary: "International Monetary Fund delegation acknowledges revenue mobilization progress and stability reforms under EFF arrangement.",
    publisher: "Dawn News",
    url: "https://dawn.com/imf-review-progress",
    published_at: "2026-11-18T15:30:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.82,
    confidence: 0.91,
    symbols_mentioned: ["KSE100"],
    category: "MACRO_IMF",
    category_badge: "Macro & IMF",
    targeted_industries: ["All PSX Sectors"],
    impacted_stocks: ["KSE100", "OGDC", "HBL"],
    impact_analysis: "De-risks sovereign external funding obligations and supports foreign institutional inflows."
  },
  {
    article_id: 105,
    headline: "Brent crude dips to $92.61 as US inventories rise, easing refinery input costs",
    summary: "Global benchmark declines 0.65% amid supply stabilization and inventory build-up.",
    publisher: "The Express Tribune",
    url: "https://tribune.com.pk/crude-oil-slips",
    published_at: "2026-11-18T14:40:00+05:00",
    sentiment_label: "NEUTRAL",
    sentiment_score: 0.12,
    confidence: 0.81,
    symbols_mentioned: ["OGDC", "PPL", "PRL"],
    category: "ENERGY_OIL",
    category_badge: "Energy & Oil",
    targeted_industries: ["Oil & Gas Exploration", "Refinery"],
    impacted_stocks: ["OGDC", "PPL", "PRL", "CNERGY"],
    impact_analysis: "Margin expansion for domestic refineries while mild pressure on E&P realizations."
  },
  {
    article_id: 106,
    headline: "Govt finalizes incentive package for brownfield refinery upgrades under new policy",
    summary: "Refineries investing in Euro-V production capabilities to receive customs tariff and tax relief concessions.",
    publisher: "Profit by Pakistan Today",
    url: "https://profit.pakistantoday.com.pk/refinery-upgrade-policy",
    published_at: "2026-11-18T13:15:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.76,
    confidence: 0.88,
    symbols_mentioned: ["PRL", "CNERGY"],
    category: "ENERGY_OIL",
    category_badge: "Energy & Oil",
    targeted_industries: ["Refinery"],
    impacted_stocks: ["PRL", "CNERGY"],
    impact_analysis: "Unlocks long-awaited multi-million dollar modernization CAPEX cycles for PRL and CNERGY."
  },
  {
    article_id: 107,
    headline: "Systems Ltd secures $18 million European AI modernization enterprise contract",
    summary: "Pakistan's technology bellwether expands global footprint with multi-year cloud architecture and generative AI pipeline deployment.",
    publisher: "Dawn News",
    url: "https://dawn.com/systems-ltd-ai-contract",
    published_at: "2026-11-18T12:00:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.94,
    confidence: 0.97,
    symbols_mentioned: ["SYS"],
    category: "TECH_AI",
    category_badge: "Technology & Exports",
    targeted_industries: ["Technology & Communication"],
    impacted_stocks: ["SYS", "WTL"],
    impact_analysis: "Substantial US dollar revenue visibility and valuation multiple re-rating for IT sector."
  },
  {
    article_id: 108,
    headline: "Pakistan IT exports climb 34% YoY in October to record $330 million run-rate",
    summary: "SBP regulatory easements allowing 50% export retention in specialized foreign currency accounts drive aggressive remittance repatriation.",
    publisher: "Mettis Global",
    url: "https://mettisglobal.news/it-exports-october-record",
    published_at: "2026-11-18T10:45:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.91,
    confidence: 0.94,
    symbols_mentioned: ["SYS"],
    category: "TECH_AI",
    category_badge: "Technology & Exports",
    targeted_industries: ["Technology & Communication"],
    impacted_stocks: ["SYS", "PTC"],
    impact_analysis: "Broad-based earnings uplift for export-oriented technology and BPO providers."
  },
  {
    article_id: 109,
    headline: "Cement dispatches rebound 14% on lower borrowing costs and private construction pickup",
    summary: "Domestic cement despatches register double-digit recovery as southern and northern plant utilization rates reach 78%.",
    publisher: "The Express Tribune",
    url: "https://tribune.com.pk/cement-dispatches-rebound",
    published_at: "2026-11-18T09:30:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.81,
    confidence: 0.89,
    symbols_mentioned: ["LUCK", "DGKC", "MLCF"],
    category: "CEMENT",
    category_badge: "Cement & Infrastructure",
    targeted_industries: ["Cement"],
    impacted_stocks: ["LUCK", "DGKC", "MLCF"],
    impact_analysis: "Operating leverage and domestic coal blending significantly improve EBITDA per ton."
  },
  {
    article_id: 110,
    headline: "Imported Afghan and South African coal rates soften 8%, lifting cement margins",
    summary: "Input fuel costs decline across northern plants, reducing power and kiln expenses for major manufacturers.",
    publisher: "Business Recorder",
    url: "https://brecorder.com/coal-prices-soften-cement",
    published_at: "2026-11-17T16:20:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.74,
    confidence: 0.86,
    symbols_mentioned: ["LUCK", "DGKC"],
    category: "CEMENT",
    category_badge: "Cement & Infrastructure",
    targeted_industries: ["Cement"],
    impacted_stocks: ["LUCK", "DGKC"],
    impact_analysis: "Margin expansion expected across Q2 and Q3 financial performance."
  },
  {
    article_id: 111,
    headline: "OGDC announces commercial hydrocarbon discovery at exploratory well in Kohat block",
    summary: "Discovery yields 14.5 MMSCFD gas and 850 bpd condensate, boosting domestic indigenous output.",
    publisher: "Dawn News",
    url: "https://dawn.com/ogdc-discovery-kohat",
    published_at: "2026-11-18T11:20:00+05:00",
    sentiment_label: "POSITIVE",
    sentiment_score: 0.91,
    confidence: 0.96,
    symbols_mentioned: ["OGDC", "PPL"],
    category: "CORPORATE",
    category_badge: "E&P Discovery",
    targeted_industries: ["Oil & Gas Exploration Companies"],
    impacted_stocks: ["OGDC", "PPL"],
    impact_analysis: "Accretive impact on reserve replacement ratios and near-term EPS."
  },
  {
    article_id: 112,
    headline: "Engro Holdings boards approve strategic portfolio reorganization and share buyback study",
    summary: "Conglomerate evaluates capital reallocation towards high-return food and energy export ventures.",
    publisher: "Profit by Pakistan Today",
    url: "https://profit.pakistantoday.com.pk/engro-reorganization",
    published_at: "2026-11-17T14:10:00+05:00",
    sentiment_label: "NEUTRAL",
    sentiment_score: 0.25,
    confidence: 0.84,
    symbols_mentioned: ["ENGROH"],
    category: "CORPORATE",
    category_badge: "Corporate & Earnings",
    targeted_industries: ["Fertilizer", "Chemicals"],
    impacted_stocks: ["ENGROH"],
    impact_analysis: "Enhances shareholder value visibility over medium-term horizon."
  }
];

export const MOCK_COMMODITIES = [
  { name: "Gold per tola (24K)", rate: "Rs 406,500", change: "-0.60%", isUp: false },
  { name: "US Dollar (Interbank)", rate: "Rs 279.75", change: "+0.02%", isUp: true },
  { name: "Petrol per litre", rate: "Rs 325.00", change: "-1.10%", isUp: false },
  { name: "Brent Crude ($/bbl)", rate: "$92.61", change: "-0.65%", isUp: false },
];

export const MOCK_ANNOUNCEMENTS = [
  {
    id: "WAS-249475",
    symbol: "MEBL",
    company_name: "Meezan Bank Ltd",
    posting_date: "2026-11-18",
    category: "Earnings Announcements",
    title: "Financial Results for the 9-Months Ended September 30, 2026 — EPS PKR 31.42 with PKR 7.00 Interim Dividend",
    document_url: "https://dps.psx.com.pk/download/document/WAS-249475.pdf",
    sentiment: "POSITIVE",
    payout: "Rs 7.00 / share (70%)",
  },
  {
    id: "WAS-249412",
    symbol: "OGDC",
    company_name: "Oil & Gas Development Co",
    posting_date: "2026-11-17",
    category: "Material Disclosures",
    title: "Hydrocarbon Discovery at Exploratory Well Kohat-1 in Khyber Pakhtunkhwa",
    document_url: "https://dps.psx.com.pk/download/document/WAS-249412.pdf",
    sentiment: "POSITIVE",
    payout: "Commercial Reserve Update",
  },
  {
    id: "WAS-249388",
    symbol: "SYS",
    company_name: "Systems Ltd",
    posting_date: "2026-11-15",
    category: "Corporate Events",
    title: "Notice of Extraordinary General Meeting (EGM) to consider strategic MEA cloud acquisition",
    document_url: "https://dps.psx.com.pk/download/document/WAS-249388.pdf",
    sentiment: "NEUTRAL",
    payout: "EGM on Nov 28, 2026",
  },
  {
    id: "WAS-249310",
    symbol: "LUCK",
    company_name: "Lucky Cement Ltd",
    posting_date: "2026-11-12",
    category: "Dividends & Bonus Shares",
    title: "Dispatch of Final Dividend Warrants for the Financial Year Ended June 30, 2026",
    document_url: "https://dps.psx.com.pk/download/document/WAS-249310.pdf",
    sentiment: "POSITIVE",
    payout: "Rs 18.00 / share (180%)",
  }
];

export const MOCK_MULTI_AGENT_COMMITTEE: MultiAgentCommittee = {
  symbol: "MEBL",
  as_of_date: "2026-11-18",
  overall_verdict: "STRONG_BUY",
  consensus_score: 87,
  confidence_calibration: {
    brier_score: 0.124,
    expected_calibration_error: 0.048,
    calibration_rating: "WELL_CALIBRATED"
  },
  disconfirmation_notes: "Devil's advocate: While banking net interest margins (NIMs) are at historic highs, an unexpected 200 bps policy rate slash by SBP would compress asset yields faster than deposit repricing. Non-performing loan (NPL) risks in small textile exposures should be monitored.",
  agents: {
    data_agent: {
      id: "agent_data",
      name: "Data Ingestion & Integrity Agent",
      role: "Zero Lookahead Point-in-Time Verification",
      stance: "BULLISH",
      confidence: 96,
      summary: "Clean verified dataset of 6,127 daily sessions with zero duplicate entries and rigorous point-in-time publication timestamps.",
      key_factors: ["100% data integrity verified", "Financial disclosure filed on 2026-10-24 before market open", "Zero restatement discrepancies"],
      evidence_citations: ["PSX DPS Filing Ref: WAS-249475", "Audited Financials Q3-2026"]
    },
    technical_agent: {
      id: "agent_tech",
      name: "Quantitative Technical Agent",
      role: "Trend, Momentum, Volatility & Candlesticks",
      stance: "BULLISH",
      confidence: 88,
      summary: "Price trades above SMA 50 and SMA 200 with ascending EMA alignment. RSI-14 sits at 58.4 (healthy momentum acceleration without overbought exhaustion). MACD histogram expanded positively.",
      key_factors: [
        "SMA Alignment: Close (248.50) > SMA50 (236.10) > SMA200 (212.40)",
        "RSI-14 at 58.4 demonstrates bullish regime headroom",
        "Bullish Engulfing pattern detected on daily bar with 1.8x volume surge"
      ],
      evidence_citations: ["Daily OHLCV series 2026-11-18", "Volume flow OBV EMA-20 cross"]
    },
    fundamental_agent: {
      id: "agent_fund",
      name: "Fundamental & Valuation Agent",
      role: "Balance Sheet Health, Solvency & Payouts",
      stance: "BULLISH",
      confidence: 92,
      summary: "Outstanding Islamic banking franchise with Return on Equity (ROE) of 42.8% and Non-Performing Financing (NPF) ratio below 1.4%. P/E multiple of 5.8x represents a 35% discount to historical 5-year median.",
      key_factors: [
        "ROE at 42.8% vs. sector average 28.5%",
        "Capital Adequacy Ratio (CAR) at 21.4% (well above regulatory 11.5%)",
        "Consistent dividend payout ratio of 45%+"
      ],
      evidence_citations: ["State Bank Quarterly Banking Review 2026", "DPS Annual Statements 2025-2026"]
    },
    risk_agent: {
      id: "agent_risk",
      name: "Risk & Portfolio VaR Agent",
      role: "Downside Volatility, Beta & Stress Testing",
      stance: "NEUTRAL",
      confidence: 79,
      summary: "Beta against KSE-100 is 0.82 (defensive profile). 95% 1-day Value at Risk (VaR) is 2.14% (PKR 5.31). Primary systemic sensitivity is sovereign debt holdings in Sukuk.",
      key_factors: [
        "Daily VaR (95%) capped at 2.14%",
        "Max drawdown over 180 days is -7.8% vs KSE-100 -12.4%",
        "High asset liquidity ratio: Cash & equivalents > 18% of assets"
      ],
      evidence_citations: ["Historical covariance matrix 2024-2026"]
    },
    market_context_agent: {
      id: "agent_context",
      name: "Macro & FinBERT Context Agent",
      role: "Geopolitical, SBP Policy & Sector Sentiment",
      stance: "BULLISH",
      confidence: 85,
      summary: "FinBERT sentiment on Pakistani banking is +0.78 (Positive). Oct current account surplus of $289m and SBP mortgage guidelines reinforce credit stability.",
      key_factors: [
        "FinBERT sector aggregate: 82% Positive / 18% Neutral",
        "IMF 7th tranche review completed smoothly",
        "Inflation trajectory expected to moderate to single digits"
      ],
      evidence_citations: ["Dawn Business News feed", "SBP Monetary Policy Statement"]
    },
    disconfirmation_agent: {
      id: "agent_disconfirm",
      name: "Disconfirmation (Red-Team) Agent",
      role: "Adversarial Stress Testing & Bearish Scenarios",
      stance: "BEARISH",
      confidence: 72,
      summary: "Identifies downside tail risks: Rapid SBP policy rate normalization may pinch spread margins by up to 140 bps. High reliance on government GoP Ijarah Sukuk yields creates sovereign spread vulnerability.",
      key_factors: [
        "Risk of accelerated policy rate cuts eroding banking spreads",
        "Textile sector financing defaults if power tariffs stay elevated",
        "Valuation re-rating ceiling if foreign portfolio flows stall"
      ],
      evidence_citations: ["Stress-test scenario: -300 bps rate shock"]
    }
  }
};
