import React, { useEffect, useState } from 'react';
import { Clock, ShieldCheck } from 'lucide-react';

interface MarketStatusInfo {
  isOpen: boolean;
  statusText: string;
  sessionDetails: string;
  pktTimeString: string;
}

function calculatePSXStatus(): MarketStatusInfo {
  const now = new Date();
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const pktDate = new Date(utc + (3600000 * 5));

  const day = pktDate.getDay();
  const hours = pktDate.getHours();
  const minutes = pktDate.getMinutes();
  const totalMinutes = hours * 60 + minutes;

  const pktTimeString = pktDate.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }) + ' PKT';

  if (day === 0 || day === 6) {
    return {
      isOpen: false,
      statusText: 'Market Closed',
      sessionDetails: 'Weekend — Opens Mon 09:15 AM PKT',
      pktTimeString,
    };
  }

  if (day === 5) {
    const s1Start = 9 * 60 + 15;
    const s1End = 12 * 60;
    const s2Start = 14 * 60 + 30;
    const s2End = 16 * 60 + 30;

    if (totalMinutes >= s1Start && totalMinutes <= s1End) {
      return {
        isOpen: true,
        statusText: 'Market Open',
        sessionDetails: 'Friday Morning Session (Closes 12:00 PM)',
        pktTimeString,
      };
    }
    if (totalMinutes > s1End && totalMinutes < s2Start) {
      return {
        isOpen: false,
        statusText: 'Friday Break',
        sessionDetails: 'Jummah Break — Resumes 02:30 PM PKT',
        pktTimeString,
      };
    }
    if (totalMinutes >= s2Start && totalMinutes <= s2End) {
      return {
        isOpen: true,
        statusText: 'Market Open',
        sessionDetails: 'Friday Afternoon Session (Closes 04:30 PM)',
        pktTimeString,
      };
    }
    return {
      isOpen: false,
      statusText: 'Market Closed',
      sessionDetails: totalMinutes < s1Start ? 'Opens Today 09:15 AM PKT' : 'Closed for Weekend',
      pktTimeString,
    };
  }

  const openTime = 9 * 60 + 15;
  const closeTime = 15 * 60 + 30;

  if (totalMinutes >= openTime && totalMinutes <= closeTime) {
    return {
      isOpen: true,
      statusText: 'Market Open',
      sessionDetails: 'Regular Trading Session (Closes 03:30 PM)',
      pktTimeString,
    };
  }

  return {
    isOpen: false,
    statusText: 'Market Closed',
    sessionDetails: totalMinutes < openTime ? 'Opens Today 09:15 AM PKT' : 'Opens Tomorrow 09:15 AM PKT',
    pktTimeString,
  };
}

export const MarketStatusBar: React.FC<{ compact?: boolean }> = ({ compact = false }) => {
  const [status, setStatus] = useState<MarketStatusInfo>(calculatePSXStatus);

  useEffect(() => {
    const timer = setInterval(() => {
      setStatus(calculatePSXStatus());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="w-full max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 pt-2 pb-1.5 flex items-center justify-between text-[11px] sm:text-xs text-[#77736C] dark:text-[#9E988E] font-medium tracking-tight">
      {/* Left Pill: Live Market Status */}
      <div className="flex items-center gap-2 sm:gap-3 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 backdrop-blur-md px-3 py-1 rounded-full border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/15 shadow-sm">
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${status.isOpen ? 'bg-[#287A50] animate-pulse' : 'bg-[#C64C4C]'}`} />
          <span className={`font-semibold ${status.isOpen ? 'text-[#287A50] dark:text-[#34A86E]' : 'text-[#252A2B] dark:text-[#F4EFE6]'}`}>
            {status.statusText}
          </span>
        </div>
        <span className="text-[#DDD5C9] dark:text-[#77736C]">|</span>
        <span className="tabular-nums font-mono text-[#252A2B] dark:text-[#F4EFE6] font-semibold">
          {status.pktTimeString}
        </span>
        <span className="hidden md:inline text-[#DDD5C9] dark:text-[#77736C]">|</span>
        <span className="hidden md:inline text-[#77736C] dark:text-[#9E988E]">
          {status.sessionDetails}
        </span>
      </div>

      {/* Right Strip: Market Category & DPS Data indicator */}
      <div className="hidden sm:flex items-center gap-3 bg-[#FFFCF6]/60 dark:bg-[#1C2022]/60 backdrop-blur-md px-3 py-1 rounded-full border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15">
        <span className="text-[#252A2B] dark:text-[#F4EFE6] font-medium">
          PSX Continuuss &amp; Murabaha Market
        </span>
        <span className="text-[#DDD5C9] dark:text-[#77736C]">|</span>
        <div className="flex items-center gap-1.5 text-[#287A50] dark:text-[#34A86E] font-semibold">
          <span className="w-1.5 h-1.5 rounded-full bg-[#287A50]" />
          <span>DPS Real-time</span>
        </div>
      </div>
    </div>
  );
};
