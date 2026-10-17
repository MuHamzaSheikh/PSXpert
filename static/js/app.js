/**
 * PSXpert Terminal - Modern Frontend Controller
 * Connects to FastAPI backend, renders real-data TradingView candlestick charts,
 * manages technical indicator overlays, and provides interactive pattern diagnostics.
 */

// Global State
const state = {
  activeSymbol: 'KSE100',
  activeDays: 180,
  activeTab: 'kse100',
  currentSector: 'ALL',
  allStocks: [],
  marketSummary: null,
  activeOHLCV: null,
  activePatterns: [],
  isFullScreener: false,
  newsCategory: 'ALL',
  indicators: {
    ema20: true,
    ema50: true,
    ema200: false,
    volume: true,
    patterns: true
  },
  chart: null,
  candleSeries: null,
  volumeSeries: null,
  ema20Series: null,
  ema50Series: null,
  ema200Series: null
};

// DOM References
const elements = {
  tape: document.getElementById('ticker-tape'),
  searchInput: document.getElementById('search-input'),
  searchResults: document.getElementById('search-results'),
  ksePrice: document.getElementById('kse-price'),
  kseChange: document.getElementById('kse-change'),
  kseHighLow: document.getElementById('kse-high-low'),
  kse52wRange: document.getElementById('kse-52w-range'),
  breadthAdv: document.getElementById('breadth-adv'),
  breadthDec: document.getElementById('breadth-dec'),
  breadthUnch: document.getElementById('breadth-unch'),
  breadthBar: document.getElementById('breadth-bar'),
  sentPos: document.getElementById('sent-pos'),
  sentNeg: document.getElementById('sent-neg'),
  sentNeu: document.getElementById('sent-neu'),
  sentBar: document.getElementById('sent-bar'),
  totalPatternsCount: document.getElementById('total-patterns-count'),
  bullishPatternsCount: document.getElementById('bullish-patterns-count'),
  bearishPatternsCount: document.getElementById('bearish-patterns-count'),
  activeSymbolBadge: document.getElementById('active-symbol-badge'),
  activeCompanyName: document.getElementById('active-company-name'),
  activeSectorTag: document.getElementById('active-sector-tag'),
  activeMainPrice: document.getElementById('active-main-price'),
  activePriceDelta: document.getElementById('active-price-delta'),
  hudOpen: document.getElementById('hud-open'),
  hudHigh: document.getElementById('hud-high'),
  hudLow: document.getElementById('hud-low'),
  hudClose: document.getElementById('hud-close'),
  hudVol: document.getElementById('hud-vol'),
  hudDate: document.getElementById('hud-date'),
  stockList: document.getElementById('stock-list'),
  sectorFilter: document.getElementById('sector-filter'),
  patternsContainer: document.getElementById('patterns-container'),
  newsContainer: document.getElementById('news-container'),
  chartContainer: document.getElementById('tradingview-chart-container'),
  
  // Phase 4 Technical Indicators DOM references
  rsiVal: document.getElementById('rsi-val'),
  rsiBadge: document.getElementById('rsi-badge'),
  rsiBar: document.getElementById('rsi-bar'),
  macdDiffVal: document.getElementById('macd-diff-val'),
  macdLineVal: document.getElementById('macd-line-val'),
  macdSigVal: document.getElementById('macd-sig-val'),
  macdBadge: document.getElementById('macd-badge'),
  bbPctbVal: document.getElementById('bb-pctb-val'),
  bbUpVal: document.getElementById('bb-up-val'),
  bbLowVal: document.getElementById('bb-low-val'),
  bbWidthVal: document.getElementById('bb-width-val'),
  bbBadge: document.getElementById('bb-badge'),
  adxVal: document.getElementById('adx-val'),
  dmiPlusVal: document.getElementById('dmi-plus-val'),
  dmiMinusVal: document.getElementById('dmi-minus-val'),
  adxBadge: document.getElementById('adx-badge'),
  adxTrendStatus: document.getElementById('adx-trend-status'),
  atrVal: document.getElementById('atr-val'),
  atrPkrVal: document.getElementById('atr-pkr-val'),
  atrPctVal: document.getElementById('atr-pct-val'),
  stochVal: document.getElementById('stoch-val'),
  stochKVal: document.getElementById('stoch-k-val'),
  stochDVal: document.getElementById('stoch-d-val'),
  stochSlowVal: document.getElementById('stoch-slow-val'),
  stochBadge: document.getElementById('stoch-badge'),
  obvVal: document.getElementById('obv-val'),
  obvEmaVal: document.getElementById('obv-ema-val'),
  obvBadge: document.getElementById('obv-badge'),
  obvFlowStatus: document.getElementById('obv-flow-status'),
  sma20Val: document.getElementById('sma20-val'),
  ema20Val: document.getElementById('ema20-val'),
  sma50Val: document.getElementById('sma50-val'),
  ema50Val: document.getElementById('ema50-val'),
  sma200Val: document.getElementById('sma200-val'),
  ema200Val: document.getElementById('ema200-val'),
  maBadge: document.getElementById('ma-badge'),
  maAlignmentStatus: document.getElementById('ma-alignment-status'),
  diagList: document.getElementById('diag-list'),

  // Full Screener and News Catalyst elements
  chartStation: document.getElementById('chart-section') || document.querySelector('.chart-station'),
  chartViewArea: document.getElementById('chart-view-area'),
  btnChartScreener: document.getElementById('btn-chart-screener'),
  btnExitScreener: document.getElementById('btn-exit-screener'),
  btnRefreshNews: document.getElementById('btn-refresh-news'),
  newsFilterTabs: document.getElementById('news-filter-tabs')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', async () => {
  initChart();
  bindEventListeners();
  await loadMarketSummary();
  await loadSectors();
  await loadStocks();
  await loadNewsSentiment();
  await selectSymbol('KSE100');
});

