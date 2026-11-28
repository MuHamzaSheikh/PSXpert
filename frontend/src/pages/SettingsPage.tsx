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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#252A2B] dark:text-[#F4EFE6]">
            Settings &amp; Research Preferences
          </h1>
          <p className="text-xs sm:text-sm text-[#77736C] dark:text-[#9E988E] mt-1">
            Configure terminal theme, risk parameters, alert thresholds, and backend endpoints.
          </p>
        </div>

        {savedSuccess && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#287A50]/15 text-[#287A50] border border-[#287A50]/30 text-xs font-bold animate-in fade-in duration-150 shadow-sm">
            <CheckCircle2 className="w-4 h-4" />
            <span>Preferences Saved</span>
          </div>
        )}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Appearance Card */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
            <Sun className="w-4 h-4 text-amber-500" />
            <h2 className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Appearance &amp; Theme</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div
              onClick={() => setTheme('light')}
              className={`p-4 rounded-2xl border cursor-pointer transition-all flex items-center justify-between ${
                theme === 'light'
                  ? 'border-[#694E7A] bg-[#694E7A]/10 shadow-sm'
                  : 'border-[#DDD5C9] bg-[#FFFCF6]/80 hover:bg-[#FFFCF6]'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-amber-400/20 text-amber-600 flex items-center justify-center">
                  <Sun className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-bold text-xs text-[#252A2B] dark:text-[#F4EFE6]">Warm Glassmorphism Ivory</div>
                  <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">Soft parchment canvas &amp; amber warmth</div>
                </div>
              </div>
              {theme === 'light' && <CheckCircle2 className="w-4 h-4 text-[#694E7A]" />}
            </div>

            <div
              onClick={() => setTheme('dark')}
              className={`p-4 rounded-2xl border cursor-pointer transition-all flex items-center justify-between ${
                theme === 'dark'
                  ? 'border-[#2F7D68] bg-[#2F7D68]/15 shadow-sm'
                  : 'border-[#DDD5C9] bg-[#FFFCF6]/80 hover:bg-[#FFFCF6]'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-[#2F7D68]/20 text-[#3DA88D] flex items-center justify-center">
                  <Moon className="w-5 h-5" />
                </div>
                <div>
                  <div className="font-bold text-xs text-[#252A2B] dark:text-[#F4EFE6]">Trading Terminal Dark</div>
                  <div className="text-[11px] text-[#77736C] dark:text-[#9E988E]">High-contrast obsidian glass surfaces</div>
                </div>
              </div>
              {theme === 'dark' && <CheckCircle2 className="w-4 h-4 text-[#2F7D68]" />}
            </div>
          </div>
        </Card>

        {/* Risk & Model Calibration Profile */}
        <Card className="p-6 space-y-5">
          <div className="flex items-center gap-2 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
            <Shield className="w-4 h-4 text-[#2F7D68]" />
            <h2 className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Risk Tolerance &amp; Agent Sensitivity</h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {(['conservative', 'balanced', 'aggressive'] as const).map(prof => (
              <div
                key={prof}
                onClick={() => setRiskProfile(prof)}
                className={`p-4 rounded-2xl border cursor-pointer transition-all space-y-1 ${
                  riskProfile === prof
                    ? 'border-[#694E7A] bg-[#694E7A]/10 shadow-sm'
                    : 'border-[#DDD5C9] bg-[#FFFCF6]/80 hover:bg-[#FFFCF6]'
                }`}
              >
                <div className="font-bold text-xs capitalize text-[#252A2B] dark:text-[#F4EFE6]">{prof}</div>
                <div className="text-[11px] text-[#77736C] dark:text-[#9E988E] leading-tight">
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
          <div className="flex items-center gap-2 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
            <Bell className="w-4 h-4 text-[#694E7A]" />
            <h2 className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">Notifications &amp; Signals</h2>
          </div>

          <div className="space-y-3 text-xs">
            <label className="flex items-center justify-between p-3.5 rounded-2xl border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 cursor-pointer transition-all hover:bg-[#FFFCF6]">
              <div>
                <span className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Technical Price &amp; RSI Alerts</span>
                <p className="text-[#77736C] dark:text-[#9E988E] text-[11px]">Notify when a watchlisted stock crosses RSI 70 (Overbought) or 30 (Oversold).</p>
              </div>
              <input
                type="checkbox"
                checked={notifyPriceAlerts}
                onChange={e => setNotifyPriceAlerts(e.target.checked)}
                className="w-4 h-4 text-[#2F7D68] rounded accent-[#2F7D68]"
              />
            </label>

            <label className="flex items-center justify-between p-3.5 rounded-2xl border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 cursor-pointer transition-all hover:bg-[#FFFCF6]">
              <div>
                <span className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">High-Impact FinBERT News Alerts</span>
                <p className="text-[#77736C] dark:text-[#9E988E] text-[11px]">Notify when an article with confidence &gt; 90% affects a portfolio holding.</p>
              </div>
              <input
                type="checkbox"
                checked={notifySentimentAlerts}
                onChange={e => setNotifySentimentAlerts(e.target.checked)}
                className="w-4 h-4 text-[#2F7D68] rounded accent-[#2F7D68]"
              />
            </label>

            <label className="flex items-center justify-between p-3.5 rounded-2xl border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 cursor-pointer transition-all hover:bg-[#FFFCF6]">
              <div>
                <span className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Corporate Dividend Disclosures</span>
                <p className="text-[#77736C] dark:text-[#9E988E] text-[11px]">Notify immediately upon official PSX board meeting announcements and dividend payouts.</p>
              </div>
              <input
                type="checkbox"
                checked={notifyAnnouncements}
                onChange={e => setNotifyAnnouncements(e.target.checked)}
                className="w-4 h-4 text-[#2F7D68] rounded accent-[#2F7D68]"
              />
            </label>
          </div>
        </Card>

        {/* Backend Endpoint Settings */}
        <Card className="p-6 space-y-4">
          <div className="flex items-center gap-2 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-3">
            <Server className="w-4 h-4 text-[#2F7D68]" />
            <h2 className="font-bold text-sm text-[#252A2B] dark:text-[#F4EFE6]">FastAPI Backend Connection</h2>
          </div>

          <div className="space-y-1.5 text-xs">
            <label className="font-semibold text-[#252A2B] dark:text-[#F4EFE6]">Backend Host URL</label>
            <input
              type="text"
              value={apiHost}
              onChange={e => setApiHost(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-full border border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 text-[#252A2B] dark:text-[#F4EFE6] font-mono outline-none focus:border-[#2F7D68]"
            />
            <p className="text-[11px] text-[#77736C] dark:text-[#9E988E]">
              Defaults to <code>http://127.0.0.1:8000</code> via the Vite dev proxy.
            </p>
          </div>
        </Card>

        {/* Save Button */}
        <div className="flex justify-end">
          <button
            type="submit"
            className="flex items-center gap-1.5 px-6 py-2.5 rounded-full bg-gradient-to-r from-[#2F7D68] to-[#236353] hover:from-[#236353] hover:to-[#1a4d40] text-white font-bold text-xs shadow-md shadow-[#2F7D68]/20 transition-all"
          >
            <Save className="w-4 h-4" />
            <span>Save Preferences</span>
          </button>
        </div>
      </form>
    </div>
  );
};
