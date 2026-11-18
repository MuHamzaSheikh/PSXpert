import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AppShell } from '@/components/layout/AppShell';
import { DashboardPage } from '@/pages/DashboardPage';
import { ScreenerPage } from '@/pages/ScreenerPage';
import { MarketAnalysisPage } from '@/pages/MarketAnalysisPage';
import { PortfolioPage } from '@/pages/PortfolioPage';
import { AssistantPage } from '@/pages/AssistantPage';
import { ResearchInsightsPage } from '@/pages/ResearchInsightsPage';
import { WatchlistPage } from '@/pages/WatchlistPage';
import { SettingsPage } from '@/pages/SettingsPage';

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/screener" element={<ScreenerPage />} />
        <Route path="/analysis" element={<MarketAnalysisPage />} />
        <Route path="/analysis/:symbol" element={<MarketAnalysisPage />} />
        <Route path="/portfolio" element={<PortfolioPage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/insights" element={<ResearchInsightsPage />} />
        <Route path="/watchlist" element={<WatchlistPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}

export default App;