// 1. CHART INITIALIZATION (TradingView Lightweight Charts)
function initChart() {
  const container = elements.chartContainer;
  container.innerHTML = '';

  const chart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight,
    layout: {
      background: { color: '#090d16' },
      textColor: '#94a3b8',
      fontFamily: 'Inter, sans-serif'
    },
    grid: {
      vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
      horzLines: { color: 'rgba(255, 255, 255, 0.04)' }
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {
        color: '#38bdf8',
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: '#0f172a'
      },
      horzLine: {
        color: '#38bdf8',
        width: 1,
        style: LightweightCharts.LineStyle.Dashed,
        labelBackgroundColor: '#0f172a'
      }
    },
    rightPriceScale: {
      borderColor: 'rgba(255, 255, 255, 0.08)',
      scaleMargins: {
        top: 0.1,
        bottom: 0.22
      }
    },
    timeScale: {
      borderColor: 'rgba(255, 255, 255, 0.08)',
      timeVisible: true,
      secondsVisible: false
    }
  });

  // Candlestick Series
  const candleSeries = chart.addCandlestickSeries({
    upColor: '#00f59b',
    downColor: '#ff3366',
    borderVisible: false,
    wickUpColor: '#00f59b',
    wickDownColor: '#ff3366'
  });

  // Volume Histogram Series
  const volumeSeries = chart.addHistogramSeries({
    priceFormat: { type: 'volume' },
    priceScaleId: '', // Separate scale
    scaleMargins: {
      top: 0.82,
      bottom: 0
    }
  });

  // Moving Average Lines
  const ema20Series = chart.addLineSeries({
    color: '#00e5ff',
    lineWidth: 1.5,
    title: 'EMA 20',
    visible: state.indicators.ema20
  });

  const ema50Series = chart.addLineSeries({
    color: '#ffb300',
    lineWidth: 1.5,
    title: 'EMA 50',
    visible: state.indicators.ema50
  });

  const ema200Series = chart.addLineSeries({
    color: '#d500f9',
    lineWidth: 1.5,
    title: 'EMA 200',
    visible: state.indicators.ema200
  });

  // Crosshair Move HUD Update
  chart.subscribeCrosshairMove(param => {
    if (!param.time || !param.seriesData) return;
    const bar = param.seriesData.get(candleSeries);
    const vol = param.seriesData.get(volumeSeries);
    if (bar) {
      elements.hudOpen.textContent = formatPKR(bar.open);
      elements.hudHigh.textContent = formatPKR(bar.high);
      elements.hudLow.textContent = formatPKR(bar.low);
      elements.hudClose.textContent = formatPKR(bar.close);
      elements.hudDate.textContent = typeof param.time === 'string' ? param.time : new Date(param.time * 1000).toISOString().split('T')[0];
    }
    if (vol) {
      elements.hudVol.textContent = vol.value.toLocaleString();
    }
  });

  // Window resize handler
  window.addEventListener('resize', () => {
    if (container && chart) {
      chart.applyOptions({
        width: container.clientWidth,
        height: container.clientHeight
      });
    }
  });

  state.chart = chart;
  state.candleSeries = candleSeries;
  state.volumeSeries = volumeSeries;
  state.ema20Series = ema20Series;
  state.ema50Series = ema50Series;
  state.ema200Series = ema200Series;
}

// 2. DATA FETCHING METHODS
async function loadMarketSummary() {
  try {
    const res = await fetch('/api/market-summary');
    if (!res.ok) throw new Error('Failed to load market summary');
    const data = await res.json();
    state.marketSummary = data;

    // Render KSE-100 Hero Card
    elements.ksePrice.textContent = formatPKR(data.close);
    const deltaColor = data.pct_change >= 0 ? '#00f59b' : '#ff3366';
    const deltaSign = data.pct_change >= 0 ? '+' : '';
    elements.kseChange.style.color = deltaColor;
    elements.kseChange.textContent = `${deltaSign}${data.point_change.toFixed(2)} (${deltaSign}${data.pct_change.toFixed(2)}%)`;
    elements.kseHighLow.textContent = `H: ${formatPKR(data.high)} | L: ${formatPKR(data.low)}`;
    elements.kse52wRange.textContent = `${formatPKR(data.low_52w)} - ${formatPKR(data.high_52w)}`;

    // Render Breadth
    const b = data.breadth;
    elements.breadthAdv.textContent = b.advances;
    elements.breadthDec.textContent = b.declines;
    elements.breadthUnch.textContent = b.unchanged;
    const advPct = (b.advances / (b.total || 1)) * 100;
    const decPct = (b.declines / (b.total || 1)) * 100;
    const unchPct = (b.unchanged / (b.total || 1)) * 100;
    elements.breadthBar.innerHTML = `
      <div class="progress-segment" style="width:${advPct}%; background:#00f59b;"></div>
      <div class="progress-segment" style="width:${unchPct}%; background:#64748b;"></div>
      <div class="progress-segment" style="width:${decPct}%; background:#ff3366;"></div>
    `;

    // Render FinBERT Sentiment Overview
    const s = data.sentiment_summary;
    elements.sentPos.textContent = s.positive;
    elements.sentNeg.textContent = s.negative;
    elements.sentNeu.textContent = s.neutral;
    const sTotal = (s.positive + s.negative + s.neutral) || 1;
    elements.sentBar.innerHTML = `
      <div class="progress-segment" style="width:${(s.positive/sTotal)*100}%; background:#00f59b;"></div>
      <div class="progress-segment" style="width:${(s.neutral/sTotal)*100}%; background:#38bdf8;"></div>
      <div class="progress-segment" style="width:${(s.negative/sTotal)*100}%; background:#ff3366;"></div>
    `;

    renderTickerTape(data);
  } catch (err) {
    console.error('Error loading market summary:', err);
  }
}

