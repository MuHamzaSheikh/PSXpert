import React, { useEffect, useRef, useState } from 'react';
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  ColorType,
  IChartApi,
  ISeriesApi,
  Time,
  createSeriesMarkers,
  SeriesMarker,
} from 'lightweight-charts';
import { useTheme } from '@/context/ThemeContext';
import { Candle, Pattern } from '@/types';
import { Sparkles, BarChart2, TrendingUp } from 'lucide-react';

interface TradingViewChartProps {
  candles: Candle[];
  patterns?: Pattern[];
  symbol?: string;
  height?: number;
  showVolume?: boolean;
  showEMAs?: boolean;
  showPatterns?: boolean;
  onSelectPattern?: (pattern: Pattern) => void;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  candles,
  patterns = [],
  symbol = 'KSE100',
  height = 420,
  showVolume = true,
  showEMAs = true,
  showPatterns = true,
  onSelectPattern,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const { theme } = useTheme();
  const [activeTimeframe, setActiveTimeframe] = useState('ALL');
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);

  // User interactive toggle states
  const [enableVolume, setEnableVolume] = useState(showVolume);
  const [enableEMAs, setEnableEMAs] = useState(showEMAs);
  const [enablePatterns, setEnablePatterns] = useState(showPatterns);

  const isDark = theme === 'dark';

  // Filter candles based on active timeframe
  const filteredCandles = React.useMemo(() => {
    if (!candles || candles.length === 0) return [];
    if (activeTimeframe === 'ALL') return candles;

    const limitMap: Record<string, number> = {
      '1D': 1,
      '5D': 5,
      '1M': 22,
      '3M': 66,
      '6M': 132,
      '1Y': 260,
    };
    const count = limitMap[activeTimeframe] || candles.length;
    return candles.slice(Math.max(0, candles.length - count));
  }, [candles, activeTimeframe]);

  // Filter patterns matching the visible timeframe
  const visiblePatterns = React.useMemo(() => {
    if (!patterns || patterns.length === 0) return [];
    if (filteredCandles.length === 0) return [];
    const minDate = filteredCandles[0].time;
    const maxDate = filteredCandles[filteredCandles.length - 1].time;
    return patterns.filter(p => p.date >= minDate && p.date <= maxDate);
  }, [patterns, filteredCandles]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const container = chartContainerRef.current;
    container.innerHTML = '';

    const chart = createChart(container, {
      width: container.clientWidth,
      height: height,
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: isDark ? '#94A3B8' : '#475569',
        fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
      },
      grid: {
        vertLines: { color: isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)' },
        horzLines: { color: isDark ? 'rgba(255, 255, 255, 0.04)' : 'rgba(0, 0, 0, 0.04)' },
      },
      crosshair: {
        mode: 1,
        vertLine: {
          color: '#238989',
          width: 1,
          style: 2,
          labelBackgroundColor: '#238989',
        },
        horzLine: {
          color: '#238989',
          width: 1,
          style: 2,
          labelBackgroundColor: '#238989',
        },
      },
      rightPriceScale: {
        borderColor: isDark ? '#22363B' : '#E2E8F0',
        scaleMargins: {
          top: 0.1,
          bottom: enableVolume ? 0.22 : 0.1,
        },
      },
      timeScale: {
        borderColor: isDark ? '#22363B' : '#E2E8F0',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 1. Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#10B981',
      downColor: '#F43F5E',
      borderVisible: false,
      wickUpColor: '#10B981',
      wickDownColor: '#F43F5E',
    });

    // 2. Volume series
    let volumeSeries: ISeriesApi<'Histogram'> | null = null;
    if (enableVolume) {
      volumeSeries = chart.addSeries(HistogramSeries, {
        color: '#238989',
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: '', // overlay
      });
      volumeSeries.priceScale().applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
      });
    }

    // 3. EMA Overlays
    let ema20Series: ISeriesApi<'Line'> | null = null;
    let ema50Series: ISeriesApi<'Line'> | null = null;
    if (enableEMAs) {
      ema20Series = chart.addSeries(LineSeries, {
        color: '#2DD4BF', // Teal-mint
        lineWidth: 2,
        title: 'EMA 20',
      });
      ema50Series = chart.addSeries(LineSeries, {
        color: '#F59E0B', // Amber
        lineWidth: 2,
        title: 'EMA 50',
      });
    }

    // Populate data
    if (filteredCandles && filteredCandles.length > 0) {
      const formattedCandles = filteredCandles.map(c => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      candleSeries.setData(formattedCandles);

      if (volumeSeries) {
        const volumeData = filteredCandles.map(c => ({
          time: c.time as Time,
          value: c.volume,
          color: c.close >= c.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
        }));
        volumeSeries.setData(volumeData);
      }

      if (ema20Series) {
        const ema20Data = filteredCandles
          .filter(c => c.ema20 !== undefined && c.ema20 !== null)
          .map(c => ({ time: c.time as Time, value: c.ema20 as number }));
        ema20Series.setData(ema20Data);
      }

      if (ema50Series) {
        const ema50Data = filteredCandles
          .filter(c => c.ema50 !== undefined && c.ema50 !== null)
          .map(c => ({ time: c.time as Time, value: c.ema50 as number }));
        ema50Series.setData(ema50Data);
      }

      // 4. Candlestick Pattern Markers
      if (enablePatterns && visiblePatterns && visiblePatterns.length > 0) {
        const totalPats = visiblePatterns.length;
        const markers: SeriesMarker<Time>[] = visiblePatterns.map((p, idx) => {
          const isBull = p.type === 'BULLISH';
          const isBear = p.type === 'BEARISH';
          // Label the most recent 8 patterns with full text; show neat discrete arrows for older patterns
          const isRecent = idx >= totalPats - 8;
          const patternName = p.name || p.pattern || 'Pattern';

          return {
            time: p.date as Time,
            position: isBull ? 'belowBar' : isBear ? 'aboveBar' : 'aboveBar',
            color: isBull ? '#10B981' : isBear ? '#F43F5E' : '#F59E0B',
            shape: isBull ? 'arrowUp' : isBear ? 'arrowDown' : 'circle',
            text: isRecent ? patternName : undefined,
            id: `pat-${idx}-${p.date}`,
            size: 1,
          };
        });

        createSeriesMarkers(candleSeries, markers);
      }

      chart.timeScale().fitContent();
      setHoveredCandle(filteredCandles[filteredCandles.length - 1]);
    }

    // Crosshair move listener for HUD
    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time || !param.seriesData) {
        if (filteredCandles.length > 0) setHoveredCandle(filteredCandles[filteredCandles.length - 1]);
        return;
      }
      const data = param.seriesData.get(candleSeries);
      if (data) {
        const match = filteredCandles.find(c => c.time === (param.time as string));
        if (match) {
          setHoveredCandle(match);
        }
      }
    });

    // Resize handler
    const handleResize = () => {
      if (container && chart) {
        chart.applyOptions({ width: container.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [filteredCandles, visiblePatterns, isDark, height, enableVolume, enableEMAs, enablePatterns]);

  const latest = hoveredCandle || filteredCandles[filteredCandles.length - 1] || null;

  return (
    <div className="flex flex-col w-full h-full">
      {/* Chart HUD & Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-border text-xs">
        {/* Left: Interactive Price HUD */}
        {latest ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono">
            <span className="text-fg-subtle font-sans text-xs">{latest.time}</span>
            <span>
              <span className="text-fg-subtle mr-1">O:</span>
              <strong className="text-fg">{latest.open?.toLocaleString()}</strong>
            </span>
            <span>
              <span className="text-fg-subtle mr-1">H:</span>
              <strong className="text-bull">{latest.high?.toLocaleString()}</strong>
            </span>
            <span>
              <span className="text-fg-subtle mr-1">L:</span>
              <strong className="text-bear">{latest.low?.toLocaleString()}</strong>
            </span>
            <span>
              <span className="text-fg-subtle mr-1">C:</span>
              <strong className={latest.close >= latest.open ? 'text-bull' : 'text-bear'}>
                {latest.close?.toLocaleString()}
              </strong>
            </span>
            <span className="hidden sm:inline">
              <span className="text-fg-subtle mr-1">Vol:</span>
              <strong className="text-brand-600 dark:text-brand-400">
                {(latest.volume / 1000000).toFixed(2)}M
              </strong>
            </span>
          </div>
        ) : (
          <div className="text-fg-subtle">Loading chart telemetry...</div>
        )}

        {/* Right: Feature Toggles & Timeframe Selectors */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Layer Toggle Chips */}
          <div className="flex items-center gap-1 bg-bg-elevated p-0.5 rounded-lg border border-border">
            <button
              onClick={() => setEnablePatterns(!enablePatterns)}
              title="Toggle Candlestick Pattern Overlay Markers"
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                enablePatterns
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-fg-muted hover:text-fg hover:bg-bg-card'
              }`}
            >
              <Sparkles className="w-3 h-3" />
              <span>Patterns</span>
              {visiblePatterns.length > 0 && (
                <span className={`text-[10px] px-1 rounded-full ${
                  enablePatterns ? 'bg-black/20 text-white' : 'bg-brand-500/10 text-brand-500'
                }`}>
                  {visiblePatterns.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setEnableEMAs(!enableEMAs)}
              title="Toggle EMA 20 & 50 Trends"
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                enableEMAs
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-fg-muted hover:text-fg hover:bg-bg-card'
              }`}
            >
              <TrendingUp className="w-3 h-3" />
              <span>EMAs</span>
            </button>

            <button
              onClick={() => setEnableVolume(!enableVolume)}
              title="Toggle Volume Flow Histogram"
              className={`flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                enableVolume
                  ? 'bg-brand-500 text-white shadow-sm'
                  : 'text-fg-muted hover:text-fg hover:bg-bg-card'
              }`}
            >
              <BarChart2 className="w-3 h-3" />
              <span>Vol</span>
            </button>
          </div>

          {/* Timeframe Selectors */}
          <div className="flex items-center gap-1 bg-bg-elevated p-0.5 rounded-lg border border-border">
            {['1M', '3M', '6M', '1Y', 'ALL'].map(tf => (
              <button
                key={tf}
                onClick={() => setActiveTimeframe(tf)}
                className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${
                  activeTimeframe === tf
                    ? 'bg-brand-500 text-white shadow-sm'
                    : 'text-fg-muted hover:text-fg hover:bg-bg-card'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Lightweight Charts Canvas Container */}
      <div ref={chartContainerRef} className="w-full flex-1 min-h-[350px] mt-2 relative" />

      {/* Legend footer */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-2 text-[11px] text-fg-subtle border-t border-border/50 mt-1">
        <div className="flex items-center gap-4">
          {enableEMAs && (
            <>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 rounded bg-[#2DD4BF]" />
                <span>EMA 20</span>
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-0.5 rounded bg-[#F59E0B]" />
                <span>EMA 50</span>
              </span>
            </>
          )}
          {enableVolume && (
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-brand-500/40" />
              <span>Volume Flow</span>
            </span>
          )}
          {enablePatterns && visiblePatterns.length > 0 && (
            <span className="flex items-center gap-1.5 text-brand-600 dark:text-brand-400">
              <Sparkles className="w-3 h-3" />
              <span>{visiblePatterns.length} Pattern Formations Active</span>
            </span>
          )}
        </div>

        {enablePatterns && (
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1 text-bull">
              <span className="w-2 h-2 rounded-full bg-bull" /> Bullish Reversal
            </span>
            <span className="flex items-center gap-1 text-bear">
              <span className="w-2 h-2 rounded-full bg-bear" /> Bearish Reversal
            </span>
            <span className="flex items-center gap-1 text-amber-500">
              <span className="w-2 h-2 rounded-full bg-amber-500" /> Neutral / Doji
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
