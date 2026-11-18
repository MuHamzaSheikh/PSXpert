import React, { useEffect, useState } from 'react';
import { Clock, ShieldAlert } from 'lucide-react';

interface MarketStatusInfo {
  isOpen: boolean;
  statusText: string;
  sessionDetails: string;
  pktTimeString: string;
}

function calculatePSXStatus(): MarketStatusInfo {
  // Get current time in Pakistan Standard Time (UTC+5)
  const now = new Date();
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  const pktDate = new Date(utc + (3600000 * 5));

  const day = pktDate.getDay(); // 0 is Sunday, 5 is Friday, 6 is Saturday
  const hours = pktDate.getHours();
  const minutes = pktDate.getMinutes();
  const totalMinutes = hours * 60 + minutes;

  const pktTimeString = pktDate.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: true,
  }) + ' PKT';

  // Weekend
  if (day === 0 || day === 6) {
    return {
      isOpen: false,
      statusText: 'Market Closed',
      sessionDetails: 'Weekend — Opens Mon 09:15 AM PKT',
      pktTimeString,
    };
  }

  // Friday Schedule: 09:15-12:00 (Session 1), 14:30-16:30 (Session 2)
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

  // Monday to Thursday Schedule: 09:15 to 15:30
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
    const interval = setInterval(() => {
      setStatus(calculatePSXStatus());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  if (compact) {
    return (
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-card text-xs font-medium">
        <span className={`w-2 h-2 rounded-full ${status.isOpen ? 'bg-bull animate-pulse' : 'bg-bear'}`} />
        <span className="font-semibold text-fg">{status.statusText}</span>
        <span className="text-fg-subtle text-[11px] font-mono hidden sm:inline">({status.pktTimeString})</span>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 sm:px-4 py-1.5 bg-bg-elevated/70 border-b border-border text-[11px] sm:text-xs text-fg-muted overflow-x-clip">
      <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-border bg-bg-card font-medium">
          <span className={`w-2 h-2 rounded-full ${status.isOpen ? 'bg-bull animate-pulse' : 'bg-bear'}`} />
          <span className={status.isOpen ? 'text-bull font-semibold' : 'text-fg-muted font-semibold'}>
            {status.statusText}
          </span>
        </div>
        <span className="text-fg-subtle hidden xs:inline">•</span>
        <span className="font-mono text-fg">{status.pktTimeString}</span>
        <span className="text-fg-subtle hidden sm:inline">•</span>
        <span className="hidden sm:inline line-clamp-1">{status.sessionDetails}</span>
      </div>

      <div className="flex items-center gap-3 text-fg-subtle ml-auto">
        <span className="hidden lg:inline">PSX Continuous &amp; Murabaha Market</span>
        <span className="flex items-center gap-1 text-[10px] sm:text-[11px] text-brand-600 dark:text-brand-400 font-medium">
          <Clock className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
          <span>DPS Real-time</span>
        </span>
      </div>
    </div>
  );
};
