import React from 'react';
import { Link } from 'react-router-dom';
import { TrendingUp, ShieldAlert, ExternalLink, Code2, Database, Cpu } from 'lucide-react';

export const Footer: React.FC = () => {
  return (
    <footer className="mt-auto border-t border-border bg-bg-card text-fg-muted text-xs">
      {/* Upper Legal & Diagnostic Notice */}
      <div className="border-b border-border bg-bg-elevated/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex flex-col sm:flex-row items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-bold text-fg text-xs uppercase tracking-wider">
                Regulatory Diagnostic & Analytical Disclaimer
              </span>
              <p className="leading-relaxed text-fg-muted text-[11px]">
                PSXpert is an academic and quantitative research platform developed for the Pakistan Stock Exchange (PSX). Technical indicators (RSI, MACD, Bollinger Bands, ATR, ADX, OBV, Stochastics, Moving Averages), candlestick pattern recognitions, HMM market regime detections, and FinBERT multi-agent AI syntheses are <strong>strictly analytical diagnostic tools</strong>. They do <strong>not</strong> constitute guaranteed buy or sell signals, investment advice, portfolio management mandates, or financial recommendations under SECP regulations. Capital investments in equity markets are subject to substantial market risks. Always conduct independent due diligence or consult a licensed broker before trading.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Footer Links */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8">
          {/* Brand Col */}
          <div className="col-span-2 space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold">
                <TrendingUp className="w-4 h-4 stroke-[2.5]" />
              </div>
              <span className="font-extrabold text-base tracking-tight text-fg">PSXpert</span>
            </div>
            <p className="text-fg-subtle text-xs leading-relaxed max-w-sm">
              Next-generation multi-agent equity intelligence platform for the Pakistan Stock Exchange (PSX), integrating historical datasets, transformer sentiment, and quantitative diagnostics.
            </p>
            <div className="flex items-center gap-3 pt-1 text-fg-subtle">
              <span className="inline-flex items-center gap-1">
                <Database className="w-3.5 h-3.5 text-brand-600" />
                <span>2002–2026 Datasets</span>
              </span>
              <span>•</span>
              <span className="inline-flex items-center gap-1">
                <Cpu className="w-3.5 h-3.5 text-brand-600" />
                <span>FinBERT AI</span>
              </span>
            </div>
          </div>

          {/* Col 1: Platform */}
          <div className="space-y-2">
            <span className="font-semibold text-fg text-xs uppercase tracking-wider">Platform</span>
            <ul className="space-y-1.5 text-fg-muted">
              <li><Link to="/" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">Market Dashboard</Link></li>
              <li><Link to="/screener" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">AI Stock Screener</Link></li>
              <li><Link to="/analysis/KSE100" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">KSE-100 Technicals</Link></li>
              <li><Link to="/analysis/MEBL" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">Stock Diagnostics</Link></li>
              <li><Link to="/portfolio" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">Portfolio Manager</Link></li>
            </ul>
          </div>

          {/* Col 2: AI & Analytics */}
          <div className="space-y-2">
            <span className="font-semibold text-fg text-xs uppercase tracking-wider">AI & Quantitative</span>
            <ul className="space-y-1.5 text-fg-muted">
              <li><Link to="/assistant" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">Research Assistant</Link></li>
              <li><Link to="/insights" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">FinBERT News Feed</Link></li>
              <li><Link to="/insights#announcements" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">PSX Filings & Payouts</Link></li>
              <li><Link to="/analysis/OGDC" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">HMM Regimes & GA</Link></li>
              <li><Link to="/watchlist" className="hover:text-brand-600 dark:hover:text-brand-400 transition-colors">Watchlist & Alerts</Link></li>
            </ul>
          </div>

          {/* Col 3: Data Provenance */}
          <div className="space-y-2">
            <span className="font-semibold text-fg text-xs uppercase tracking-wider">Data Provenance</span>
            <ul className="space-y-1.5 text-fg-muted">
              <li>
                <a href="https://dps.psx.com.pk/" target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-brand-600 dark:hover:text-brand-400">
                  <span>PSX Data Portal</span>
                  <ExternalLink className="w-3 h-3 text-fg-subtle" />
                </a>
              </li>
              <li>
                <a href="https://sarmaaya.pk/" target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-brand-600 dark:hover:text-brand-400">
                  <span>Sarmaaya Financials</span>
                  <ExternalLink className="w-3 h-3 text-fg-subtle" />
                </a>
              </li>
              <li>
                <a href="https://www.sbp.org.pk/" target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-brand-600 dark:hover:text-brand-400">
                  <span>State Bank of Pakistan</span>
                  <ExternalLink className="w-3 h-3 text-fg-subtle" />
                </a>
              </li>
              <li>
                <a href="https://github.com/MuHamzaSheikh/PSXpert" target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-brand-600 dark:hover:text-brand-400">
                  <Code2 className="w-3 h-3" />
                  <span>GitHub Repository</span>
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom Sub-bar */}
        <div className="mt-8 pt-6 border-t border-border flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-fg-subtle">
          <div>
            © {new Date().getFullYear()} PSXpert. Built for academic Final Year Project (FYP) research on the Pakistan Stock Exchange.
          </div>
          <div className="flex items-center gap-4">
            <span>Branch: <code className="font-mono text-brand-600 dark:text-brand-400">frontend/ui-design</code></span>
            <span>•</span>
            <span>FastAPI Backend Proxy on <code>:8000</code></span>
          </div>
        </div>
      </div>
    </footer>
  );
};
