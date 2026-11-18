# PSXpert Frontend-Backend API Contract & Specification

> **Version:** 1.0.0  
> **Target Framework:** FastAPI (`app.py`), SQLAlchemy 2.0, PostgreSQL 14+ / SQLite  
> **Frontend Client:** `frontend/src/api/client.ts`

This document defines the interface specifications between the PSXpert React frontend and the FastAPI backend. It documents:
1. Endpoints currently live in the backend.
2. New endpoints required for planned multi-agent, chatbot, portfolio, and watchlist features, complete with JSON request and response examples.
3. How to toggle mock data off once the backend implements each endpoint.

---

## 1. Endpoints Currently Live in Backend

| Method | Live Endpoint | Parameters | Response Description |
|---|---|---|---|
| `GET` | `/api/market-summary` | None | KSE-100 latest points, point delta, % change, 52W range, market breadth (advances/declines/unchanged), top 5 gainers & losers, FinBERT sentiment counts. |
| `GET` | `/api/stocks` | `search?: str`, `sector?: str`, `limit?: int` | Listed PSX stocks with latest price, volume, change %, is_kse100, is_shariah. |
| `GET` | `/api/sectors` | None | Distinct list of PSX industry sectors. |
| `GET` | `/api/ohlcv/{symbol}` | `days: int = 180` | OHLCV daily candlestick bars, EMAs (20, 50, 200), and 20+ detected candlestick patterns. |
| `GET` | `/api/indicators/{symbol}` | `days: int = 180` | Precomputed 8 technical indicators + plain-English diagnostic interpretation object. |
| `GET` | `/api/patterns/{symbol}` | `days: int = 180` | Candlestick patterns detected in recent price history. |
| `GET` | `/api/sentiment/latest` | `category?: str`, `symbol?: str`, `limit?: int` | Financial news with FinBERT sentiment scores, confidence, targeted industries, and impacted stock tickers. |
| `POST` | `/api/news/refresh` | None | Real-time RSS feed ingest trigger for Dawn and Business Recorder. |
| `GET` | `/api/quantitative/hmm` | `symbol: str`, `days: int`, `states: int = 3` | Latent Gaussian HMM regime probabilities (Bullish, Bearish, Sideways) and transition persistence. |
| `GET` | `/api/quantitative/ga/optimize` | `symbol: str`, `days: int`, `population: int`, `generations: int` | Genetic Algorithm parameter optimization with Walk-Forward out-of-sample validation. |

---

## 2. Planned Endpoints Required by Frontend

### 2.1 Multi-Agent Deliberation Committee
- **Endpoint:** `GET /api/agents/committee/{symbol}`
- **Description:** Returns the consensus verdict, confidence calibration (Brier score, ECE), and individual specialist reports from the 6-agent committee (Data Ingestion, Technical, Fundamental, Risk, Context, Disconfirmation).
- **Request Example:**
  ```http
  GET /api/agents/committee/MEBL HTTP/1.1
  Host: 127.0.0.1:8000
  ```
- **Response Example (`200 OK`):**
  ```json
  {
    "symbol": "MEBL",
    "as_of_date": "2026-11-18",
    "overall_verdict": "STRONG_BUY",
    "consensus_score": 87,
    "confidence_calibration": {
      "brier_score": 0.124,
      "expected_calibration_error": 0.048,
      "calibration_rating": "WELL_CALIBRATED"
    },
    "disconfirmation_notes": "Devil's advocate: Rapid SBP policy rate cuts may compress net interest margins (NIMs) by 140 bps. Textile loan defaults require ongoing monitoring.",
    "agents": {
      "data_agent": {
        "id": "agent_data",
        "name": "Data Ingestion & Integrity Agent",
        "role": "Point-in-Time Zero Lookahead Verification",
        "stance": "BULLISH",
        "confidence": 96,
        "summary": "Verified 6,127 sessions with zero duplicates. Disclosure filed on 2026-10-24 prior to trading session.",
        "key_factors": ["100% data integrity verified", "Zero restatement discrepancies"],
        "evidence_citations": ["PSX DPS Ref: WAS-249475", "Audited Q3-2026 Financials"]
      },
      "technical_agent": {
        "id": "agent_tech",
        "name": "Quantitative Technical Agent",
        "role": "Trend, Momentum, Volatility & Candlesticks",
        "stance": "BULLISH",
        "confidence": 88,
        "summary": "Price trades above SMA 50 and 200 with ascending EMA alignment. RSI-14 sits at 58.4.",
        "key_factors": ["Close (248.50) > SMA50 (236.10) > SMA200 (212.40)", "Bullish Engulfing pattern with 1.8x volume"],
        "evidence_citations": ["Daily OHLCV series 2026-11-18"]
      },
      "fundamental_agent": {
        "id": "agent_fund",
        "name": "Fundamental & Valuation Agent",
        "role": "Balance Sheet Health, Solvency & Payouts",
        "stance": "BULLISH",
        "confidence": 92,
        "summary": "Return on Equity (ROE) of 42.8% and Non-Performing Financing below 1.4%. P/E multiple of 5.8x.",
        "key_factors": ["Capital Adequacy Ratio at 21.4%", "Consistent dividend payout ratio > 45%"],
        "evidence_citations": ["State Bank Banking Review 2026"]
      },
      "risk_agent": {
        "id": "agent_risk",
        "name": "Risk & Portfolio VaR Agent",
        "role": "Downside Volatility, Beta & Stress Testing",
        "stance": "NEUTRAL",
        "confidence": 79,
        "summary": "Beta against KSE-100 is 0.82. 95% 1-day Value at Risk (VaR) is 2.14% (PKR 5.31).",
        "key_factors": ["Daily VaR capped at 2.14%", "Max drawdown over 180 days is -7.8% vs KSE-100 -12.4%"],
        "evidence_citations": ["Historical covariance matrix 2024-2026"]
      },
      "market_context_agent": {
        "id": "agent_context",
        "name": "Macro & FinBERT Context Agent",
        "role": "Geopolitical, SBP Policy & Sector Sentiment",
        "stance": "BULLISH",
        "confidence": 85,
        "summary": "FinBERT sentiment on Pakistani banking is +0.78 (Positive). Oct current account surplus of $289m supports liquidity.",
        "key_factors": ["FinBERT sector aggregate: 82% Positive", "IMF 7th tranche review completed smoothly"],
        "evidence_citations": ["Dawn Business News feed", "SBP Monetary Policy Statement"]
      },
      "disconfirmation_agent": {
        "id": "agent_disconfirm",
        "name": "Disconfirmation (Red-Team) Agent",
        "role": "Adversarial Stress Testing & Bearish Scenarios",
        "stance": "BEARISH",
        "confidence": 72,
        "summary": "Identifies downside tail risks: High reliance on sovereign Sukuk yields creates spread risk if debt yields compress.",
        "key_factors": ["Risk of aggressive policy rate cuts eroding margins", "Textile power tariff pressures"],
        "evidence_citations": ["Stress-test scenario: -300 bps rate shock"]
      }
    }
  }
  ```

