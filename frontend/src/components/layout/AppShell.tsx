import React from 'react';
import { Navbar } from './Navbar';
import { Footer } from './Footer';
import { DisclaimerBanner } from '@/components/common/DisclaimerBanner';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  return (
    <div className="min-h-screen flex flex-col bg-[#F4EFE6] dark:bg-[#141718] text-[#252A2B] dark:text-[#F4EFE6] antialiased selection:bg-[#694E7A]/20 selection:text-[#694E7A] relative overflow-x-clip">
      
      {/* Ambient Warm Gradient Orbs */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
        <div className="absolute -top-32 -right-32 w-[600px] h-[600px] rounded-full bg-[#E7E0D5]/70 dark:bg-[#252A2C]/40 blur-3xl" />
        <div className="absolute top-72 -left-32 w-[500px] h-[500px] rounded-full bg-[#694E7A]/5 dark:bg-[#694E7A]/10 blur-3xl" />
        <div className="absolute top-[480px] right-1/4 w-[600px] h-[600px] rounded-full bg-[#2F7D68]/5 dark:bg-[#2F7D68]/10 blur-3xl" />
      </div>

      {/* Official PSX Building Ambient Backdrop in Header Area */}
      <div className="absolute top-0 right-0 w-[380px] sm:w-[480px] md:w-[540px] h-[240px] pointer-events-none z-0 overflow-hidden opacity-40 dark:opacity-25 mix-blend-multiply dark:mix-blend-luminosity">
        <img
          src="/psx-building-crop.jpg"
          alt="Pakistan Stock Exchange Building"
          className="w-full h-full object-cover object-center [mask-image:linear-gradient(to_bottom,black_60%,transparent_100%),linear-gradient(to_left,black_60%,transparent_100%)] [mask-composite:intersect]"
        />
      </div>

      {/* 1. Top Navbar with Floating Warm Glass Architecture */}
      <Navbar />

      {/* 2. Top Diagnostic Notice */}
      <div className="relative z-10">
        <DisclaimerBanner variant="compact" dismissible />
      </div>

      {/* 3. Main Page Content Viewport */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-5 relative z-10">
        {children}
      </main>

      {/* 4. Full Footer with SECP/PSX Disclaimer & Links */}
      <Footer />
    </div>
  );
};
