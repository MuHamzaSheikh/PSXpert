# PSXpert Design System (DESIGN.md)

Design language inspired by modern financial terminals and [Investify.pk](https://www.investify.pk/), tailored for Pakistan Stock Exchange (PSX) equity intelligence.

---

## 1. Brand & Color Palette

### 1.1 Core Brand Teal (`#238989`)
- `brand-50`: `#F0F9F9` — subtle highlight backgrounds
- `brand-100`: `#D7EFEF` — badge backgrounds (light mode)
- `brand-500`: `#238989` — primary brand color, active tabs, buttons, indicators
- `brand-600`: `#1B6E6E` — hover states
- `brand-700`: `#165757` — active states
- `brand-900`: `#0F2929` — dark accent surfaces

### 1.2 Market Direction (Bull vs Bear)
- **Bullish (Up / Gainers):**
  - Text & Accents: `#10B981` (Emerald-500)
  - Pill Background: `rgba(16, 185, 129, 0.12)`
  - Candlestick / Border: `#10B981`
- **Bearish (Down / Losers):**
  - Text & Accents: `#F43F5E` (Rose-500)
  - Pill Background: `rgba(244, 63, 94, 0.12)`
  - Candlestick / Border: `#F43F5E`
- **Neutral / Unchanged:**
  - Text: `#F59E0B` (Amber-500) or `#94A3B8` (Slate-400)
  - Pill Background: `rgba(245, 158, 11, 0.12)`

### 1.3 Surface & Contrast Tokens

| Token | Light Theme | Dark Theme | Purpose |
|---|---|---|---|
| `--color-bg` | `#F8FBFB` | `#0C1416` | Root app background |
| `--color-bg-card` | `#FFFFFF` | `#131F22` | Cards, panels, dropdowns |
| `--color-bg-elevated` | `#F1F6F6` | `#18272B` | Hover states, table headers, nested boxes |
| `--color-bg-subtle` | `#E8F0F0` | `#1F3338` | Badges, tags, track bars |
| `--color-border` | `#E2E8F0` | `#22363B` | Dividers, card strokes, table rows |
| `--color-fg` | `#0F172A` | `#F1F5F9` | Primary headings, values, labels |
| `--color-fg-muted` | `#475569` | `#94A3B8` | Subtitles, metadata, secondary text |
| `--color-fg-subtle` | `#94A3B8` | `#64748B` | Footers, timestamps, disabled items |

---

## 2. Typography

- **Primary Font Family:** `"Plus Jakarta Sans", Inter, -apple-system, sans-serif`
- **Monospace / Numerical Font Family:** `"JetBrains Mono", ui-monospace, monospace`
- **Tabular Figures:** All financial tables, prices, percentage changes, and timestamps MUST use `font-variant-numeric: tabular-nums` or `font-mono` to prevent jitter on real-time value updates.
- **Hierarchy:**
  - Page Titles: `text-2xl font-bold tracking-tight` (24px)
  - Section Headers: `text-lg font-semibold tracking-tight` (18px)
  - Card Titles: `text-sm font-medium text-fg-muted uppercase tracking-wider`
  - Big Numerical Values: `text-2xl font-extrabold font-mono tracking-tight`
  - Table Cell Text: `text-sm` (14px)
  - Badges & Microcopy: `text-xs font-semibold` (12px)

---

## 3. Radii, Spacing & Shadows

- **Border Radii:**
  - Outer Cards: `rounded-2xl` (16px)
  - Inner Panels / Sections: `rounded-xl` (12px)
  - Buttons / Inputs / Dropdowns: `rounded-lg` (8px)
  - Badges / Pill Tabs: `rounded-full` (9999px)
- **Shadows:**
  - Standard Card: `box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)`
  - Hover Card: `box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08)`
  - Elevated Modal / Search: `box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15)`

---

## 4. UI Component Anatomy

1. **Top Navbar:**
   - Wordmark: "PSXpert" with stylized green/teal upward trend icon.
   - Global Search: `Ctrl + K` instant search dialog supporting stock symbols, company names, sectors, and indices.
   - Navigation Links: Dashboard, Screener, Market Analysis, Portfolio, AI Assistant, Research & Insights, Watchlist.
   - Theme Toggle: Sun/Moon button with LocalStorage persistence.
   - Market Status Pill: Live indicator computing Pakistan Standard Time (PKT) trading window.
2. **Index Cards:**
   - Index ticker (e.g., KSE100, KSE30, KMI30).
   - Current points (large font).
   - Point change & percentage change pill with up/down arrows.
   - 7-day mini sparkline.
3. **Movers Pill Tabs:**
   - Tabs: `Most Active`, `Gainers`, `Losers`.
   - Filter chips: `KSE 100`, `All Stocks`, `Shariah Compliant`.
4. **Fear & Greed Dial:**
   - Semi-circular needle gauge ($0$ to $100$) with 5 zones: Extreme Fear ($0-24$), Fear ($25-44$), Neutral ($45-55$), Greed ($56-75$), Extreme Greed ($76-100$).
   - 30-session historical trend chart.
5. **Technical Indicator Card:**
   - Card title with indicator acronym + full name.
   - Numerical current value + state badge (`Bullish`, `Bearish`, `Neutral`, `Overbought`, `Oversold`).
   - Visual gauge, bar, or histogram.
   - 1-2 sentence plain-English diagnostic interpretation.
6. **Disclaimers & Badges:**
   - Visible banner and footer disclaimer on all analysis screens: *"Analytical diagnostics, not guaranteed signals, not financial advice."*
   - Clear amber badge: `Demo Data` wherever mock data is used.
