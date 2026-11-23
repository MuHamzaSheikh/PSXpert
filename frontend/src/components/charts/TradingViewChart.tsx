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
} from 'lightweight-charts';
import { useTheme } from '@/context/ThemeContext';
import { Candle } from '@/types';

interface TradingViewChartProps {
  candles: Candle[];
  symbol?: string;
  height?: number;
  showVolume?: boolean;
  showEMAs?: boolean;
}

export const TradingViewChart: React.FC<TradingViewChartProps> = ({
  candles,
  symbol = 'KSE100',
  height = 420,
  showVolume = true,
  showEMAs = true,
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  const { theme } = useTheme();
  const [activeTimeframe, setActiveTimeframe] = useState('6M');
  const [hoveredCandle, setHoveredCandle] = useState<Candle | null>(null);

  const isDark = theme === 'dark';

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
    if (showVolume) {
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
    if (showEMAs) {
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
    if (candles && candles.length > 0) {
      const formattedCandles = candles.map(c => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      }));
      candleSeries.setData(formattedCandles);

      if (volumeSeries) {
        const volumeData = candles.map(c => ({
          time: c.time as Time,
          value: c.volume,
          color: c.close >= c.open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
        }));
        volumeSeries.setData(volumeData);
      }

      if (ema20Series) {
        const ema20Data = candles
          .filter(c => c.ema20 !== undefined && c.ema20 !== null)
          .map(c => ({ time: c.time as Time, value: c.ema20 as number }));
        ema20Series.setData(ema20Data);
      }

      if (ema50Series) {
        const ema50Data = candles
          .filter(c => c.ema50 !== undefined && c.ema50 !== null)
          .map(c => ({ time: c.time as Time, value: c.ema50 as number }));
        ema50Series.setData(ema50Data);
      }

      chart.timeScale().fitContent();
      setHoveredCandle(candles[candles.length - 1]);
    }

    // Crosshair move listener for HUD
    chart.subscribeCrosshairMove(param => {
      if (!param || !param.time || !param.seriesData) {
        if (candles.length > 0) setHoveredCandle(candles[candles.length - 1]);
        return;
      }
      const data = param.seriesData.get(candleSeries);
      if (data) {
        const match = candles.find(c => c.time === (param.time as string));
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
  }, [candles, isDark, height, showVolume, showEMAs]);

  const latest = hoveredCandle || candles[candles.length - 1] || null;

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

        {/* Right: Timeframe Selectors */}
        <div className="flex items-center gap-1 bg-bg-elevated p-0.5 rounded-lg border border-border">
          {['1D', '5D', '1M', '3M', '6M', '1Y', 'ALL'].map(tf => (
            <button
              key={tf}
              onClick={() => setActiveTimeframe(tf)}
              className={`px-2 py-0.5 rounded text-[11px] font-semibold transition-colors ${activeTimeframe === tf
                ? 'bg-brand-500 text-white shadow-sm'
                : 'text-fg-muted hover:text-fg hover:bg-bg-card'
                }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Main Lightweight Charts Canvas Container */}
      <div ref={chartContainerRef} className="w-full flex-1 min-h-[350px] mt-2 relative" />

      {/* Legend footer */}
      {showEMAs && (
        <div className="flex items-center gap-4 pt-2 text-[11px] text-fg-subtle">
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 rounded bg-[#2DD4BF]" />
            <span>EMA 20</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-0.5 rounded bg-[#F59E0B]" />
            <span>EMA 50</span>
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-sm bg-brand-500/40" />
            <span>Volume Flow</span>
          </span>
        </div>
      )}
    </div>
  );
};