---

### 2.2 AI Research Assistant Chat & RAG
- **Endpoint:** `POST /api/assistant/chat`
- **Description:** Conversational query endpoint retrieving relevant exchange filings, FinBERT news articles, and quantitative indicators as RAG evidence citations.
- **Request Example:**
  ```json
  {
    "prompt": "Evaluate Meezan Bank (MEBL) quarterly dividend payout and capital adequacy.",
    "history": [
      {
        "role": "user",
        "content": "Hi, summarize today's banking market."
      }
    ]
  }
  ```
- **Response Example (`200 OK`):**
  ```json
  {
    "response": "Meezan Bank (PSX: MEBL) reported an EPS of PKR 31.42 for 9M-2026 alongside a PKR 7.00 per share interim cash dividend (70%). Its Capital Adequacy Ratio (CAR) is 21.4% against the regulatory 11.5% threshold.",
    "evidence": [
      {
        "source": "PSX DPS Regulatory Disclosure",
        "title": "MEBL Financial Results for 9-Months Ended Sept 30, 2026",
        "snippet": "Board approved interim cash dividend of Rs. 7.00 per share (70%). Profit after tax reported at PKR 48.2 billion.",
        "url": "https://dps.psx.com.pk/download/document/WAS-249475.pdf"
      }
    ],
    "confidence_score": 94,
    "disclaimer_required": true
  }
  ```

---

### 2.3 User Portfolio & Trade Logging
- **Endpoint:** `GET /api/portfolio`
- **Response Example (`200 OK`):**
  ```json
  {
    "total_portfolio_value": 1621880.0,
    "cash_balance": 350000.0,
    "total_unrealized_pnl": 110296.0,
    "total_unrealized_pnl_pct": 7.30,
    "risk_metrics": {
      "portfolio_beta": 0.88,
      "sharpe_ratio": 1.72,
      "daily_value_at_risk_95_pct": 34200.0
    },
    "holdings": [
      {
        "id": "hold_1",
        "symbol": "MEBL",
        "company_name": "Meezan Bank Ltd",
        "sector": "Commercial Banks",
        "shares": 2500,
        "avg_buy_price": 215.40,
        "current_price": 248.50,
        "total_cost": 538500.0,
        "current_value": 621250.0,
        "unrealized_pnl": 82750.0,
        "unrealized_pnl_pct": 15.37,
        "portfolio_weight_pct": 38.5
      }
    ]
  }
  ```
- **Endpoint:** `POST /api/portfolio/trade`
- **Request Example:**
  ```json
  {
    "symbol": "OGDC",
    "trade_type": "BUY",
    "shares": 500,
    "price": 212.72,
    "trade_date": "2026-11-18"
  }
  ```

---

### 2.4 User Watchlist
- **Endpoint:** `GET /api/watchlist`
- **Response Example (`200 OK`):**
  ```json
  [
    {
      "symbol": "MEBL",
      "company_name": "Meezan Bank Ltd",
      "sector": "Commercial Banks",
      "added_at": "2026-11-18T10:00:00+05:00",
      "target_price": 280.00,
      "alert_on_rsi": true
    }
  ]
  ```
- **Endpoint:** `POST /api/watchlist`
- **Request Example:** `{"symbol": "HUBC", "target_price": 225.00}`
- **Endpoint:** `DELETE /api/watchlist/{symbol}`

---

## 3. How to Toggle Mocks Off Once Backend is Deployed

In `frontend/.env`:
```env
# Point to your running FastAPI backend
VITE_API_BASE_URL=http://127.0.0.1:8000

# Set to false to bypass mock fallbacks and raise real network errors
VITE_USE_MOCK_FALLBACK=false
```

Inside `frontend/src/api/client.ts`, all calls go through `safeFetch<T>()`. When `VITE_USE_MOCK_FALLBACK=false`, any 404 or connection refusal will propagate directly to TanStack Query for error boundaries.
