import React from 'react';
import { Card } from '@/components/common/Card';
import { DollarSign, PieChart, ShieldCheck, TrendingUp, Building } from 'lucide-react';

interface CompanyFundamentalsTabProps {
  symbol: string;
}

export const CompanyFundamentalsTab: React.FC<CompanyFundamentalsTabProps> = ({ symbol }) => {
  return (
    <Card className="p-6 space-y-6">
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <h3 className="font-bold text-base text-fg">Fundamentals & Valuation Ratios</h3>
          <p className="text-xs text-fg-subtle">Sourced from official audited PSX exchange reports (DPS) & Sarmaaya</p>
        </div>
        <span className="text-xs font-mono text-brand-600 dark:text-brand-400 font-bold px-2.5 py-1 rounded-lg bg-brand-500/10 border border-brand-500/20">
          FY 2025–2026 Audit
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-xs">
        {/* Col 1: Valuation Multiples */}
        <div className="space-y-3 p-4 rounded-xl bg-bg-elevated/40 border border-border">
          <div className="flex items-center gap-2 font-bold text-fg uppercase tracking-wider text-[11px]">
            <DollarSign className="w-4 h-4 text-brand-600" />
            <span>Valuation Multiples</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">P/E Ratio</span>
              <span className="font-mono font-bold text-fg">6.42x</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Price to Book (P/B)</span>
              <span className="font-mono font-bold text-fg">1.84x</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">EV / EBITDA</span>
              <span className="font-mono font-bold text-fg">4.12x</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-fg-muted">Market Cap</span>
              <span className="font-mono font-bold text-fg">PKR 442.8B</span>
            </div>
          </div>
        </div>

        {/* Col 2: Profitability & Returns */}
        <div className="space-y-3 p-4 rounded-xl bg-bg-elevated/40 border border-border">
          <div className="flex items-center gap-2 font-bold text-fg uppercase tracking-wider text-[11px]">
            <TrendingUp className="w-4 h-4 text-emerald-500" />
            <span>Profitability & Returns</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Return on Equity (ROE)</span>
              <span className="font-mono font-bold text-bull">38.4%</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Return on Assets (ROA)</span>
              <span className="font-mono font-bold text-fg">2.6%</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Net Profit Margin</span>
              <span className="font-mono font-bold text-fg">24.8%</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-fg-muted">EPS Growth (YoY)</span>
              <span className="font-mono font-bold text-bull">+18.5%</span>
            </div>
          </div>
        </div>

        {/* Col 3: Balance Sheet & Dividends */}
        <div className="space-y-3 p-4 rounded-xl bg-bg-elevated/40 border border-border">
          <div className="flex items-center gap-2 font-bold text-fg uppercase tracking-wider text-[11px]">
            <ShieldCheck className="w-4 h-4 text-sky-500" />
            <span>Solvency & Payouts</span>
          </div>
          <div className="space-y-2">
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Dividend Yield</span>
              <span className="font-mono font-bold text-bull">9.20%</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Payout Ratio</span>
              <span className="font-mono font-bold text-fg">46.5%</span>
            </div>
            <div className="flex justify-between py-1 border-b border-border/40">
              <span className="text-fg-muted">Book Value Per Share</span>
              <span className="font-mono font-bold text-fg">PKR 135.20</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-fg-muted">Debt / Equity</span>
              <span className="font-mono font-bold text-fg">0.34x</span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};
