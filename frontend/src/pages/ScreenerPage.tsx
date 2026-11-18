import React from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';

export const ScreenerPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">AI Stock Screener</h1>
          <p className="text-sm text-fg-muted">Multi-factor technical, fundamental, and AI confidence filters</p>
        </div>
        <DemoBadge label="Screener Engine" />
      </div>
      <Card className="p-8 text-center text-fg-muted">
        Stock Screener interface building in Milestone 2...
      </Card>
    </div>
  );
};
