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
  chartContainer: document.getElementById('tradingview-chart-container')
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

// 4. NEWS & SENTIMENT LOADING
async function loadNewsSentiment() {
  try {
    const res = await fetch('/api/sentiment/latest?limit=15');
    const news = await res.json();
    const container = elements.newsContainer;
    container.innerHTML = '';

    news.forEach(item => {
      const card = document.createElement('div');
      card.className = 'news-item';

      let labelClass = 'pill-neutral';
      if (item.sentiment_label === 'POSITIVE') labelClass = 'pill-bullish';
      if (item.sentiment_label === 'NEGATIVE') labelClass = 'pill-bearish';

      const symbols = item.symbols_mentioned.map(s => `<span class="ticker-badge" style="font-size:10px; padding:1px 5px;">${s}</span>`).join(' ');

      card.innerHTML = `
        <a href="${item.url}" target="_blank" class="news-headline">${item.headline}</a>
        <div style="margin:4px 0;">${symbols}</div>
        <div class="news-meta">
          <span>${item.publisher} • ${item.published_at ? item.published_at.split('T')[0] : ''}</span>
          <span class="pill-badge ${labelClass}">FinBERT: ${item.sentiment_label} (${(item.confidence * 100).toFixed(0)}%)</span>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading news sentiment:', err);
  }
}

// 5. EVENT LISTENERS & CONTROLS
function bindEventListeners() {
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