function renderTickerTape(summary) {
  const movers = [...(summary.top_gainers || []), ...(summary.top_losers || [])];
  let tapeHtml = `
    <div class="tape-item">
      <span class="tape-symbol">KSE-100</span>
      <span class="tape-price">${formatPKR(summary.close)}</span>
      <span class="${summary.pct_change >= 0 ? 'tape-up' : 'tape-down'}">
        ${summary.pct_change >= 0 ? '▲' : '▼'} ${summary.pct_change.toFixed(2)}%
      </span>
    </div>
  `;

  movers.forEach(m => {
    const isUp = m.pct_change >= 0;
    tapeHtml += `
      <div class="tape-item" onclick="selectSymbol('${m.symbol}')" style="cursor:pointer;">
        <span class="tape-symbol">${m.symbol}</span>
        <span class="tape-price">PKR ${m.close.toFixed(2)}</span>
        <span class="${isUp ? 'tape-up' : 'tape-down'}">
          ${isUp ? '▲' : '▼'} ${m.pct_change > 0 ? '+' : ''}${m.pct_change.toFixed(2)}%
        </span>
      </div>
    `;
  });

  // Duplicate for seamless infinite marquee loop
  elements.tape.innerHTML = tapeHtml + tapeHtml;
}

async function loadSectors() {
  try {
    const res = await fetch('/api/sectors');
    const sectors = await res.json();
    sectors.forEach(sec => {
      const opt = document.createElement('option');
      opt.value = sec;
      opt.textContent = sec;
      elements.sectorFilter.appendChild(opt);
    });
  } catch (err) {
    console.error('Error loading sectors:', err);
  }
}

async function loadStocks() {
  try {
    const res = await fetch('/api/stocks?limit=200');
    state.allStocks = await res.json();
    renderWatchlist();
  } catch (err) {
    console.error('Error loading stocks:', err);
  }
}

function renderWatchlist() {
  let filtered = [...state.allStocks];

  // Sector filter
  if (state.currentSector !== 'ALL') {
    filtered = filtered.filter(s => s.sector === state.currentSector);
  }

  // Tab filter
  if (state.activeTab === 'kse100') {
    filtered = filtered.filter(s => s.is_kse100);
  } else if (state.activeTab === 'gainers') {
    filtered = filtered.filter(s => s.pct_change > 0).sort((a, b) => b.pct_change - a.pct_change);
  } else if (state.activeTab === 'losers') {
    filtered = filtered.filter(s => s.pct_change < 0).sort((a, b) => a.pct_change - b.pct_change);
  } else if (state.activeTab === 'volume') {
    filtered = filtered.sort((a, b) => b.volume - a.volume);
  }

  elements.stockList.innerHTML = '';

  // Always keep KSE-100 option at top
  const kseRow = document.createElement('div');
  kseRow.className = `stock-row ${state.activeSymbol === 'KSE100' ? 'active' : ''}`;
  kseRow.onclick = () => selectSymbol('KSE100');
  const kseSummary = state.marketSummary || { close: 164776.44, pct_change: -0.21 };
  const kseUp = kseSummary.pct_change >= 0;
  kseRow.innerHTML = `
    <div>
      <div class="stock-ticker">KSE-100</div>
      <div class="stock-sec">Pakistan Stock Exchange</div>
    </div>
    <div class="stock-price-col">
      <div class="stock-curr-price">${formatPKR(kseSummary.close)}</div>
      <div class="stock-pct" style="color:${kseUp ? '#00f59b' : '#ff3366'}">
        ${kseUp ? '+' : ''}${kseSummary.pct_change.toFixed(2)}%
      </div>
    </div>
  `;
  elements.stockList.appendChild(kseRow);

  filtered.slice(0, 50).forEach(stock => {
    const row = document.createElement('div');
    row.className = `stock-row ${state.activeSymbol === stock.symbol ? 'active' : ''}`;
    row.onclick = () => selectSymbol(stock.symbol);

    const isUp = stock.pct_change >= 0;
    row.innerHTML = `
      <div>
        <div class="stock-ticker">${stock.symbol}</div>
        <div class="stock-sec">${stock.company_name}</div>
      </div>
      <div class="stock-price-col">
        <div class="stock-curr-price">PKR ${stock.close.toFixed(2)}</div>
        <div class="stock-pct" style="color:${isUp ? '#00f59b' : '#ff3366'}">
          ${isUp ? '+' : ''}${stock.pct_change.toFixed(2)}%
        </div>
      </div>
    `;
    elements.stockList.appendChild(row);
  });
}

