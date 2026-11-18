import React from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';

export const PortfolioPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">Portfolio Manager</h1>
          <p className="text-sm text-fg-muted">PSX equity holdings, sector allocation, P&L, and risk metrics</p>
        </div>
        <DemoBadge label="Client LocalStore" />
      </div>
      <Card className="p-8 text-center text-fg-muted">
        Portfolio interface building in Milestone 4...
      </Card>
    </div>
  );
};
