import React from 'react';
import { Card } from '@/components/common/Card';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { useTheme } from '@/context/ThemeContext';

export const SettingsPage: React.FC = () => {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-fg">Settings & Preferences</h1>
        <p className="text-sm text-fg-muted">Customize platform appearance, trading parameters, and data sources</p>
      </div>

      <Card className="p-6 space-y-6">
        <div>
          <h2 className="text-base font-semibold text-fg">Appearance</h2>
          <p className="text-xs text-fg-muted">Choose between light and dark modes</p>
        </div>

        <div className="flex items-center justify-between p-4 rounded-xl border border-border bg-bg-elevated/50">
          <div>
            <div className="font-semibold text-sm text-fg">Color Theme</div>
            <div className="text-xs text-fg-muted">Current: <span className="capitalize font-mono font-bold text-brand-600 dark:text-brand-400">{theme}</span></div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setTheme('light')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${theme === 'light' ? 'bg-brand-500 text-white border-brand-500' : 'bg-bg-card border-border text-fg-muted'}`}
            >
              Light
            </button>
            <button
              onClick={() => setTheme('dark')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border ${theme === 'dark' ? 'bg-brand-500 text-white border-brand-500' : 'bg-bg-card border-border text-fg-muted'}`}
            >
              Dark
            </button>
          </div>
        </div>
      </Card>
    </div>
  );
};