// 3. SYMBOL SELECTION & CHART UPDATE
async function selectSymbol(symbol) {
  state.activeSymbol = symbol;
  renderWatchlist();

  try {
    const res = await fetch(`/api/ohlcv/${symbol}?days=${state.activeDays}`);
    if (!res.ok) throw new Error('Symbol not found');
    const data = await res.json();
    state.activeOHLCV = data;
    state.activePatterns = data.patterns || [];

    // Header Meta Update
    elements.activeSymbolBadge.textContent = data.symbol;
    elements.activeCompanyName.textContent = data.company.name;
    elements.activeSectorTag.textContent = `${data.company.sector} | ${data.total_bars} Sessions Analyzed`;

    const latest = data.candles[data.candles.length - 1];
    const prev = data.candles[0];
    const netPct = ((latest.close - prev.close) / prev.close) * 100;
    const isUp = netPct >= 0;

    elements.activeMainPrice.textContent = `PKR ${formatPKR(latest.close)}`;
    elements.activePriceDelta.style.color = isUp ? '#00f59b' : '#ff3366';
    elements.activePriceDelta.textContent = `${isUp ? '+' : ''}${netPct.toFixed(2)}% in period`;

    // Stats Bar Update
    elements.totalPatternsCount.textContent = data.stats.bullish_patterns_count + data.stats.bearish_patterns_count + data.stats.neutral_patterns_count;
    elements.bullishPatternsCount.textContent = data.stats.bullish_patterns_count;
    elements.bearishPatternsCount.textContent = data.stats.bearish_patterns_count;

    // Push Candlesticks to TradingView chart
    const candleData = data.candles.map(c => ({
      time: c.time,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close
    }));
    state.candleSeries.setData(candleData);

    // Push Volume data
    const volumeData = data.candles.map(c => ({
      time: c.time,
      value: c.volume,
      color: c.close >= c.open ? 'rgba(0, 245, 155, 0.45)' : 'rgba(255, 51, 102, 0.45)'
    }));
    state.volumeSeries.setData(volumeData);

    // Push EMA data
    const ema20Data = data.candles.filter(c => c.ema20 !== null).map(c => ({ time: c.time, value: c.ema20 }));
    const ema50Data = data.candles.filter(c => c.ema50 !== null).map(c => ({ time: c.time, value: c.ema50 }));
    const ema200Data = data.candles.filter(c => c.ema200 !== null).map(c => ({ time: c.time, value: c.ema200 }));
    state.ema20Series.setData(ema20Data);
    state.ema50Series.setData(ema50Data);
    state.ema200Series.setData(ema200Data);

    // Set Candlestick Pattern Markers
    if (state.indicators.patterns) {
      applyPatternMarkers(data.patterns);
    } else {
      state.candleSeries.setMarkers([]);
    }

    state.chart.timeScale().fitContent();

    // Render Pattern Cards
    renderPatternsList(data.patterns);

    // Phase 4: Fetch Quantitative Indicators & System Diagnostics
    await loadQuantitativeIndicators(symbol);

  } catch (err) {
    console.error('Error fetching OHLCV for', symbol, err);
  }
}

function applyPatternMarkers(patterns) {
  if (!patterns || !patterns.length) {
    state.candleSeries.setMarkers([]);
    return;
  }

  const markers = patterns.map(p => {
    const isBull = p.type === 'BULLISH';
    const isBear = p.type === 'BEARISH';
    return {
      time: p.date,
      position: isBull ? 'belowBar' : (isBear ? 'aboveBar' : 'aboveBar'),
      color: isBull ? '#00f59b' : (isBear ? '#ff3366' : '#94a3b8'),
      shape: isBull ? 'arrowUp' : (isBear ? 'arrowDown' : 'circle'),
      text: p.pattern,
      size: 1.2
    };
  });

  // Sort markers chronologically
  markers.sort((a, b) => new Date(a.time) - new Date(b.time));
  state.candleSeries.setMarkers(markers);
}

function renderPatternsList(patterns) {
  const container = elements.patternsContainer;
  container.innerHTML = '';

  if (!patterns || !patterns.length) {
    container.innerHTML = `<div style="color:#64748b; font-size:12px; text-align:center; padding:20px;">No classical candlestick patterns detected in this timeframe.</div>`;
    return;
  }

  // Reverse to show newest patterns first
  [...patterns].reverse().forEach(p => {
    const card = document.createElement('div');
    card.className = 'pattern-card';
    
    let pillClass = 'pill-neutral';
    let icon = '◆';
    if (p.type === 'BULLISH') {
      pillClass = 'pill-bullish';
      icon = '▲';
    } else if (p.type === 'BEARISH') {
      pillClass = 'pill-bearish';
      icon = '▼';
    }

    card.innerHTML = `
      <div class="pattern-header">
        <div class="pattern-title">${icon} ${p.pattern}</div>
        <span class="pill-badge ${pillClass}">${p.signal}</span>
      </div>
      <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
        <span class="pattern-date">${p.date}</span>
        <span style="font-size:11px; font-family:var(--font-mono); color:#fff;">PKR ${formatPKR(p.close)}</span>
      </div>
      <div class="pattern-desc">${p.description}</div>
    `;

    // Clicking pattern highlights it on chart
    card.onclick = () => {
      if (state.chart) {
        state.chart.timeScale().scrollToPosition(-5, true);
      }
    };

    container.appendChild(card);
  });
}

