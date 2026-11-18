# PSXpert — Frontend Web Application

Modern quantitative technical analysis, multi-agent equity intelligence, and investment research platform for the **Pakistan Stock Exchange (PSX)**.

---

## 🚀 Tech Stack

- **Framework:** React 19 + TypeScript + Vite
- **Styling & Design System:** Tailwind CSS v4 + Plus Jakarta Sans + Investify-inspired teal design tokens (`#238989`)
- **Routing:** React Router v7
- **Data Fetching & Caching:** TanStack React Query v5
- **Financial Charting:** TradingView `lightweight-charts` v5 (60fps Candlesticks, Volume Flow, and EMA 20/50 overlays)
- **Icons:** Lucide React
- **Browser Automation / Testing:** Puppeteer Core + Chrome

---

## 📁 Application Structure

```
frontend/
├── DESIGN.md                          # Design tokens, color palette & typography
├── package.json
├── vite.config.ts                     # Proxies /api to http://127.0.0.1:8000
├── tailwind.config.js
├── src/
│   ├── api/
│   │   ├── client.ts                  # Typed API client with graceful fallback
│   │   └── mockData.ts                # Realistic fixtures for planned agent endpoints
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Navbar.tsx             # Brand header, links, search omnibar, theme toggle
│   │   │   ├── GlobalSearchModal.tsx  # Quick Ctrl+K search dialog
│   │   │   ├── MarketStatusBar.tsx    # Dynamic PKT (UTC+5) open/closed logic
│   │   │   ├── Footer.tsx             # SECP/PSX educational disclaimer & links
│   │   │   └── AppShell.tsx           # Shared page layout wrapper
│   │   ├── common/
│   │   │   ├── ThemeToggle.tsx        # Dark/Light mode switcher
│   │   │   ├── DemoBadge.tsx          # "Demo Data" notification badge
│   │   │   ├── DisclaimerBanner.tsx   # Persistent diagnostic tool disclaimer
│   │   │   ├── Badge.tsx              # Positive/Negative/Neutral pills
│   │   │   └── Card.tsx               # Investify-styled rounded card containers
│   │   ├── charts/
│   │   │   ├── TradingViewChart.tsx   # Lightweight-charts candlestick engine
│   │   │   ├── FearGreedGauge.tsx     # 0-100 semi-circle SVG needle dial
│   │   │   └── MarketBreadthBar.tsx   # Advances vs Declines proportional bar
│   │   ├── dashboard/
│   │   │   ├── MarketMoversTable.tsx  # Most Active, Gainers, Losers + Islamic filters
│   │   │   ├── AnnouncementsCard.tsx  # PSX filings with official PDF links
│   │   │   ├── NewsSentimentCard.tsx  # FinBERT scored financial headlines
│   │   │   └── CommoditiesForexCard.tsx # Gold, USD, Petrol, Brent crude rates
│   │   └── analysis/
│   │       ├── IndicatorCardsGrid.tsx # The 8 core technical indicators
│   │       ├── MultiAgentCommitteePanel.tsx # 6-agent deliberation & confidence calibration
│   │       ├── HMMRegimeCard.tsx      # Latent market regime probabilities
│   │       ├── GAOptimizationCard.tsx # Walk-Forward out-of-sample optimization
│   │       ├── CandlestickPatternsList.tsx # Detected pattern signals
│   │       └── CompanyFundamentalsTab.tsx # Audited ratios & balance sheets
│   ├── pages/
│   │   ├── DashboardPage.tsx          # Main market overview (/)
│   │   ├── ScreenerPage.tsx           # Multi-factor AI stock screener (/screener)
│   │   ├── MarketAnalysisPage.tsx     # Deep-dive per-stock analysis (/analysis/:symbol)
│   │   ├── PortfolioPage.tsx          # Holdings, allocation & risk metrics (/portfolio)
│   │   ├── AssistantPage.tsx          # Conversational RAG research chat (/assistant)
│   │   ├── ResearchInsightsPage.tsx   # FinBERT categorized feed (/insights)
│   │   ├── WatchlistPage.tsx          # Custom symbol tracking & alerts (/watchlist)
│   │   └── SettingsPage.tsx           # Preferences, theme, and host config (/settings)
│   ├── context/
│   │   └── ThemeContext.tsx           # Dark/Light theme state
│   ├── types/
│   │   └── index.ts                   # Domain TypeScript interfaces
│   └── main.tsx                       # App entry point
```

---

## ⚙️ Installation & Running

### 1. Prerequisites
- Node.js (v18+) and npm
- (Optional) Running PSXpert FastAPI backend on `http://127.0.0.1:8000`

### 2. Install Dependencies
```bash
cd frontend
npm install
```

### 3. Start Development Server
```bash
npm run dev
```
The application will launch at: **`http://localhost:5173/`**

### 4. Build for Production
```bash
npm run build
```
Build output is generated in `frontend/dist/`.

---

## 🔌 Connecting to the Backend vs. Mock Data

PSXpert features a resilient data layer in `src/api/client.ts`.

- **Live Backend Endpoints:** If the FastAPI backend is running on `http://127.0.0.1:8000`, the frontend automatically fetches live market summaries, listed stocks, sectors, real candlestick bars, and FinBERT sentiment.
- **Unreleased Agent Endpoints:** For features under ongoing model training (Multi-Agent committee, RAG chatbot, Portfolio LocalStore), the client falls back to realistic fixtures and displays a clear `Demo Data` badge.

### Configuration (`frontend/.env`):
```env
# URL of your FastAPI backend daemon
VITE_API_BASE_URL=http://127.0.0.1:8000

# Toggle to false to enforce strict live backend responses and disable mock fallbacks
VITE_USE_MOCK_FALLBACK=true
```

For the full backend API specification, see [`docs/API_CONTRACT.md`](../docs/API_CONTRACT.md).

---

## ⚖️ Regulatory Notice
Indicators, candlestick pattern detections, and neural language model inferences are strictly diagnostic aids designed to identify statistical tendencies and momentum shifts. They do **not** constitute securities recommendations, legal advice, or financial advisory.
