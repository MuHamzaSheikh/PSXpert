import React from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';

export const WatchlistPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">Watchlist & Alerts</h1>
          <p className="text-sm text-fg-muted">Custom equity tracking, price thresholds, and technical triggers</p>
        </div>
        <DemoBadge label="LocalStore Watchlist" />
      </div>
      <Card className="p-8 text-center text-fg-muted">
        Watchlist interface building in Milestone 7...
      </Card>
    </div>
  );
};