// 3b. QUANTITATIVE INDICATORS & SYSTEM DIAGNOSTICS (Phase 4)
async function loadQuantitativeIndicators(symbol) {
  try {
    const res = await fetch(`/api/indicators/${symbol}?days=${state.activeDays}`);
    if (!res.ok) throw new Error('Failed to fetch quantitative indicators');
    const data = await res.json();
    const diag = data.latest_diagnostics || {};

    // 1. RSI (14)
    if (diag.rsi_14 !== null && diag.rsi_14 !== undefined) {
      elements.rsiVal.textContent = diag.rsi_14.toFixed(2);
      elements.rsiBar.style.width = `${Math.min(100, Math.max(0, diag.rsi_14))}%`;
      if (diag.rsi_14 >= 70) {
        elements.rsiBadge.className = 'qc-badge bearish';
        elements.rsiBadge.textContent = 'OVERBOUGHT';
      } else if (diag.rsi_14 <= 30) {
        elements.rsiBadge.className = 'qc-badge bullish';
        elements.rsiBadge.textContent = 'OVERSOLD';
      } else {
        elements.rsiBadge.className = 'qc-badge neutral';
        elements.rsiBadge.textContent = 'NEUTRAL';
      }
    } else {
      elements.rsiVal.textContent = '--';
      elements.rsiBadge.className = 'qc-badge neutral';
      elements.rsiBadge.textContent = 'N/A';
    }

    // 2. MACD (12, 26, 9)
    if (diag.macd_diff !== null && diag.macd_diff !== undefined) {
      const diff = diag.macd_diff;
      const isPositive = diff >= 0;
      elements.macdDiffVal.textContent = `${isPositive ? '+' : ''}${diff.toFixed(2)}`;
      elements.macdDiffVal.style.color = isPositive ? 'var(--bullish)' : 'var(--bearish)';
      elements.macdLineVal.textContent = diag.macd_line !== null ? diag.macd_line.toFixed(2) : '--';
      elements.macdSigVal.textContent = diag.macd_signal !== null ? diag.macd_signal.toFixed(2) : '--';
      elements.macdBadge.className = `qc-badge ${isPositive ? 'bullish' : 'bearish'}`;
      elements.macdBadge.textContent = isPositive ? 'MOMENTUM +' : 'MOMENTUM -';
    } else {
      elements.macdDiffVal.textContent = '--';
      elements.macdDiffVal.style.color = '#fff';
      elements.macdLineVal.textContent = '--';
      elements.macdSigVal.textContent = '--';
      elements.macdBadge.className = 'qc-badge neutral';
      elements.macdBadge.textContent = 'N/A';
    }

    // 3. Bollinger Bands (20, 2)
    if (diag.bb_percent_b !== null && diag.bb_percent_b !== undefined) {
      const pctB = diag.bb_percent_b;
      elements.bbPctbVal.textContent = `%B: ${pctB.toFixed(2)}`;
      elements.bbUpVal.textContent = diag.bb_upper !== null ? formatPKR(diag.bb_upper) : '--';
      elements.bbLowVal.textContent = diag.bb_lower !== null ? formatPKR(diag.bb_lower) : '--';
      elements.bbWidthVal.textContent = diag.bb_bandwidth !== null && diag.bb_bandwidth !== undefined ? `${diag.bb_bandwidth.toFixed(2)}%` : '--';
      if (pctB > 1.0) {
        elements.bbBadge.className = 'qc-badge bearish';
        elements.bbBadge.textContent = 'ABOVE UPPER';
      } else if (pctB < 0.0) {
        elements.bbBadge.className = 'qc-badge bullish';
        elements.bbBadge.textContent = 'BELOW LOWER';
      } else {
        elements.bbBadge.className = 'qc-badge neutral';
        elements.bbBadge.textContent = 'IN BAND';
      }
    } else {
      elements.bbPctbVal.textContent = '--';
      elements.bbUpVal.textContent = '--';
      elements.bbLowVal.textContent = '--';
      elements.bbWidthVal.textContent = '--';
      elements.bbBadge.className = 'qc-badge neutral';
      elements.bbBadge.textContent = 'N/A';
    }

    // 4. ADX / DMI (14)
    if (diag.adx_14 !== null && diag.adx_14 !== undefined) {
      elements.adxVal.textContent = `ADX: ${diag.adx_14.toFixed(1)}`;
      elements.dmiPlusVal.textContent = diag.dmi_plus_14 !== null ? `+DI: ${diag.dmi_plus_14.toFixed(1)}` : '--';
      elements.dmiMinusVal.textContent = diag.dmi_minus_14 !== null ? `-DI: ${diag.dmi_minus_14.toFixed(1)}` : '--';
      const isTrending = diag.adx_14 >= 25;
      const isBullDominance = (diag.dmi_plus_14 || 0) > (diag.dmi_minus_14 || 0);
      elements.adxBadge.className = `qc-badge ${isTrending ? 'bullish' : 'neutral'}`;
      elements.adxBadge.textContent = isTrending ? 'TRENDING' : 'RANGING';
      elements.adxTrendStatus.textContent = isBullDominance ? '+DI Bull Dominance' : '-DI Bear Dominance';
    } else {
      elements.adxVal.textContent = '--';
      elements.dmiPlusVal.textContent = '--';
      elements.dmiMinusVal.textContent = '--';
      elements.adxBadge.className = 'qc-badge neutral';
      elements.adxBadge.textContent = 'N/A';
      elements.adxTrendStatus.textContent = 'Trend Strength & Dir';
    }

    // 5. ATR (14)
    if (diag.atr_14 !== null && diag.atr_14 !== undefined) {
      elements.atrVal.textContent = `${diag.atr_14.toFixed(2)} PKR`;
      elements.atrPkrVal.textContent = `${diag.atr_14.toFixed(2)} PKR`;
      elements.atrPctVal.textContent = diag.atr_pct !== null ? `${diag.atr_pct.toFixed(2)}%` : '--%';
    } else {
      elements.atrVal.textContent = '--';
      elements.atrPkrVal.textContent = '--';
      elements.atrPctVal.textContent = '--%';
    }

    // 6. Stochastic (14, 3, 3)
    if (diag.stoch_k !== null && diag.stoch_k !== undefined) {
      elements.stochVal.textContent = `%K: ${diag.stoch_k.toFixed(1)}%`;
      elements.stochKVal.textContent = `${diag.stoch_k.toFixed(1)}%`;
      elements.stochDVal.textContent = diag.stoch_d !== null ? `${diag.stoch_d.toFixed(1)}%` : '--';
      elements.stochSlowVal.textContent = diag.stoch_slow_d !== null ? `${diag.stoch_slow_d.toFixed(1)}%` : '--';
      if (diag.stoch_k >= 80) {
        elements.stochBadge.className = 'qc-badge bearish';
        elements.stochBadge.textContent = 'OVERBOUGHT';
      } else if (diag.stoch_k <= 20) {
        elements.stochBadge.className = 'qc-badge bullish';
        elements.stochBadge.textContent = 'OVERSOLD';
      } else {
        elements.stochBadge.className = 'qc-badge neutral';
        elements.stochBadge.textContent = 'MID-RANGE';
      }
    } else {
      elements.stochVal.textContent = '--';
      elements.stochKVal.textContent = '--';
      elements.stochDVal.textContent = '--';
      elements.stochSlowVal.textContent = '--';
      elements.stochBadge.className = 'qc-badge neutral';
      elements.stochBadge.textContent = 'N/A';
    }

    // 7. OBV Volume Flow
    if (diag.obv !== null && diag.obv !== undefined) {
      elements.obvVal.textContent = formatLargeNumber(diag.obv);
      elements.obvEmaVal.textContent = diag.obv_ema_20 !== null && diag.obv_ema_20 !== undefined ? formatLargeNumber(diag.obv_ema_20) : '--';
      const isAccum = (diag.obv_ema_20 !== null && diag.obv_ema_20 !== undefined) ? diag.obv >= diag.obv_ema_20 : true;
      elements.obvBadge.className = `qc-badge ${isAccum ? 'bullish' : 'bearish'}`;
      elements.obvBadge.textContent = isAccum ? 'ACCUMULATION' : 'DISTRIBUTION';
      elements.obvFlowStatus.textContent = isAccum ? 'Buying Volume Surge' : 'Selling Volume Pressure';
    } else {
      elements.obvVal.textContent = '--';
      elements.obvEmaVal.textContent = '--';
      elements.obvBadge.className = 'qc-badge neutral';
      elements.obvBadge.textContent = 'N/A';
      elements.obvFlowStatus.textContent = 'Cumulative Price-Vol';
    }

    // 8. SMA / EMA Moving Averages Alignment
    elements.sma20Val.textContent = diag.sma_20 !== null ? formatPKR(diag.sma_20) : '--';
    elements.ema20Val.textContent = diag.ema_20 !== null ? formatPKR(diag.ema_20) : '--';
    elements.sma50Val.textContent = diag.sma_50 !== null ? formatPKR(diag.sma_50) : '--';
    elements.ema50Val.textContent = diag.ema_50 !== null ? formatPKR(diag.ema_50) : '--';
    elements.sma200Val.textContent = diag.sma_200 !== null ? formatPKR(diag.sma_200) : '--';
    elements.ema200Val.textContent = diag.ema_200 !== null ? formatPKR(diag.ema_200) : '--';

    const close = diag.close;
    if (close && diag.sma_50 && diag.sma_200) {
      if (close > diag.sma_50 && diag.sma_50 > diag.sma_200) {
        elements.maBadge.className = 'qc-badge bullish';
        elements.maBadge.textContent = 'BULLISH';
        elements.maAlignmentStatus.textContent = 'Price > SMA50 > SMA200';
      } else if (close < diag.sma_50 && diag.sma_50 < diag.sma_200) {
        elements.maBadge.className = 'qc-badge bearish';
        elements.maBadge.textContent = 'BEARISH';
        elements.maAlignmentStatus.textContent = 'Price < SMA50 < SMA200';
      } else {
        elements.maBadge.className = 'qc-badge neutral';
        elements.maBadge.textContent = 'CONSOLIDATING';
        elements.maAlignmentStatus.textContent = 'Mixed Alignment';
      }
    } else {
      elements.maBadge.className = 'qc-badge neutral';
      elements.maBadge.textContent = 'NEUTRAL';
      elements.maAlignmentStatus.textContent = 'Historical Tracking';
    }

    // Diagnostic Explanations
    elements.diagList.innerHTML = '';
    const points = diag.diagnostics || [];
    if (!points.length) {
      elements.diagList.innerHTML = `<li class="diag-item"><span class="diag-bullet">▸</span><span>Insufficient historical lookback for full multi-indicator synthesis.</span></li>`;
    } else {
      points.forEach(item => {
        const li = document.createElement('li');
        li.className = 'diag-item';
        li.innerHTML = `<span class="diag-bullet">▸</span><span>${item}</span>`;
        elements.diagList.appendChild(li);
      });
    }

  } catch (err) {
    console.error('Error fetching quantitative indicators:', err);
  }
}

