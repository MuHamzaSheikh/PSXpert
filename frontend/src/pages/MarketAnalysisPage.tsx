import React from 'react';
import { useParams } from 'react-router-dom';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';

export const MarketAnalysisPage: React.FC = () => {
  const { symbol = 'KSE100' } = useParams<{ symbol?: string }>();
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">Market Analysis: {symbol.toUpperCase()}</h1>
          <p className="text-sm text-fg-muted">Candlesticks, 8 quantitative indicators, diagnostics & multi-agent committee</p>
        </div>
        <DemoBadge label="Quantitative Engine" />
      </div>
      <Card className="p-8 text-center text-fg-muted">
        Analysis interface building in Milestone 3...
      </Card>
    </div>
  );
};
