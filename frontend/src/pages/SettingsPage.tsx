import React, { useState } from 'react';
import { Card } from '@/components/common/Card';
import { useTheme } from '@/context/ThemeContext';
import {
  Settings,
  Sun,
  Moon,
  Bell,
  Sliders,
  Shield,
  Server,
  Save,
  CheckCircle2,
  RefreshCw,
} from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { theme, setTheme } = useTheme();

  // Settings State
  const [apiHost, setApiHost] = useState('http://127.0.0.1:8000');
  const [riskProfile, setRiskProfile] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [notifyPriceAlerts, setNotifyPriceAlerts] = useState(true);
  const [notifySentimentAlerts, setNotifySentimentAlerts] = useState(true);
  const [notifyAnnouncements, setNotifyAnnouncements] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    localStorage.setItem('psxpert_api_host', apiHost);
    localStorage.setItem('psxpert_risk_profile', riskProfile);
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-in fade-in duration-300">
      {/* 1. Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-fg">
            Settings & Research Preferences
          </h1>
          <p className="text-xs sm:text-sm text-fg-muted mt-1">
            Configure terminal theme, risk parameters, alert thresholds, and backend endpoints.
          </p>
        </div>

        {savedSuccess && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-bull-bg text-bull border border-bull/30 text-xs font-bold animate-in fade-in duration-150">
            <CheckCircle2 className="w-4 h-4" />
            <span>Preferences Saved</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Appearance Card */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Sun className="w-4 h-4 text-amber-500" />
            <h2 className="font-bold text-sm text-fg">Appearance & Theme</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div
              onClick={() => setTheme('light')}
              className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                theme === 'light'
                  ? 'border-brand-500 bg-brand-500/10 shadow-sm'
                  : 'border-border bg-bg-card hover:bg-bg-elevated'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-amber-400/20 text-amber-600 flex items-center justify-center">
                  <Sun className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-bold text-xs text-fg">Clean Light Theme</div>
                  <div className="text-[11px] text-fg-subtle">Investify-inspired off-white canvas</div>
                </div>
              </div>
              {theme === 'light' && <CheckCircle2 className="w-4 h-4 text-brand-600" />}
            </div>

            <div
              onClick={() => setTheme('dark')}
              className={`p-4 rounded-xl border cursor-pointer transition-all flex items-center justify-between ${
                theme === 'dark'
                  ? 'border-brand-500 bg-brand-500/10 shadow-sm'
                  : 'border-border bg-bg-card hover:bg-bg-elevated'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-brand-900/40 text-brand-400 flex items-center justify-center">
                  <Moon className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-bold text-xs text-fg">Trading Terminal Dark</div>
                  <div className="text-[11px] text-fg-subtle">High-contrast deep teal surfaces</div>
                </div>
              </div>
              {theme === 'dark' && <CheckCircle2 className="w-4 h-4 text-brand-400" />}
            </div>
          </div>
        </Card>

        {/* Risk & Model Calibration Profile */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Shield className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <h2 className="font-bold text-sm text-fg">Risk Tolerance & Agent Sensitivity</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(['conservative', 'balanced', 'aggressive'] as const).map(prof => (
              <div
                key={prof}
                onClick={() => setRiskProfile(prof)}
                className={`p-4 rounded-xl border cursor-pointer transition-all space-y-1 ${
                  riskProfile === prof
                    ? 'border-brand-500 bg-brand-500/10'
                    : 'border-border bg-bg-card hover:bg-bg-elevated'
                }`}
              >
                <div className="font-bold text-xs capitalize text-fg">{prof}</div>
                <div className="text-[11px] text-fg-subtle leading-tight">
                  {prof === 'conservative'
                    ? 'Emphasizes low beta, dividend yield, and capital preservation.'
                    : prof === 'balanced'
                    ? 'Balanced blend of technical momentum and fundamental value.'
                    : 'Aggressive multi-factor weighting seeking high-beta breakouts.'}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Notification & Telemetry Alerts */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Bell className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <h2 className="font-bold text-sm text-fg">Notifications & Signals</h2>
          </div>

          <div className="space-y-3 text-xs">
            <label className="flex items-center justify-between p-3 rounded-xl border border-border bg-bg-elevated/40 cursor-pointer">
              <div>
                <span className="font-semibold text-fg">Technical Price & RSI Alerts</span>
                <p className="text-fg-subtle text-[11px]">Notify when a watchlisted stock crosses RSI 70 (Overbought) or 30 (Oversold).</p>
              </div>
              <input
                type="checkbox"
                checked={notifyPriceAlerts}
                onChange={e => setNotifyPriceAlerts(e.target.checked)}
                className="w-4 h-4 text-brand-600 rounded"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded-xl border border-border bg-bg-elevated/40 cursor-pointer">
              <div>
                <span className="font-semibold text-fg">High-Impact FinBERT News Alerts</span>
                <p className="text-fg-subtle text-[11px]">Notify when an article with confidence &gt; 90% affects a portfolio holding.</p>
              </div>
              <input
                type="checkbox"
                checked={notifySentimentAlerts}
                onChange={e => setNotifySentimentAlerts(e.target.checked)}
                className="w-4 h-4 text-brand-600 rounded"
              />
            </label>

            <label className="flex items-center justify-between p-3 rounded-xl border border-border bg-bg-elevated/40 cursor-pointer">
              <div>
                <span className="font-semibold text-fg">Corporate Dividend Disclosures</span>
                <p className="text-fg-subtle text-[11px]">Notify immediately upon official PSX board meeting announcements and dividend payouts.</p>
              </div>
              <input
                type="checkbox"
                checked={notifyAnnouncements}
                onChange={e => setNotifyAnnouncements(e.target.checked)}
                className="w-4 h-4 text-brand-600 rounded"
              />
            </label>
          </div>
        </Card>

        {/* Backend Endpoint Settings */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-border pb-3">
            <Server className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <h2 className="font-bold text-sm text-fg">FastAPI Backend Connection</h2>
          </div>

          <div className="space-y-1.5 text-xs">
            <label className="font-semibold text-fg">Backend Host URL</label>
            <input
              type="text"
              value={apiHost}
              onChange={e => setApiHost(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-border bg-bg text-fg font-mono outline-none focus:border-brand-500"
            />
            <p className="text-[11px] text-fg-subtle">
              Defaults to <code>http://127.0.0.1:8000</code> via the Vite dev proxy.
            </p>
          </div>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            className="flex items-center gap-1.5 px-6 py-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs shadow-sm transition-all"
          >
            <Save className="w-4 h-4" />
            <span>Save Preferences</span>
          </button>
        </div>
      </form>
    </div>
  );
};