function formatLargeNumber(val) {
  if (val === null || val === undefined) return '--';
  const abs = Math.abs(val);
  const sign = val < 0 ? '-' : '';
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}${(abs / 1e3).toFixed(2)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

// 4. NEWS & SENTIMENT LOADING (FinBERT Market Catalysts & Geopolitical Intelligence)
async function loadNewsSentiment(cat = null) {
  if (cat !== null) {
    state.newsCategory = cat;
  }
  try {
    let url = `/api/sentiment/latest?limit=30`;
    if (state.newsCategory && state.newsCategory !== 'ALL') {
      url += `&category=${state.newsCategory}`;
    }
    const res = await fetch(url);
    const news = await res.json();
    const container = elements.newsContainer;
    container.innerHTML = '';

    if (!news || !news.length) {
      container.innerHTML = `<div style="color:#64748b; font-size:12px; text-align:center; padding:20px;">No articles found for ${state.newsCategory}. Click 'Live Refresh' to fetch feeds.</div>`;
      return;
    }

    news.forEach(item => {
      const card = document.createElement('div');
      card.className = 'news-item';

      let labelClass = 'pill-neutral';
      if (item.sentiment_label === 'POSITIVE') labelClass = 'pill-bullish';
      if (item.sentiment_label === 'NEGATIVE') labelClass = 'pill-bearish';

      let catClass = 'cat-corp';
      let catIcon = '🏢';
      if (item.category === 'GEOPOLITICAL') { catClass = 'cat-geo'; catIcon = '🌍'; }
      else if (item.category === 'MACRO_IMF') { catClass = 'cat-macro'; catIcon = '🏛️'; }
      else if (item.category === 'ENERGY_OIL') { catClass = 'cat-energy'; catIcon = '⚡'; }
      else if (item.category === 'TECH_AI') { catClass = 'cat-tech'; catIcon = '💻'; }
      else if (item.category === 'BANKING') { catClass = 'cat-bank'; catIcon = '🏦'; }
      else if (item.category === 'CEMENT') { catClass = 'cat-cement'; catIcon = '🏗️'; }

      // Targeted Industries Badges
      const industries = item.targeted_industries || [];
      const indHtml = industries.map(ind => `<span class="industry-tag">${ind}</span>`).join(' ');

      // Impacted Stocks Chips (Clickable!)
      const stocks = item.impacted_stocks || [];
      const stocksHtml = stocks.map(stk => `
        <span class="news-stock-chip" onclick="selectSymbol('${stk}')" title="Click to view ${stk} chart and technical diagnostics">${stk}</span>
      `).join(' ');

      card.innerHTML = `
        <div class="news-item-top">
          <span class="news-cat-pill ${catClass}">${catIcon} ${item.category_badge || item.category}</span>
          <span class="pill-badge ${labelClass}">FinBERT: ${item.sentiment_label} (${(item.confidence * 100).toFixed(0)}%)</span>
        </div>

        <a href="${item.url}" target="_blank" class="news-headline">${item.headline}</a>

        ${indHtml ? `
          <div class="news-industries-row">
            <span style="color:#64748b; font-size:10px; font-weight:700;">Targeted Industries:</span>
            ${indHtml}
          </div>
        ` : ''}

        ${stocksHtml ? `
          <div class="news-stocks-row">
            <span style="color:#64748b; font-size:10px; font-weight:700;">Impacted Stocks:</span>
            ${stocksHtml}
          </div>
        ` : ''}

        ${item.impact_analysis ? `
          <div class="news-transmission-box">
            <div class="news-transmission-title">💡 Transmission Impact:</div>
            <div>${item.impact_analysis}</div>
          </div>
        ` : ''}

        <div class="news-meta">
          <span>${item.publisher} • ${item.published_at ? item.published_at.split('T')[0] : ''}</span>
          <span style="color:#38bdf8; font-size:10px; font-family:var(--font-mono);">Polarity: ${item.sentiment_score > 0 ? '+' : ''}${item.sentiment_score.toFixed(2)}</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading news catalysts:', err);
  }
}

// 4b. FULL SCREENER TOGGLE & RESIZING
function resizeChartNow() {
  const resize = () => {
    if (state.chart && elements.chartContainer) {
      const width = elements.chartContainer.clientWidth;
      const height = elements.chartContainer.clientHeight;
      if (width > 0 && height > 0) {
        state.chart.applyOptions({ width, height });
        state.chart.timeScale().fitContent();
      }
    }
  };
  resize();
  setTimeout(resize, 40);
  setTimeout(resize, 120);
  setTimeout(resize, 300);
}

function updateScreenerUI() {
  if (state.isFullScreener) {
    if (elements.btnChartScreener) {
      elements.btnChartScreener.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        <span>Exit Screener</span>
      `;
    }
    if (elements.btnExitScreener) {
      elements.btnExitScreener.style.display = 'flex';
    }
  } else {
    if (elements.btnChartScreener) {
      elements.btnChartScreener.innerHTML = `
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
        <span>Full Screener</span>
      `;
    }
    if (elements.btnExitScreener) {
      elements.btnExitScreener.style.display = 'none';
    }
  }
}

function toggleFullScreener(forceState = null) {
  const targetStation = elements.chartStation || document.getElementById('chart-section') || document.querySelector('.chart-station');
  if (forceState !== null) {
    state.isFullScreener = forceState;
  } else {
    state.isFullScreener = !state.isFullScreener;
  }

  document.body.classList.toggle('full-screener-active', state.isFullScreener);
  if (targetStation) {
    targetStation.classList.toggle('full-screener-active', state.isFullScreener);
  }

  // HTML5 Fullscreen API Integration
  if (state.isFullScreener) {
    if (targetStation && targetStation.requestFullscreen && !document.fullscreenElement) {
      targetStation.requestFullscreen().catch(err => {
        console.warn('Native Fullscreen API not permitted, relying on CSS full-screener overlay:', err);
      });
    }
  } else {
    if (document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(err => console.warn(err));
    }
  }

  updateScreenerUI();
  resizeChartNow();
}

// 5. EVENT LISTENERS & CONTROLS
function bindEventListeners() {
  // Full Screener Button
  if (elements.btnChartScreener) {
    elements.btnChartScreener.addEventListener('click', () => toggleFullScreener());
  }
  if (elements.btnExitScreener) {
    elements.btnExitScreener.addEventListener('click', () => toggleFullScreener(false));
  }

  // Escape Key to Exit Full Screener
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && state.isFullScreener) {
      toggleFullScreener(false);
    }
  });

  // Native Fullscreen Change Handler (e.g. user presses ESC or browser exits fullscreen)
  document.addEventListener('fullscreenchange', () => {
    const isNativeFullscreen = !!document.fullscreenElement;
    if (!isNativeFullscreen && state.isFullScreener) {
      toggleFullScreener(false);
    }
  });

  // Window Resize
  window.addEventListener('resize', () => {
    if (state.chart && elements.chartContainer) {
      state.chart.applyOptions({
        width: elements.chartContainer.clientWidth,
        height: elements.chartContainer.clientHeight
      });
    }
  });

  // News Filter Tabs
  document.querySelectorAll('.nft-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nft-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      loadNewsSentiment(btn.dataset.cat);
    });
  });

  // News Live Refresh Button
  if (elements.btnRefreshNews) {
    elements.btnRefreshNews.addEventListener('click', async () => {
      elements.btnRefreshNews.classList.add('loading');
      try {
        const res = await fetch('/api/news/refresh', { method: 'POST' });
        const data = await res.json();
        console.log('Live news feed refresh:', data);
      } catch (err) {
        console.error('Error refreshing feeds:', err);
      } finally {
        await loadNewsSentiment();
        elements.btnRefreshNews.classList.remove('loading');
      }
    });
  }

  // Timeframe Buttons
  document.querySelectorAll('.tf-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeDays = parseInt(btn.dataset.days);
      selectSymbol(state.activeSymbol);
    });
  });

  // Watchlist Tabs
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeTab = btn.dataset.tab;
      renderWatchlist();
    });
  });

  // Sector Filter
  elements.sectorFilter.addEventListener('change', (e) => {
    state.currentSector = e.target.value;
    renderWatchlist();
  });

  // Indicator Toggles
  document.getElementById('toggle-ema20').addEventListener('click', function() {
    state.indicators.ema20 = !state.indicators.ema20;
    this.classList.toggle('active-ema20', state.indicators.ema20);
    state.ema20Series.applyOptions({ visible: state.indicators.ema20 });
  });

  document.getElementById('toggle-ema50').addEventListener('click', function() {
    state.indicators.ema50 = !state.indicators.ema50;
    this.classList.toggle('active-ema50', state.indicators.ema50);
    state.ema50Series.applyOptions({ visible: state.indicators.ema50 });
  });

  document.getElementById('toggle-ema200').addEventListener('click', function() {
    state.indicators.ema200 = !state.indicators.ema200;
    this.classList.toggle('active-ema200', state.indicators.ema200);
    state.ema200Series.applyOptions({ visible: state.indicators.ema200 });
  });

  document.getElementById('toggle-volume').addEventListener('click', function() {
    state.indicators.volume = !state.indicators.volume;
    this.classList.toggle('active-patterns', state.indicators.volume);
    state.volumeSeries.applyOptions({ visible: state.indicators.volume });
  });

  document.getElementById('toggle-patterns').addEventListener('click', function() {
    state.indicators.patterns = !state.indicators.patterns;
    this.classList.toggle('active-patterns', state.indicators.patterns);
    if (state.indicators.patterns && state.activeOHLCV) {
      applyPatternMarkers(state.activeOHLCV.patterns);
    } else {
      state.candleSeries.setMarkers([]);
    }
  });

  // Search Input Filter
  elements.searchInput.addEventListener('input', (e) => {
    const val = e.target.value.trim().toUpperCase();
    if (!val) {
      elements.searchResults.style.display = 'none';
      return;
    }

    const matches = state.allStocks.filter(s => 
      s.symbol.includes(val) || s.company_name.toUpperCase().includes(val)
    ).slice(0, 8);

    if (!matches.length) {
      elements.searchResults.style.display = 'none';
      return;
    }

    elements.searchResults.innerHTML = '';
    matches.forEach(m => {
      const item = document.createElement('div');
      item.className = 'search-item';
      item.innerHTML = `
        <div>
          <b style="color:#38bdf8;">${m.symbol}</b>
          <span style="color:#94a3b8; font-size:12px; margin-left:8px;">${m.company_name}</span>
        </div>
        <span style="font-family:var(--font-mono); font-size:12px;">PKR ${m.close.toFixed(2)}</span>
      `;
      item.onclick = () => {
        elements.searchInput.value = '';
        elements.searchResults.style.display = 'none';
        selectSymbol(m.symbol);
      };
      elements.searchResults.appendChild(item);
    });
    elements.searchResults.style.display = 'block';
  });

  // Hide search dropdown on blur
  document.addEventListener('click', (e) => {
    if (!elements.searchInput.contains(e.target) && !elements.searchResults.contains(e.target)) {
      elements.searchResults.style.display = 'none';
    }
  });
}

// Utility: format PKR
function formatPKR(val) {
  if (val === undefined || val === null) return '0.00';
  return Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
