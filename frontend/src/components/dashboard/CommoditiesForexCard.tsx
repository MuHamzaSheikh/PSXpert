import React from 'react';
import { Card } from '@/components/common/Card';
import { Coins, ArrowUpRight, ArrowDownRight, Globe } from 'lucide-react';
import { MOCK_COMMODITIES } from '@/api/mockData';

export const CommoditiesForexCard: React.FC = () => {
  return (
    <Card className="p-5 space-y-4">
      <div className="flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Coins className="w-4 h-4 text-brand-600 dark:text-brand-400" />
          <span className="font-semibold text-sm text-fg">Forex & Commodities</span>
        </div>
        <span className="text-[11px] font-mono text-fg-subtle">Pakistan Benchmark</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {MOCK_COMMODITIES.map(item => (
          <div
            key={item.name}
            className="p-3 rounded-xl bg-bg-elevated/60 border border-border/80 flex flex-col justify-between space-y-1 hover:border-brand-500/40 transition-colors"
          >
            <div className="text-[11px] text-fg-muted font-medium line-clamp-1">{item.name}</div>
            <div className="text-base font-bold font-mono text-fg">{item.rate}</div>
            <div className={`flex items-center gap-0.5 text-xs font-mono font-semibold ${item.isUp ? 'text-bull' : 'text-bear'}`}>
              {item.isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              <span>{item.change}</span>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
};
