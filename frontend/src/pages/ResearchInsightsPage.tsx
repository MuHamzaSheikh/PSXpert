import React from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';

export const ResearchInsightsPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">Research & Insights</h1>
          <p className="text-sm text-fg-muted">FinBERT news sentiment feed, official PSX filings, and macro analyses</p>
        </div>
        <DemoBadge label="FinBERT Ingestion" />
      </div>
      <Card className="p-8 text-center text-fg-muted">
        Research & Insights interface building in Milestone 6...
      </Card>
    </div>
  );
};
