import React, { useEffect, useRef, useState, useMemo } from 'react';
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  ColorType,
  IChartApi,
  ISeriesApi,
  Time,
} from 'lightweight-charts';
import { useTheme } from '@/context/ThemeContext';
import { Candle, Pattern } from '@/types';
import { Sparkles, Eye, EyeOff } from 'lucide-react';

interface TradingViewChartProps {
  candles: Candle[];
  patterns?: Pattern[];
  selectedDate?: string | null;
  symbol?: string;
  height?: number;
  showVolume?: boolean;
  showEMAs?: boolean;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  candles,
  patterns = [],
  selectedDate = null,
  symbol = 'KSE100',
  height = 420,
  showVolume = true,
  showEMAs = true,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);

  const { theme } = useTheme();
  const [activeTimeframe, setActiveTimeframe] = useState('ALL');
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);
  const [showPatternMarkers, setShowPatternMarkers] = useState(false);

  const isDark = theme === 'dark';

  // Filter candles based on active timeframe
  const filteredCandles = useMemo(() => {
    if (!candles || candles.length === 0) return [];
    if (activeTimeframe === 'ALL') return candles;

    const countMap: Record<string, number> = {
      '1D': 1,
      '5D': 5,
      '1M': 22,
      '3M': 66,
      '6M': 130,
      '1Y': 252,
    };
    const count = countMap[activeTimeframe] || candles.length;
    return candles.slice(-count);
  }, [candles, activeTimeframe]);

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
        fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
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
          top: 0.12,
          bottom: showVolume ? 0.22 : 0.1,
        },
      },
      timeScale: {
        borderColor: isDark ? '#22363B' : '#E2E8F0',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    chartRef.current = chart;

    // 1. Candlestick series with authentic Green / Red styling
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#287A50',
      downColor: '#C64C4C',
      borderVisible: true,
      borderColor: '#287A50',
      borderUpColor: '#287A50',
      borderDownColor: '#C64C4C',
      wickUpColor: '#287A50',
      wickDownColor: '#C64C4C',
    });
    candleSeriesRef.current = candleSeries;

    // 2. Volume series
    let volumeSeries: ISeriesApi<'Histogram'> | null = null;
    if (showVolume) {
      volumeSeries = chart.addSeries(HistogramSeries, {
        color: '#2F7D68',
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
    if (showEMAs) {
      ema20Series = chart.addSeries(LineSeries, {
        color: '#2F7D68', // Deep Jade EMA 20
        lineWidth: 2,
        title: 'EMA 20',
      });
      ema50Series = chart.addSeries(LineSeries, {
        color: '#E67E22', // Amber-Orange EMA 50
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
          color: c.close >= c.open ? 'rgba(16, 185, 129, 0.45)' : 'rgba(244, 63, 94, 0.45)',
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

      // Attach Candlestick Pattern Markers directly on chart bars
      if (showPatternMarkers && patterns && patterns.length > 0) {
        const candleDates = new Set(filteredCandles.map(c => c.time));
        const activePatterns = patterns.filter(p => candleDates.has(p.date));
        // Show text label on the 8 most recent patterns to keep chart readable, shapes on others
        const recentDatesWithText = new Set(activePatterns.slice(-8).map(p => p.date));

        const patternMarkers = activePatterns.map(p => {
          const isBull = p.type === 'BULLISH';
          const isBear = p.type === 'BEARISH';
          const hasLabel = recentDatesWithText.has(p.date);
          return {
            time: p.date as Time,
            position: (isBull ? 'belowBar' : 'aboveBar') as any,
            color: isBull ? '#10B981' : isBear ? '#F43F5E' : '#EAB308',
            shape: (isBull ? 'arrowUp' : isBear ? 'arrowDown' : 'circle') as any,
            text: hasLabel ? p.name : '',
          };
        });

        if (patternMarkers.length > 0) {
          try {
            createSeriesMarkers(candleSeries, patternMarkers);
          } catch (e) {
            console.warn('Failed to set pattern markers:', e);
          }
        }
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
  }, [filteredCandles, patterns, showPatternMarkers, isDark, height, showVolume, showEMAs]);

  // Handle focus when a pattern is clicked in the list
  useEffect(() => {
    if (selectedDate && chartRef.current && filteredCandles.length > 0) {
      const idx = filteredCandles.findIndex(c => c.time === selectedDate);
      if (idx !== -1) {
        setHoveredCandle(filteredCandles[idx]);
        const start = Math.max(0, idx - 15);
        const end = Math.min(filteredCandles.length - 1, idx + 15);
        try {
          chartRef.current.timeScale().setVisibleRange({
            from: filteredCandles[start].time as Time,
            to: filteredCandles[end].time as Time,
          });
        } catch {
          // Fallback if range fails
          chartRef.current.timeScale().fitContent();
        }
      }
    }
  }, [selectedDate, filteredCandles]);

  const latest = hoveredCandle || filteredCandles[filteredCandles.length - 1] || null;

  return (
    <div className="flex flex-col w-full h-full">
      {/* Chart HUD & Control Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 text-xs">
        {/* Left: Interactive Price HUD */}
        {latest ? (
          <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1 font-mono text-[11px] sm:text-xs">
            <span className="text-[#77736C] dark:text-[#9E988E] font-sans text-xs">{latest.time}</span>
            <span>
              <span className="text-[#77736C] dark:text-[#9E988E] mr-1">O:</span>
              <strong className="text-[#252A2B] dark:text-[#F4EFE6]">{latest.open?.toLocaleString()}</strong>
            </span>
            <span>
              <span className="text-[#77736C] dark:text-[#9E988E] mr-1">H:</span>
              <strong className="text-[#287A50] dark:text-[#34A86E]">{latest.high?.toLocaleString()}</strong>
            </span>
            <span>
              <span className="text-[#77736C] dark:text-[#9E988E] mr-1">L:</span>
              <strong className="text-[#C64C4C] dark:text-[#E05C5C]">{latest.low?.toLocaleString()}</strong>
            </span>
            <span>
              <span className="text-[#77736C] dark:text-[#9E988E] mr-1">C:</span>
              <strong className={latest.close >= latest.open ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#C64C4C] dark:text-[#E05C5C]'}>
                {latest.close?.toLocaleString()}
              </strong>
            </span>
            <span className="hidden sm:inline">
              <span className="text-[#77736C] dark:text-[#9E988E] mr-1">Vol:</span>
              <strong className="text-[#252A2B] dark:text-[#F4EFE6]">
                {(latest.volume / 1000000).toFixed(2)}M
              </strong>
            </span>
            {latest.pattern && (
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-[#C47C4F]/15 text-[#C47C4F] border border-[#C47C4F]/30">
                ★ {latest.pattern}
              </span>
            )}
          </div>
        ) : (
          <div className="text-[#77736C]">Loading chart telemetry...</div>
        )}

        {/* Right: Pattern Toggle & Timeframe Selectors */}
        <div className="flex items-center gap-2">
          {/* Pattern Toggle Button */}
          {patterns && patterns.length > 0 && (
            <button
              onClick={() => setShowPatternMarkers(!showPatternMarkers)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border transition-all ${
                showPatternMarkers
                  ? 'bg-[#694E7A]/15 text-[#694E7A] dark:text-[#A888BF] border-[#694E7A]/30'
                  : 'bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#252A2B] dark:text-[#F4EFE6] border-[#DDD5C9] hover:bg-[#FFFCF6]'
              }`}
              title="Toggle candlestick pattern markers on the chart"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Patterns ({patterns.length})</span>
              {showPatternMarkers ? <Eye className="w-3 h-3 ml-0.5" /> : <EyeOff className="w-3 h-3 ml-0.5" />}
            </button>
          )}

          {/* Timeframe Selectors */}
          <div className="flex items-center gap-0.5 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 p-0.5 rounded-full border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20 shadow-sm">
            {['1M', '3M', '6M', '1Y', 'ALL'].map(tf => (
              <button
                key={tf}
                onClick={() => setActiveTimeframe(tf)}
                className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold transition-all ${
                  activeTimeframe === tf
                    ? 'bg-[#2F7D68] text-white shadow-sm'
                    : 'text-[#77736C] dark:text-[#9E988E] hover:text-[#252A2B] dark:hover:text-[#F4EFE6]'
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
      <div className="flex flex-wrap items-center justify-between gap-3 pt-2 text-[11px] text-fg-subtle border-t border-border/50">
        <div className="flex items-center gap-4">
          {showEMAs && (
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
          {showVolume && (
            <span className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm bg-brand-500/40" />
              <span>Volume Flow</span>
            </span>
          )}
        </div>

        {showPatternMarkers && patterns && patterns.length > 0 && (
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1">
              <span className="text-bull font-bold">▲</span> Bullish Marker
            </span>
            <span className="flex items-center gap-1">
              <span className="text-bear font-bold">▼</span> Bearish Marker
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
