import React from 'react';
import { Navbar } from './Navbar';
import { Footer } from './Footer';
import { DisclaimerBanner } from '@/components/common/DisclaimerBanner';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  return (
    <div className="min-h-screen flex flex-col bg-bg text-fg antialiased selection:bg-brand-500/20 selection:text-brand-600">
      {/* 1. Top Navbar with Market Status Strip */}
      <Navbar />

      {/* 2. Top Diagnostic Notice */}
      <DisclaimerBanner variant="compact" dismissible />

      {/* 3. Main Page Content Viewport */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      {/* 4. Full Footer with SECP/PSX Disclaimer & Links */}
      <Footer />
    </div>
  );
};
