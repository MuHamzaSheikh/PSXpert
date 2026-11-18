import React from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';

export const AssistantPage: React.FC = () => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg">AI Research Assistant</h1>
          <p className="text-sm text-fg-muted">Conversational market intelligence, citations & confidence calibration</p>
        </div>
        <DemoBadge label="FinBERT + RAG" />
      </div>
      <Card className="p-8 text-center text-fg-muted">
        AI Assistant interface building in Milestone 5...
      </Card>
    </div>
  );
};
